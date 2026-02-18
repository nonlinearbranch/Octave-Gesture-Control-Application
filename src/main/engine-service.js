import { EventEmitter } from 'events'
import { existsSync } from 'fs'
import { dirname, join } from 'path'
import { app } from 'electron'
import { spawn } from 'child_process'
import { createInterface } from 'readline'

const REQUEST_TIMEOUT_MS = 15000

const pickScriptPath = () => {
  const appPath = app.getAppPath()
  const unpackedRoot = appPath.includes('app.asar')
    ? appPath.replace('app.asar', 'app.asar.unpacked')
    : appPath

  const candidates = [
    join(unpackedRoot, 'service.py'),
    join(unpackedRoot, 'python_engine', 'service.py'),
    join(appPath, 'service.py'),
    join(appPath, 'python_engine', 'service.py'),
    join(process.resourcesPath, 'app.asar.unpacked', 'service.py'),
    join(process.resourcesPath, 'app.asar.unpacked', 'python_engine', 'service.py'),
    join(process.resourcesPath, 'service.py'),
    join(process.resourcesPath, 'python_engine', 'service.py'),
    join(process.cwd(), 'service.py'),
    join(process.cwd(), 'python_engine', 'service.py')
  ]

  return candidates.find((path) => existsSync(path)) || candidates[candidates.length - 1]
}

const getLaunchCandidates = () => {
  const fromEnv = process.env.OCTAVE_PYTHON_BIN
  if (fromEnv && fromEnv.trim()) {
    return [{ command: fromEnv.trim(), args: [] }]
  }

  if (process.platform === 'win32') {
    return [
      { command: 'python', args: [] },
      { command: 'py', args: ['-3'] }
    ]
  }

  return [
    { command: 'python3', args: [] },
    { command: 'python', args: [] }
  ]
}

class EngineService extends EventEmitter {
  constructor() {
    super()
    this.child = null
    this.readline = null
    this.pending = new Map()
    this.reqId = 0
    this.connected = false
    this.lastError = ''
    this.lastRuntime = null
    this.lastStatus = { connected: false, running: false, phase: 'stopped', lastError: '' }
    this.startPromise = null
  }

  getStatusSnapshot() {
    return {
      ...this.lastStatus,
      connected: this.connected,
      lastError: this.lastError || this.lastStatus.lastError || ''
    }
  }

  _rejectPending(error) {
    for (const [, job] of this.pending) {
      clearTimeout(job.timer)
      job.reject(error)
    }
    this.pending.clear()
  }

  _handleMessage(message) {
    if (!message || typeof message !== 'object') return
    if (message.type === 'response') {
      const requestId = message.id
      if (!requestId || !this.pending.has(requestId)) return
      const job = this.pending.get(requestId)
      this.pending.delete(requestId)
      clearTimeout(job.timer)
      if (message.ok) {
        job.resolve(message.data || {})
      } else {
        const reason = message?.data?.error || 'Engine command failed'
        job.reject(new Error(reason))
      }
      return
    }

    if (message.type === 'engine.ready') {
      this.connected = true
      this.lastError = ''
      this.lastStatus = {
        ...this.lastStatus,
        connected: true,
        phase: 'ready',
        lastError: ''
      }
    }

    if (message.type === 'engine.status') {
      const data = message.data || {}
      this.lastStatus = {
        connected: this.connected,
        running: Boolean(data.running),
        phase: data.phase || (data.running ? 'active' : 'stopped'),
        lastError: this.lastError || ''
      }
    }

    if (message.type === 'engine.runtime') {
      this.lastRuntime = message.data || null
    }

    if (message.type === 'engine.error') {
      const errorText =
        message?.data?.error || message?.data?.traceback || message?.data?.stage || 'Engine error'
      this.lastError = errorText
      this.lastStatus = {
        ...this.lastStatus,
        connected: this.connected,
        running: false,
        phase: 'error',
        lastError: errorText
      }
    }

    this.emit(message.type, message.data || {}, message)
  }

  _spawnWithCandidate(candidate) {
    const scriptPath = pickScriptPath()
    const command = candidate.command
    const args = [...candidate.args, scriptPath]
    const cwd = dirname(scriptPath)

    return new Promise((resolve, reject) => {
      let settled = false
      let readyTimeout = null

      const child = spawn(command, args, {
        cwd,
        stdio: ['pipe', 'pipe', 'pipe'],
        windowsHide: true,
        env: {
          ...process.env,
          PYTHONIOENCODING: 'utf-8',
          OCTAVE_DATA_DIR: app.getPath('userData')
        }
      })

      const cleanup = () => {
        if (readyTimeout) clearTimeout(readyTimeout)
      }

      const fail = (error) => {
        if (settled) return
        settled = true
        cleanup()
        try {
          child.kill()
        } catch {
          // ignore kill errors
        }
        reject(error)
      }

      child.once('error', (error) => {
        fail(error)
      })

      child.once('exit', (code, signal) => {
        if (settled) return
        fail(new Error(`Engine exited early (${code ?? 'null'}, ${signal ?? 'null'})`))
      })

      const rl = createInterface({ input: child.stdout })
      rl.on('line', (line) => {
        let parsed = null
        try {
          parsed = JSON.parse(line)
        } catch {
          return
        }
        if (parsed.type === 'engine.ready' && !settled) {
          settled = true
          cleanup()
          rl.close()
          resolve({ child, scriptPath, command, args })
        }
      })

      readyTimeout = setTimeout(() => {
        fail(new Error('Engine startup timed out'))
      }, 7000)
    })
  }

  async ensureStarted() {
    if (this.child && !this.child.killed) {
      return true
    }
    if (this.startPromise) {
      await this.startPromise
      return true
    }

    this.startPromise = (async () => {
      const candidates = getLaunchCandidates()
      let lastErr = null

      for (const candidate of candidates) {
        try {
          const started = await this._spawnWithCandidate(candidate)
          this.child = started.child
          this.connected = true
          this.lastError = ''
          this.lastStatus = {
            connected: true,
            running: false,
            phase: 'ready',
            lastError: ''
          }

          this.readline = createInterface({ input: this.child.stdout })
          this.readline.on('line', (line) => {
            try {
              const parsed = JSON.parse(line)
              this._handleMessage(parsed)
            } catch {
              // ignore non-json lines
            }
          })

          this.child.stderr.on('data', (chunk) => {
            const text = String(chunk || '').trim()
            if (!text) return
            this.emit('engine.stderr', { text })
          })

          this.child.once('exit', (code, signal) => {
            this.connected = false
            this.child = null
            this.lastStatus = {
              connected: false,
              running: false,
              phase: 'stopped',
              lastError: this.lastError
            }
            this._rejectPending(
              new Error(`Engine process exited (${code ?? 'null'}, ${signal ?? 'null'})`)
            )
            this.emit('engine.status', this.getStatusSnapshot())
          })

          return true
        } catch (error) {
          lastErr = error
        }
      }

      this.connected = false
      this.lastError = lastErr?.message || 'Unable to start Python engine'
      this.lastStatus = {
        connected: false,
        running: false,
        phase: 'error',
        lastError: this.lastError
      }
      throw lastErr || new Error(this.lastError)
    })()

    try {
      await this.startPromise
      return true
    } finally {
      this.startPromise = null
    }
  }

  async request(cmd, payload = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
    await this.ensureStarted()
    if (!this.child || this.child.killed || !this.child.stdin.writable) {
      throw new Error('Engine is not available')
    }
    const id = `req-${++this.reqId}-${Date.now()}`
    const message = { id, cmd, payload }

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`Engine request timeout: ${cmd}`))
      }, timeoutMs)
      this.pending.set(id, { resolve, reject, timer })
      try {
        this.child.stdin.write(JSON.stringify(message) + '\n')
      } catch (error) {
        this.pending.delete(id)
        clearTimeout(timer)
        reject(error)
      }
    })
  }

  async stopProcess() {
    if (!this.child || this.child.killed) return
    try {
      await this.request('engine.stop', {}, 4000)
    } catch {
      // ignore stop request failures and kill directly
    }
    if (this.child) {
      this.child.kill()
    }
    this.child = null
    this.connected = false
    this.lastStatus = {
      connected: false,
      running: false,
      phase: 'stopped',
      lastError: this.lastError
    }
  }
}

export const engineService = new EngineService()

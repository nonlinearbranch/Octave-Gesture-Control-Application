import { app, BrowserWindow, ipcMain, Notification, Menu } from 'electron'
import { join, resolve } from 'path'
import { existsSync, readFileSync } from 'fs'
import { spawn } from 'child_process'
import net from 'net'

let mainWindow = null
let engineProcess = null
let engineStatus = { running: false, phase: 'stopped', mode: 'HAND' }
let trainingTimer = null
let currentTraining = null

const ENGINE_PORT = 50556
const ENGINE_HOST = '127.0.0.1'
const ENGINE_EXE_DEBUG = resolve(__dirname, '../../../build/Debug/spider_slice1.exe')
const ENGINE_EXE_RELEASE = resolve(__dirname, '../../../build/Release/spider_slice1.exe')
const ENGINE_EXE_ROOT = resolve(__dirname, '../../../build/spider_slice1.exe')

function resolveEngineExecutable() {
  // Prefer the release-style/root binary before Debug.
  // Debug executables are more fragile on Windows after rollbacks because they may
  // depend on a local debug runtime/toolchain state that is no longer present.
  const candidates = [ENGINE_EXE_RELEASE, ENGINE_EXE_ROOT, ENGINE_EXE_DEBUG]
  return candidates.find((candidate) => existsSync(candidate)) || ENGINE_EXE_ROOT
}
function broadcast(channel, payload) {
  BrowserWindow.getAllWindows().forEach((win) => {
    if (!win.isDestroyed()) {
      win.webContents.send(channel, payload)
    }
  })
}

function setEngineStatus(next) {
  engineStatus = { ...engineStatus, ...next }
  broadcast('engine:status', engineStatus)
}

function loadJsonConfig(filePath) {
  try {
    const raw = readFileSync(filePath, 'utf8')
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

function loadGestureConfig() {
  const projectRoot = resolve(__dirname, '../../..')
  const configDir = resolve(projectRoot, 'ml/config')
  return {
    default_mapping: loadJsonConfig(resolve(configDir, 'default_mapping.json')),
    user_mapping: loadJsonConfig(resolve(configDir, 'user_mapping.json')),
    override_state: loadJsonConfig(resolve(configDir, 'override_state.json'))
  }
}

function sendEngineCommand(command) {
  return new Promise((resolvePromise, rejectPromise) => {
    const client = net.createConnection({ host: ENGINE_HOST, port: ENGINE_PORT }, () => {
      client.write(`${JSON.stringify(command)}\n`)
      client.end()
    })

    let buffer = ''
    client.on('data', (chunk) => {
      buffer += chunk.toString('utf8')
    })
    client.on('end', () => {
      try {
        resolvePromise(buffer.trim() ? JSON.parse(buffer) : { ok: true })
      } catch (error) {
        rejectPromise(error)
      }
    })
    client.on('error', rejectPromise)
  })
}

async function waitForEngineReady(timeoutMs = 8000) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    try {
      await sendEngineCommand({ command: 'list_gestures' })
      return true
    } catch (error) {
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 300))
    }
  }
  return false
}

async function syncEngineMode() {
  try {
    const result = await sendEngineCommand({ command: 'get_mode' })
    if (result?.mode) {
      setEngineStatus({ mode: result.mode })
    }
  } catch {
    // ignore mode sync failures during startup
  }
}

function stopTrainingTimer() {
  if (trainingTimer) {
    clearInterval(trainingTimer)
    trainingTimer = null
  }
}

function startTrainingProgress(session) {
  stopTrainingTimer()
  trainingTimer = setInterval(async () => {
    try {
      const status = await sendEngineCommand({ command: 'recording_status' })
      const sampleCount = Number(status.sample_count || 0)
      const targetSamples = Math.max(1, Number(status.target_samples || 320))
      const progress = Math.max(0, Math.min(100, Math.floor((sampleCount / targetSamples) * 100)))
      const payload = {
        sessionId: session.sessionId,
        gestureId: session.gestureId,
        progress,
        sampleCount,
        targetSamples,
        done: sampleCount >= targetSamples
      }
      broadcast('training:progress', payload)
      if (sampleCount >= targetSamples) {
        stopTrainingTimer()
      }
    } catch (error) {
      broadcast('training:progress', {
        sessionId: session.sessionId,
        gestureId: session.gestureId,
        progress: 0,
        error: error.message || 'Could not read recording status'
      })
    }
  }, 500)
}

async function startEngineProcess() {
  if (engineProcess && !engineProcess.killed) {
    setEngineStatus({ running: true, phase: 'running' })
    return { ok: true }
  }

  const engineExe = resolveEngineExecutable()
  const engineCwd = resolve(__dirname, '../../../')

  if (!existsSync(engineExe)) {
    setEngineStatus({ running: false, phase: 'error' })
    return { ok: false, error: `Engine executable not found at ${engineExe}` }
  }

  setEngineStatus({ running: false, phase: 'starting' })

  try {
    console.log(`[engine:start] launching ${engineExe} (cwd=${engineCwd})`)
    engineProcess = spawn(engineExe, [], {
      cwd: engineCwd,
      stdio: 'ignore',
      windowsHide: true
    })
  } catch (error) {
    setEngineStatus({ running: false, phase: 'error' })
    return {
      ok: false,
      error: `Failed to spawn engine at ${engineExe}: ${error.message || String(error)}`
    }
  }

  engineProcess.once('error', (error) => {
    console.error(`[engine:start] spawn failed for ${engineExe}:`, error)
    engineProcess = null
    setEngineStatus({ running: false, phase: 'error' })
  })

  engineProcess.once('exit', (code, signal) => {
    console.error(`[engine:start] engine exited code=${code} signal=${signal ?? 'none'}`)
    engineProcess = null
    setEngineStatus({ running: false, phase: 'stopped' })
  })

  const ready = await waitForEngineReady()
  if (!ready) {
    setEngineStatus({ running: false, phase: 'error' })
    if (engineProcess && !engineProcess.killed) {
      engineProcess.kill()
      engineProcess = null
    }
    return {
      ok: false,
      error: `Engine started from ${engineExe} but did not become ready. Check whether the engine opened port 50556 and whether the Python ML service came up cleanly.`
    }
  }
  await syncEngineMode()
  setEngineStatus({ running: true, phase: 'running' })
  return { ok: true }
}

async function stopEngineProcess() {
  stopTrainingTimer()
  currentTraining = null
  if (engineProcess && !engineProcess.killed) {
    if (process.platform === 'win32' && engineProcess.pid) {
      await new Promise((resolvePromise) => {
        const killer = spawn('taskkill', ['/PID', String(engineProcess.pid), '/T', '/F'], {
          windowsHide: true,
          stdio: 'ignore'
        })
        killer.once('exit', resolvePromise)
        killer.once('error', () => {
          try {
            engineProcess.kill()
          } catch {
            // ignore process already gone
          }
          resolvePromise()
        })
      })
    } else {
      engineProcess.kill()
    }
    engineProcess = null
  }
  setEngineStatus({ running: false, phase: 'stopped' })
  return { ok: true }
}

function mapListGesturesResult(result, config = loadGestureConfig()) {
  const labels = Array.isArray(result.gestures) ? result.gestures : []
  const defaultStatic = config.default_mapping?.static || {}
  const defaultDynamic = config.default_mapping?.dynamic || {}
  const userStatic = config.user_mapping?.static || {}
  const userDynamic = config.user_mapping?.dynamic || {}
  const voiceActions = result.mapping?.voice_actions || {}

  const defaultStaticGestures = Object.entries(defaultStatic).map(([label, item]) => ({
    label,
    name: item?.name || label,
    action: item?.action || 'None',
    ownership: 'default',
    controlModel: 'static',
    type: 'hand'
  }))
  const defaultDynamicGestures = Object.entries(defaultDynamic).map(([label, item]) => ({
    label,
    name: item?.name || label,
    action: item?.action || 'None',
    ownership: 'default',
    controlModel: 'dynamic',
    type: 'hand'
  }))
  const customStaticGestures = Object.entries(userStatic).map(([label, item]) => ({
    label,
    name: item?.name || label,
    action: item?.action || result.mapping?.static_actions?.[item?.name] || 'Click',
    ownership: 'custom',
    controlModel: 'static',
    type: 'hand'
  }))
  const customDynamicGestures = Object.entries(userDynamic).map(([label, item]) => ({
    label,
    name: item?.name || label,
    action: item?.action || result.mapping?.static_actions?.[item?.name] || 'Adjust',
    ownership: 'custom',
    controlModel: 'dynamic',
    type: 'hand'
  }))
  const customVoiceGestures = Object.entries(voiceActions).map(([phrase, action]) => ({
    phrase,
    name: phrase,
    action,
    ownership: 'custom',
    controlModel: 'static',
    type: 'voice'
  }))

  return {
    ok: result.ok !== false,
    gestures: labels.map((label) => ({ name: label, label })),
    partitions: {
      default: {
        static: defaultStaticGestures,
        dynamic: defaultDynamicGestures
      },
      custom: {
        static: customStaticGestures,
        dynamic: customDynamicGestures,
        voice: customVoiceGestures
      }
    },
    mapping: {
      disabled_static: result.mapping?.disabled_static || [],
      static_actions: result.mapping?.static_actions || {},
      voice_actions: result.mapping?.voice_actions || {}
    },
    voice_actions: result.mapping?.voice_actions || {}
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 820,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  const template = [
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn', accelerator: 'CommandOrControl+=' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    }
  ]
  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)

  createWindow()
  setEngineStatus({ running: false, phase: 'stopped' })

  ipcMain.handle('app:is-startup-supported', () => {
    return process.platform === 'win32' || process.platform === 'darwin'
  })

  ipcMain.handle('app:get-startup-enabled', () => {
    if (process.platform === 'win32' || process.platform === 'darwin') {
      return app.getLoginItemSettings().openAtLogin
    }
    return false
  })

  ipcMain.handle('app:set-startup-enabled', (_event, enabled) => {
    if (process.platform !== 'win32' && process.platform !== 'darwin') {
      return { ok: false, enabled: false }
    }
    app.setLoginItemSettings({ openAtLogin: Boolean(enabled) })
    return { ok: true, enabled: app.getLoginItemSettings().openAtLogin }
  })

  ipcMain.handle('app:notify', (_event, payload = {}) => {
    if (!Notification.isSupported()) return false
    new Notification({
      title: payload.title || 'SPIDER',
      body: payload.body || '',
      silent: true
    }).show()
    return true
  })

  ipcMain.on('app:log', (_event, message) => {
    console.log('[Renderer]', message)
  })

  ipcMain.handle('engine:start', async () => startEngineProcess())
  ipcMain.handle('engine:stop', async () => stopEngineProcess())
  ipcMain.handle('engine:get-status', async () => engineStatus)
  ipcMain.handle('get-config', async () => {
    return loadGestureConfig()
  })
  ipcMain.handle('engine:update-settings', async (_event, payload = {}) => {
    try {
      return await sendEngineCommand({
        command: 'update_settings',
        camera_index: Number(payload.camera_index ?? 0),
        voice_input_index: Number(payload.voice_input_index ?? -1),
        hand_min_detection_confidence: Number(payload.hand_min_detection_confidence ?? 0.5),
        voice_phrase_cooldown_sec: Number(payload.voice_phrase_cooldown_sec ?? 0.5),
        notifications: Boolean(payload.notifications)
      })
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })
  ipcMain.handle('engine:update-mapping', async (_event, payload = {}) => {
    try {
      if (Array.isArray(payload.disabled_static)) {
        const labels = payload.disabled_static.join('|')
        return await sendEngineCommand({ command: 'set_disabled_static', labels })
      }
      return { ok: true }
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })
  ipcMain.handle('engine:get-mode', async () => {
    try {
      const result = await sendEngineCommand({ command: 'get_mode' })
      if (result?.mode) {
        setEngineStatus({ mode: result.mode })
      }
      return result
    } catch (error) {
      return { ok: false, error: error.message, mode: engineStatus.mode || 'HAND' }
    }
  })
  ipcMain.handle('engine:set-mode', async (_event, mode) => {
    try {
      const result = await sendEngineCommand({ command: 'set_mode', mode })
      if (result?.mode) {
        setEngineStatus({ mode: result.mode })
      }
      return result
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('gestures:list', async () => {
    try {
      const config = loadGestureConfig()
      const result = await sendEngineCommand({ command: 'list_gestures' })
      return mapListGesturesResult(result, config)
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('gesture:delete', async (_event, payload = {}) => {
    try {
      const label = payload.type === 'voice'
        ? payload.phrase || payload.label || payload.gestureName
        : payload.gestureName || payload.label || payload.phrase
      return await sendEngineCommand({ command: 'delete_gesture', label, type: payload.type || 'hand' })
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('gesture:update', async (_event, payload = {}) => {
    try {
      if (payload.type === 'voice') {
        return await sendEngineCommand({
          command: 'upsert_voice_action',
          phrase: payload.phrase || payload.oldPhrase || '',
          action: payload.action || 'Click'
        })
      }

      return await sendEngineCommand({
        command: 'upsert_gesture',
        old_name: payload.oldName || '',
        new_name: payload.newName || payload.oldName || '',
        action: payload.action || 'Click'
      })
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('training:start', async (_event, payload = {}) => {
    try {
      const gestureName = payload.gestureName || payload.label || 'CustomGesture'
      const action = payload.action || 'Click'
      const type = payload.type || 'hand'
      const phrase = payload.phrase || ''

      if (type === 'voice') {
        currentTraining = {
          sessionId: `session-${Date.now()}`,
          gestureId: payload.gestureId || gestureName,
          gestureName,
          type,
          action,
          phrase
        }
        startTrainingProgress(currentTraining)
        return {
          ok: true,
          sessionId: currentTraining.sessionId,
          gestureId: currentTraining.gestureId,
          type
        }
      }

      const result = await sendEngineCommand({
        command: 'start_recording',
        label: gestureName,
        action,
        gesture_type: payload.controlModel || 'static'
      })
      if (result.ok === false) {
        return result
      }

      currentTraining = {
        sessionId: `session-${Date.now()}`,
        gestureId: payload.gestureId || gestureName,
        gestureName,
        type,
        action
      }

      startTrainingProgress(currentTraining)
      return {
        ok: true,
        sessionId: currentTraining.sessionId,
        gestureId: currentTraining.gestureId,
        type: payload.type || 'hand'
      }
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('training:complete', async () => {
    try {
      stopTrainingTimer()
      if (currentTraining?.type === 'voice') {
        const result = await sendEngineCommand({
          command: 'upsert_voice_action',
          phrase: currentTraining.phrase || currentTraining.gestureName,
          action: currentTraining.action || 'Click'
        })
        currentTraining = null
        return result
      }

      await sendEngineCommand({ command: 'stop_recording' })
      const result = await sendEngineCommand({ command: 'train_model' })
      if (result?.ok !== false && currentTraining) {
        await sendEngineCommand({
          command: 'upsert_gesture',
          old_name: currentTraining.gestureName,
          new_name: currentTraining.gestureName,
          action: currentTraining.action || 'Click'
        })
      }
      currentTraining = null
      return result
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('training:cancel', async () => {
    try {
      stopTrainingTimer()
      if (currentTraining?.type === 'voice') {
        currentTraining = null
        return { ok: true }
      }
      currentTraining = null
      return await sendEngineCommand({ command: 'stop_recording' })
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', async () => {
  if (process.platform !== 'darwin') {
    await stopEngineProcess()
    app.quit()
  }
})

import { app } from 'electron'
import { appendFileSync, mkdirSync } from 'fs'
import { dirname, join } from 'path'

const getLogPath = () => {
  try {
    return join(app.getPath('userData'), 'logs', 'main.log')
  } catch {
    return join(process.cwd(), 'octave-main.log')
  }
}

const formatExtra = (extra) => {
  if (!extra) return ''
  if (extra instanceof Error) {
    return `\n${extra.stack || extra.message}`
  }
  if (typeof extra === 'object') {
    try {
      return `\n${JSON.stringify(extra)}`
    } catch {
      return `\n${String(extra)}`
    }
  }
  return `\n${String(extra)}`
}

const writeConsole = (method, args) => {
  if (app.isPackaged && !process.stdout?.isTTY && !process.stderr?.isTTY) {
    return
  }
  try {
    console[method](...args)
  } catch {
    // Ignore broken stdout/stderr pipes in GUI mode.
  }
}

const writeLog = (level, message, extra = null) => {
  try {
    const logPath = getLogPath()
    mkdirSync(dirname(logPath), { recursive: true })
    appendFileSync(
      logPath,
      `[${new Date().toISOString()}] [${level}] ${message}${formatExtra(extra)}\n`,
      'utf8'
    )
  } catch {
    // Logging must never block app startup.
  }
}

export const logInfo = (message, extra = null) => {
  writeLog('INFO', message, extra)
  if (extra === null) {
    writeConsole('log', [message])
    return
  }
  writeConsole('log', [message, extra])
}

export const logWarn = (message, extra = null) => {
  writeLog('WARN', message, extra)
  if (extra === null) {
    writeConsole('warn', [message])
    return
  }
  writeConsole('warn', [message, extra])
}

export const logError = (message, extra = null) => {
  writeLog('ERROR', message, extra)
  if (extra === null) {
    writeConsole('error', [message])
    return
  }
  writeConsole('error', [message, extra])
}

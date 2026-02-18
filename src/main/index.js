import { app, shell, BrowserWindow, session, ipcMain, Notification } from 'electron'
import { join } from 'path'
import icon from '../../resources/icon.png?asset'
import { engineService } from './engine-service'

const isDev = !app.isPackaged

const rendererWindows = () =>
  BrowserWindow.getAllWindows().filter((window) => !window.isDestroyed())

const broadcast = (channel, payload) => {
  rendererWindows().forEach((window) => {
    const webContents = window.webContents
    if (!webContents || webContents.isDestroyed()) return
    webContents.send(channel, payload)
  })
}

const safeEngineRequest = async (cmd, payload = {}, timeoutMs) => {
  await engineService.ensureStarted()
  return engineService.request(cmd, payload, timeoutMs)
}

function loadRendererWindow(window) {
  if (isDev && process.env['ELECTRON_RENDERER_URL']) {
    window.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    window.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

function createWindow(options = {}) {
  const window = new BrowserWindow({
    title: 'Octave',
    width: 1000,
    height: 720,
    show: false,
    autoHideMenuBar: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    ...options,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  window.on('ready-to-show', () => {
    window.show()
    window.webContents.send('engine:status', engineService.getStatusSnapshot())
  })

  window.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  loadRendererWindow(window)
  return window
}

const registerEngineEvents = () => {
  engineService.on('training.progress', (payload) => {
    broadcast('training:progress', payload)
  })

  engineService.on('engine.status', (payload) => {
    broadcast('engine:status', payload)
  })

  engineService.on('engine.runtime', (payload) => {
    broadcast('engine:runtime', payload)
  })

  engineService.on('engine.error', (payload) => {
    broadcast('engine:error', payload)
  })

  engineService.on('engine.voice', (payload) => {
    broadcast('engine:voice', payload)
  })

  engineService.on('engine.stderr', (payload) => {
    broadcast('engine:stderr', payload)
  })
}

const registerIpcHandlers = () => {
  ipcMain.handle('app:get-startup-enabled', () => {
    if (process.platform === 'win32' || process.platform === 'darwin') {
      return app.getLoginItemSettings().openAtLogin
    }
    return false
  })

  ipcMain.handle('app:is-startup-supported', () => {
    return process.platform === 'win32' || process.platform === 'darwin'
  })

  ipcMain.handle('app:set-startup-enabled', (_, enabled) => {
    const nextEnabled = Boolean(enabled)
    if (process.platform !== 'win32' && process.platform !== 'darwin') {
      return { ok: false, enabled: false, reason: 'unsupported_platform' }
    }

    app.setLoginItemSettings({ openAtLogin: nextEnabled })
    return { ok: true, enabled: app.getLoginItemSettings().openAtLogin }
  })

  ipcMain.handle('app:notify', (_, payload = {}) => {
    if (!Notification.isSupported()) return false
    const title =
      typeof payload.title === 'string' && payload.title.trim() ? payload.title.trim() : 'Octave'
    const body = typeof payload.body === 'string' ? payload.body : ''
    new Notification({ title, body, silent: true }).show()
    return true
  })

  ipcMain.handle('engine:get-status', async () => {
    return { ok: true, status: engineService.getStatusSnapshot() }
  })

  ipcMain.handle('engine:health', async () => {
    try {
      const result = await safeEngineRequest('engine.health')
      return { ok: true, ...result, status: engineService.getStatusSnapshot() }
    } catch (error) {
      return {
        ok: false,
        error: error?.message || 'Failed to get engine health',
        status: engineService.getStatusSnapshot()
      }
    }
  })

  ipcMain.handle('engine:start', async () => {
    try {
      const result = await safeEngineRequest('engine.start')
      return { ok: true, ...result, status: engineService.getStatusSnapshot() }
    } catch (error) {
      return {
        ok: false,
        error: error?.message || 'Failed to start engine',
        status: engineService.getStatusSnapshot()
      }
    }
  })

  ipcMain.handle('engine:stop', async () => {
    try {
      const result = await safeEngineRequest('engine.stop')
      return { ok: true, ...result, status: engineService.getStatusSnapshot() }
    } catch (error) {
      return {
        ok: false,
        error: error?.message || 'Failed to stop engine',
        status: engineService.getStatusSnapshot()
      }
    }
  })

  ipcMain.handle('engine:update-settings', async (_, payload = {}) => {
    try {
      const result = await safeEngineRequest('engine.update_settings', payload)
      return { ok: true, ...result, status: engineService.getStatusSnapshot() }
    } catch (error) {
      return {
        ok: false,
        error: error?.message || 'Failed to update engine settings',
        status: engineService.getStatusSnapshot()
      }
    }
  })

  ipcMain.handle('engine:update-mapping', async (_, payload = {}) => {
    try {
      const result = await safeEngineRequest('engine.update_mapping', payload)
      return { ok: true, ...result, status: engineService.getStatusSnapshot() }
    } catch (error) {
      return {
        ok: false,
        error: error?.message || 'Failed to update gesture mapping',
        status: engineService.getStatusSnapshot()
      }
    }
  })

  ipcMain.handle('training:start', async (_, payload = {}) => {
    try {
      await safeEngineRequest('engine.start')
      const result = await safeEngineRequest('training.start', payload)
      return { ok: true, ...result, status: engineService.getStatusSnapshot() }
    } catch (error) {
      return {
        ok: false,
        error: error?.message || 'Failed to start training session',
        status: engineService.getStatusSnapshot()
      }
    }
  })

  ipcMain.handle('training:complete', async () => {
    try {
      const result = await safeEngineRequest('training.complete')
      if (!result?.completed) return { ok: false, reason: 'no_active_session' }
      return { ok: true, status: engineService.getStatusSnapshot() }
    } catch (error) {
      return {
        ok: false,
        error: error?.message || 'Failed to complete training session',
        status: engineService.getStatusSnapshot()
      }
    }
  })

  ipcMain.handle('training:cancel', async () => {
    try {
      const result = await safeEngineRequest('training.cancel')
      if (!result?.cancelled) return { ok: false, reason: 'no_active_session' }
      return { ok: true, status: engineService.getStatusSnapshot() }
    } catch (error) {
      return {
        ok: false,
        error: error?.message || 'Failed to cancel training session',
        status: engineService.getStatusSnapshot()
      }
    }
  })
}

app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((_, permission, callback) => {
    if (permission === 'media' || permission === 'camera' || permission === 'microphone') {
      callback(true)
      return
    }
    callback(false)
  })

  registerEngineEvents()
  registerIpcHandlers()

  if (process.platform === 'win32') {
    app.setAppUserModelId('com.octave.app')
  }

  app.on('browser-window-created', (_, window) => {
    window.webContents.on('before-input-event', (event, input) => {
      if (isDev && input.type === 'keyDown' && input.key === 'F12') {
        window.webContents.toggleDevTools()
        event.preventDefault()
      }

      const isReload =
        input.type === 'keyDown' &&
        (input.control || input.meta) &&
        input.key?.toLowerCase() === 'r'
      if (!isDev && isReload) {
        event.preventDefault()
      }
    })
  })

  createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', () => {
  void engineService.stopProcess()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    void engineService.stopProcess()
    app.quit()
  }
})

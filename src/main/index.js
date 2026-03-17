import { app, shell, BrowserWindow, session, ipcMain, Notification } from 'electron'
import { join } from 'path'
import icon from '../../resources/icon.png?asset'

const isDev = !app.isPackaged

app.setPath('sessionData', join(app.getPath('userData'), 'session'))

const hasSingleInstanceLock = app.requestSingleInstanceLock()
if (!hasSingleInstanceLock) {
  app.quit()
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
  })

  window.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  loadRendererWindow(window)
  return window
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
import { engineService } from './engine-service'

// ... existing code ...

app.whenReady().then(() => {
  // Initialize Python Engine
  engineService
    .ensureStarted()
    .then(() => {
      // Silence AV scanning overhead on Windows for future startups
      // tryAddDefenderExclusion(engineService.pythonExe)
      console.log('Engine service ready, waiting for frontend start command.')
    })
    .catch((err) => {
      console.error('Failed to start engine service:', err)
    })

  // Forward engine events to all windows
  engineService.on('training.progress', (payload) => {
    BrowserWindow.getAllWindows().forEach((win) => {
      if (!win.isDestroyed()) {
        win.webContents.send('training:progress', payload)
      }
    })
  })

  engineService.on('engine.status', (payload) => {
    BrowserWindow.getAllWindows().forEach((win) => {
      if (!win.isDestroyed()) {
        win.webContents.send('engine:status', payload)
      }
    })
  })

  engineService.on('engine.error', (payload) => {
    console.error('Forwarding engine error:', payload)
    BrowserWindow.getAllWindows().forEach((win) => {
      if (!win.isDestroyed()) {
        win.webContents.send('engine:error', payload)
      }
    })
  })

  engineService.on('engine.voice', (payload) => {
    BrowserWindow.getAllWindows().forEach((win) => {
      if (!win.isDestroyed()) {
        win.webContents.send('engine:voice', payload)
      }
    })
  })

  session.defaultSession.setPermissionRequestHandler((_, permission, callback) => {
    if (permission === 'media' || permission === 'camera' || permission === 'microphone') {
      callback(true)
      return
    }
    callback(false)
  })

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

  ipcMain.on('app:log', (_, message) => {
    console.log('[Renderer]', message)
  })

  ipcMain.handle('engine:update-settings', async (event, payload = {}) => {
    try {
      const response = await engineService.request('engine.update_settings', payload)
      return response
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('training:start', async (event, payload = {}) => {
    try {
      const response = await engineService.request('training.start', payload)
      return response
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('training:complete', async () => {
    try {
      const response = await engineService.request('training.complete', {})
      return response
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('training:cancel', async () => {
    try {
      const response = await engineService.request('training.cancel', {})
      return response
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('engine:start', async () => {
    try {
      console.log('[Main] IPC: engine:start received')
      const result = await engineService.request('engine.start', {})
      console.log('[Main] IPC: engine:start result:', result)
      return result
    } catch (error) {
      console.error('[Main] IPC: engine:start failed:', error)
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('engine:stop', async () => {
    try {
      return await engineService.request('engine.stop', {})
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('engine:get-status', () => {
    return engineService.getStatusSnapshot()
  })

  ipcMain.handle('engine:update-mapping', async (event, payload = {}) => {
    try {
      return await engineService.request('engine.update_mapping', payload)
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('gesture:update', async (event, payload = {}) => {
    try {
      return await engineService.request('gesture.update', payload)
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('gesture:delete', async (event, payload = {}) => {
    try {
      return await engineService.request('gesture.delete', payload)
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

  ipcMain.handle('gestures:list', async () => {
    try {
      return await engineService.request('gestures.list', {})
    } catch (error) {
      return { ok: false, error: error.message }
    }
  })

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

  app.on('web-contents-created', (_, webContents) => {
    webContents.on('destroyed', () => {
      // proper cleanup handled by engine service if needed
    })
  })

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('second-instance', () => {
  const [window] = BrowserWindow.getAllWindows()
  if (!window) return
  if (window.isMinimized()) {
    window.restore()
  }
  window.focus()
  window.show()
})

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and require them here.

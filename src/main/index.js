import { app, shell, BrowserWindow, session, ipcMain, Notification } from 'electron'
import { join } from 'path'
import icon from '../../resources/icon.png?asset'

const isDev = !app.isPackaged
const trainingJobs = new Map()

const stopTrainingJob = (webContentsId) => {
  const job = trainingJobs.get(webContentsId)
  if (!job) return null
  clearInterval(job.timer)
  trainingJobs.delete(webContentsId)
  return job
}

const sendTrainingProgress = (webContents, payload) => {
  if (!webContents || webContents.isDestroyed()) return
  webContents.send('training:progress', payload)
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
app.whenReady().then(() => {
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

  ipcMain.handle('training:start', (event, payload = {}) => {
    const webContents = event.sender
    const webContentsId = webContents.id
    stopTrainingJob(webContentsId)

    const type = payload?.type === 'voice' ? 'voice' : 'hand'
    const gestureId =
      typeof payload?.gestureId === 'string' && payload.gestureId.trim()
        ? payload.gestureId.trim()
        : `gesture-${Date.now()}`
    const sessionId = `${webContentsId}-${Date.now()}`
    const step = type === 'voice' ? 9 : 7
    let progress = 0

    sendTrainingProgress(webContents, {
      sessionId,
      gestureId,
      type,
      progress,
      done: false
    })

    const timer = setInterval(() => {
      const jitter = Math.floor(Math.random() * 3)
      progress = Math.min(100, progress + step + jitter)
      const done = progress >= 100

      sendTrainingProgress(webContents, {
        sessionId,
        gestureId,
        type,
        progress,
        done
      })

      if (done) {
        stopTrainingJob(webContentsId)
      }
    }, 320)

    trainingJobs.set(webContentsId, { timer, sessionId, gestureId, type })
    return { ok: true, sessionId, gestureId, type }
  })

  ipcMain.handle('training:complete', (event) => {
    const webContents = event.sender
    const webContentsId = webContents.id
    const job = stopTrainingJob(webContentsId)
    if (!job) return { ok: false, reason: 'no_active_session' }

    sendTrainingProgress(webContents, {
      sessionId: job.sessionId,
      gestureId: job.gestureId,
      type: job.type,
      progress: 100,
      done: true
    })
    return { ok: true, sessionId: job.sessionId }
  })

  ipcMain.handle('training:cancel', (event) => {
    const webContents = event.sender
    const webContentsId = webContents.id
    const job = stopTrainingJob(webContentsId)
    if (!job) return { ok: false, reason: 'no_active_session' }

    sendTrainingProgress(webContents, {
      sessionId: job.sessionId,
      gestureId: job.gestureId,
      type: job.type,
      progress: 0,
      done: false,
      cancelled: true
    })
    return { ok: true, sessionId: job.sessionId }
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
      stopTrainingJob(webContents.id)
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

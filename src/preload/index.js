import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {
  isStartupSupported: () => ipcRenderer.invoke('app:is-startup-supported'),
  getStartupEnabled: () => ipcRenderer.invoke('app:get-startup-enabled'),
  setStartupEnabled: (enabled) => ipcRenderer.invoke('app:set-startup-enabled', enabled),
  notify: (payload) => ipcRenderer.invoke('app:notify', payload),
  startTraining: (payload) => ipcRenderer.invoke('training:start', payload),
  completeTraining: () => ipcRenderer.invoke('training:complete'),
  cancelTraining: () => ipcRenderer.invoke('training:cancel'),
  onTrainingProgress: (callback) => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_, payload) => callback(payload)
    ipcRenderer.on('training:progress', listener)
    return () => ipcRenderer.removeListener('training:progress', listener)
  }
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  window.electron = electronAPI
  window.api = api
}

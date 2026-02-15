import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {
  isStartupSupported: () => ipcRenderer.invoke('app:is-startup-supported'),
  getStartupEnabled: () => ipcRenderer.invoke('app:get-startup-enabled'),
  setStartupEnabled: (enabled) => ipcRenderer.invoke('app:set-startup-enabled', enabled),
  notify: (payload) => ipcRenderer.invoke('app:notify', payload)
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

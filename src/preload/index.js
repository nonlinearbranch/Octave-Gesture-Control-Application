import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {
  isStartupSupported: () => ipcRenderer.invoke('app:is-startup-supported'),
  getStartupEnabled: () => ipcRenderer.invoke('app:get-startup-enabled'),
  setStartupEnabled: (enabled) => ipcRenderer.invoke('app:set-startup-enabled', enabled),
  notify: (payload) => ipcRenderer.invoke('app:notify', payload),
  log: (message) => ipcRenderer.send('app:log', message),
  updateSettings: (payload) => ipcRenderer.invoke('engine:update-settings', payload),
  updateMapping: (payload) => ipcRenderer.invoke('engine:update-mapping', payload),
  startTraining: (payload) => ipcRenderer.invoke('training:start', payload),
  startEngine: () => ipcRenderer.invoke('engine:start'),
  stopEngine: () => ipcRenderer.invoke('engine:stop'),
  listGestures: () => ipcRenderer.invoke('gestures:list'),
  completeTraining: () => ipcRenderer.invoke('training:complete'),
  cancelTraining: () => ipcRenderer.invoke('training:cancel'),
  updateGesture: (payload) => ipcRenderer.invoke('gesture:update', payload),
  deleteGesture: (payload) => ipcRenderer.invoke('gesture:delete', payload),
  onTrainingProgress: (callback) => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_, payload) => callback(payload)
    ipcRenderer.on('training:progress', listener)
    return () => ipcRenderer.removeListener('training:progress', listener)
  },
  onEngineStatus: (callback) => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_, payload) => callback(payload)
    ipcRenderer.on('engine:status', listener)
    return () => ipcRenderer.removeListener('engine:status', listener)
  },
  getEngineStatus: () => ipcRenderer.invoke('engine:get-status'),
  onEngineVoice: (callback) => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_, payload) => callback(payload)
    ipcRenderer.on('engine:voice', listener)
    return () => ipcRenderer.removeListener('engine:voice', listener)
  },
  onEngineError: (callback) => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_, payload) => callback(payload)
    ipcRenderer.on('engine:error', listener)
    return () => ipcRenderer.removeListener('engine:error', listener)
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

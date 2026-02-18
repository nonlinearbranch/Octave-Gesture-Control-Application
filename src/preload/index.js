import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

const subscribe = (channel, callback) => {
  if (typeof callback !== 'function') return () => {}
  const listener = (_, payload) => callback(payload)
  ipcRenderer.on(channel, listener)
  return () => ipcRenderer.removeListener(channel, listener)
}

// Custom APIs for renderer
const api = {
  isStartupSupported: () => ipcRenderer.invoke('app:is-startup-supported'),
  getStartupEnabled: () => ipcRenderer.invoke('app:get-startup-enabled'),
  setStartupEnabled: (enabled) => ipcRenderer.invoke('app:set-startup-enabled', enabled),
  notify: (payload) => ipcRenderer.invoke('app:notify', payload),

  getEngineStatus: () => ipcRenderer.invoke('engine:get-status'),
  getEngineHealth: () => ipcRenderer.invoke('engine:health'),
  startEngine: () => ipcRenderer.invoke('engine:start'),
  stopEngine: () => ipcRenderer.invoke('engine:stop'),
  updateEngineSettings: (payload) => ipcRenderer.invoke('engine:update-settings', payload),
  updateGestureMapping: (payload) => ipcRenderer.invoke('engine:update-mapping', payload),

  startTraining: (payload) => ipcRenderer.invoke('training:start', payload),
  completeTraining: () => ipcRenderer.invoke('training:complete'),
  cancelTraining: () => ipcRenderer.invoke('training:cancel'),

  onTrainingProgress: (callback) => subscribe('training:progress', callback),
  onEngineStatus: (callback) => subscribe('engine:status', callback),
  onEngineRuntime: (callback) => subscribe('engine:runtime', callback),
  onEngineError: (callback) => subscribe('engine:error', callback),
  onEngineVoice: (callback) => subscribe('engine:voice', callback),
  onEngineStderr: (callback) => subscribe('engine:stderr', callback)
}

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

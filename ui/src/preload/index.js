import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

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
  getMode: () => ipcRenderer.invoke('engine:get-mode'),
  setMode: (mode) => ipcRenderer.invoke('engine:set-mode', mode),
  listGestures: () => ipcRenderer.invoke('gestures:list'),
  getConfig: () => ipcRenderer.invoke('get-config'),
  completeTraining: () => ipcRenderer.invoke('training:complete'),
  cancelTraining: () => ipcRenderer.invoke('training:cancel'),
  updateGesture: (payload) => ipcRenderer.invoke('gesture:update', payload),
  deleteGesture: (payload) => ipcRenderer.invoke('gesture:delete', payload),
  getEngineStatus: () => ipcRenderer.invoke('engine:get-status'),
  onTrainingProgress: (callback) => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('training:progress', listener)
    return () => ipcRenderer.removeListener('training:progress', listener)
  },
  onEngineStatus: (callback) => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('engine:status', listener)
    return () => ipcRenderer.removeListener('engine:status', listener)
  },
  onEngineVoice: (callback) => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('engine:voice', listener)
    return () => ipcRenderer.removeListener('engine:voice', listener)
  },
  onEngineError: (callback) => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('engine:error', listener)
    return () => ipcRenderer.removeListener('engine:error', listener)
  }
}

if (process.contextIsolated) {
  contextBridge.exposeInMainWorld('electron', electronAPI)
  contextBridge.exposeInMainWorld('api', api)
} else {
  window.electron = electronAPI
  window.api = api
}

import { useEffect, useMemo, useRef, useState } from 'react'

const TABS = [
  { id: 'gesture-library', label: 'Gesture Library' },
  { id: 'settings', label: 'Settings' }
]

const DEFAULT_GESTURES = [
  {
    id: 'dyn-magnitude-control',
    title: 'Magnitude Control',
    subtitle: 'Open Palm Up/Down for Increase/Decrease',
    type: 'hand',
    family: 'Magnitude Control Family',
    controlModel: 'dynamic',
    dynamicTargets: ['Volume', 'Brightness', 'Zoom', 'Scroll Speed', 'Playback Speed'],
    enabled: true,
    locked: true,
    demo: 'up',
    howTo: [
      'Show a flat open palm with all fingers extended.',
      'Move your hand up to increase the active parameter.',
      'Move your hand down to decrease the active parameter.'
    ]
  },
  {
    id: 'dyn-cursor-control',
    title: 'Cursor Control',
    subtitle: 'Index Finger Pointing for Mouse Movement',
    type: 'hand',
    family: 'Cursor Control Family',
    controlModel: 'dynamic',
    dynamicTargets: ['Mouse Movement', 'Hover', 'UI Selection'],
    enabled: true,
    locked: true,
    demo: 'right',
    howTo: [
      'Extend only the index finger and keep other fingers folded.',
      'Move your pointing finger in space to move the cursor.',
      'Pause over controls to hover and select targets.'
    ]
  },
  {
    id: 'dyn-grab-drag',
    title: 'Grab and Drag',
    subtitle: 'Pinch Hold to Grab, Move to Drag, Release to Drop',
    type: 'hand',
    family: 'Grab & Drag Family',
    controlModel: 'dynamic',
    dynamicTargets: ['Drag Windows', 'Move Files', 'Resize', 'Select Items'],
    enabled: true,
    locked: true,
    demo: 'pinch',
    howTo: [
      'Pinch thumb and index to start a grab.',
      'Keep pinch held while moving to drag objects.',
      'Release pinch to drop at the current position.'
    ]
  },
  {
    id: 'dyn-navigation-control',
    title: 'Navigation Control',
    subtitle: 'Index Finger Left/Right for Back/Forward Navigation',
    type: 'hand',
    family: 'Navigation Family',
    controlModel: 'dynamic',
    dynamicTargets: [
      'Switch Tabs',
      'Switch Desktops',
      'Slides Next/Previous',
      'Timeline Scrubbing'
    ],
    enabled: true,
    locked: true,
    demo: 'right',
    howTo: [
      'Extend index finger and move horizontally.',
      'Move left for previous/back actions.',
      'Move right for next/forward actions.'
    ]
  },
  {
    id: 'dyn-rotation-dial',
    title: 'Rotation Dial',
    subtitle: 'Curved Hand Wrist Rotation for Knob-Style Controls',
    type: 'hand',
    family: 'Rotation / Dial Family',
    controlModel: 'dynamic',
    dynamicTargets: ['3D Rotation', 'Hue Adjustment', 'Knob Controls'],
    enabled: true,
    locked: true,
    demo: 'hold',
    howTo: [
      'Keep an open but slightly curved hand shape.',
      'Rotate wrist clockwise to increase dial value.',
      'Rotate wrist anticlockwise to decrease dial value.'
    ]
  },
  {
    id: 'dyn-scroll-control',
    title: 'Scroll Control',
    subtitle: 'Two Fingers Up/Down for Continuous Scroll',
    type: 'hand',
    family: 'Scroll Family',
    controlModel: 'dynamic',
    dynamicTargets: ['Web Scroll', 'Code Scroll', 'Chat Scroll'],
    enabled: true,
    locked: true,
    demo: 'up',
    howTo: [
      'Extend two fingers together.',
      'Move upward to scroll up.',
      'Move downward to scroll down.'
    ]
  },
  {
    id: 'st-fist-play-pause',
    title: 'Closed Fist',
    subtitle: 'Play / Pause',
    type: 'hand',
    family: 'Static Command Family',
    controlModel: 'static',
    defaultAction: 'Play/Pause Media',
    enabled: true,
    locked: true,
    demo: 'hold',
    howTo: [
      'Form a clear closed fist gesture.',
      'Hold for a short confirmation beat.',
      'Triggers a one-time play/pause action.'
    ]
  },
  {
    id: 'st-thumbs-up-mute',
    title: 'Thumbs Up',
    subtitle: 'Mute / Unmute',
    type: 'hand',
    family: 'Static Command Family',
    controlModel: 'static',
    defaultAction: 'Mute/Unmute Audio',
    enabled: true,
    locked: true,
    demo: 'up',
    howTo: [
      'Show a clear thumbs-up with stable hand orientation.',
      'Keep gesture in frame for confirmation.',
      'Toggles mute state once per trigger.'
    ]
  },
  {
    id: 'st-v-sign-next-prev',
    title: 'V Sign',
    subtitle: 'Next / Previous',
    type: 'hand',
    family: 'Static Command Family',
    controlModel: 'static',
    defaultAction: 'Navigate Next/Previous',
    enabled: true,
    locked: true,
    demo: 'right',
    howTo: [
      'Show a clear V sign with index and middle finger.',
      'Optional: slight right movement for next, left for previous.',
      'Triggers discrete navigation command.'
    ]
  },
  {
    id: 'st-ok-sign-confirm',
    title: 'OK Sign',
    subtitle: 'Confirm / Enter',
    type: 'hand',
    family: 'Static Command Family',
    controlModel: 'static',
    defaultAction: 'Confirm / Enter',
    enabled: true,
    locked: true,
    demo: 'pinch',
    howTo: [
      'Touch thumb and index finger into an OK circle.',
      'Keep the gesture steady for a brief moment.',
      'Sends one-time confirm action.'
    ]
  },
  {
    id: 'st-mode-switch-cycle',
    title: 'Three-Finger Mode Switch',
    subtitle: 'Hold to Cycle Active Control Mode',
    type: 'hand',
    family: 'Static Command Family',
    controlModel: 'static',
    defaultAction: 'Switch Active Dynamic Mode',
    modeCycle: ['Volume', 'Brightness', 'Zoom', 'Scroll', 'Cursor'],
    enabled: true,
    locked: true,
    demo: 'hold',
    howTo: [
      'Extend index, middle, and ring fingers only.',
      'Hold for about one second to confirm mode switch.',
      'Cycles control mode in order: Volume to Cursor.'
    ]
  },
  {
    id: 'st-drs-frame-power',
    title: 'DRS Frame Power Command',
    subtitle: 'Third Umpire Review Signal (Showcase Automation)',
    type: 'hand',
    family: 'Power Command Gesture',
    controlModel: 'static',
    defaultAction: 'Launch VS Code',
    enabled: true,
    locked: true,
    demo: 'hold',
    howTo: [
      'Use two hands to form a review-frame/T shape.',
      'Hold steady for around one second.',
      'Default showcase action launches VS Code. Rebind later if needed.'
    ]
  }
]

const HAND_TRAINING_CUES = [
  'Center your hand in frame.',
  'Rotate your hand slightly left and right.',
  'Move closer, then farther for scale coverage.',
  'Hold steady for final confirmation.'
]

const VOICE_TRAINING_CUES = [
  'Speak your trigger phrase clearly.',
  'Repeat with natural pace changes.',
  'Record one low-volume and one strong sample.',
  'Add one sample with mild background noise.'
]

const getCueIndexFromProgress = (type, progress) => {
  const cueList = type === 'voice' ? VOICE_TRAINING_CUES : HAND_TRAINING_CUES
  const normalized = Math.max(0, Math.min(100, Number(progress) || 0))
  return Math.min(cueList.length - 1, Math.floor((normalized / 100) * cueList.length))
}

const cloneDefaultGestures = () =>
  DEFAULT_GESTURES.map((gesture) => ({
    ...gesture,
    enabled: gesture.enabled !== false,
    howTo: Array.isArray(gesture.howTo) ? [...gesture.howTo] : []
  }))

const DEFAULT_LIBRARY_VISIBLE = 8

const ADD_GESTURE_SECTIONS = [
  {
    id: 'dynamic',
    label: 'Dynamic Controls',
    help: 'Use this when you want smooth, continuous control while gesture is active.',
    items: [
      {
        id: 'custom-dynamic-hand',
        title: 'Dynamic Hand Control',
        subtitle: 'Continuous control (magnitude, cursor, drag, dial, scroll).',
        fromUserView: 'I want to control something continuously with my hand movement.',
        example: 'Volume up/down by moving an open palm',
        type: 'hand',
        controlModel: 'dynamic',
        family: 'Dynamic Gesture Family',
        templateTitle: 'New Dynamic Gesture',
        templateSubtitle: 'Continuous control mapping'
      },
      {
        id: 'custom-dynamic-voice',
        title: 'Dynamic Voice Control',
        subtitle: 'Continuous voice-driven control profile.',
        fromUserView: 'I want voice-driven continuous control instead of hand movement.',
        example: 'Progressive zoom control from voice cues',
        type: 'voice',
        controlModel: 'dynamic',
        family: 'Dynamic Voice Family',
        templateTitle: 'New Dynamic Voice Gesture',
        templateSubtitle: 'Continuous voice control mapping',
        phrase: 'Your dynamic command'
      }
    ]
  },
  {
    id: 'static',
    label: 'Static Commands',
    help: 'Use this when one gesture/phrase should trigger one single action.',
    items: [
      {
        id: 'custom-static-hand',
        title: 'Static Hand Command',
        subtitle: 'One-time hand trigger action.',
        fromUserView: 'I want one hand sign to trigger one action.',
        example: 'Closed fist to Play/Pause',
        type: 'hand',
        controlModel: 'static',
        family: 'Static Command Family',
        templateTitle: 'New Static Gesture',
        templateSubtitle: 'One-time hand action mapping'
      },
      {
        id: 'custom-static-voice',
        title: 'Static Voice Command',
        subtitle: 'One-time voice trigger phrase.',
        fromUserView: 'I want one voice phrase to trigger one action.',
        example: 'Say "next tab" to switch tab',
        type: 'voice',
        controlModel: 'static',
        family: 'Static Command Voice Family',
        templateTitle: 'New Voice Command',
        templateSubtitle: 'One-time voice action mapping',
        phrase: 'Your command phrase'
      }
    ]
  },
  {
    id: 'power',
    label: 'Power Command',
    help: 'Use this for a high-impact shortcut that launches a workflow.',
    items: [
      {
        id: 'custom-power-automation',
        title: 'Power Automation',
        subtitle: 'High-impact custom workflow trigger.',
        fromUserView: 'I want one custom gesture to run a powerful shortcut.',
        example: 'DRS frame gesture to launch VS Code',
        type: 'hand',
        controlModel: 'static',
        family: 'Power Command Gesture',
        templateTitle: 'New Power Command',
        templateSubtitle: 'Automation trigger mapping'
      }
    ]
  }
]

const DEFAULT_SETTINGS = {
  selectedCameraId: '',
  selectedMicId: '',
  gestureSensitivity: 70,
  actionCooldownMs: 450,
  launchOnStartup: false,
  notifications: true,
  confirmBeforeDelete: true,
  openMonitoringAfterAdd: true
}

const readBool = (value, fallback) => (typeof value === 'boolean' ? value : fallback)
const readNum = (value, fallback) =>
  typeof value === 'number' && !Number.isNaN(value) ? value : fallback

// eslint-disable-next-line react/prop-types
function SidebarIcon({ tabId }) {
  if (tabId === 'gesture-library') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden>
        <path d="M5.75 4A1.75 1.75 0 0 0 4 5.75v12.5C4 19.22 4.78 20 5.75 20h12.5c.97 0 1.75-.78 1.75-1.75V5.75C20 4.78 19.22 4 18.25 4H5.75Zm0 1.5h12.5c.14 0 .25.11.25.25v12.5a.25.25 0 0 1-.25.25H5.75a.25.25 0 0 1-.25-.25V5.75c0-.14.11-.25.25-.25Zm2.5 2.25a.75.75 0 0 0-.75.75v7a.75.75 0 0 0 1.5 0v-7a.75.75 0 0 0-.75-.75Zm3.75 1.75a.75.75 0 0 0-.75.75v5.25a.75.75 0 0 0 1.5 0v-5.25a.75.75 0 0 0-.75-.75Zm3.75-2.25a.75.75 0 0 0-.75.75v7a.75.75 0 0 0 1.5 0v-7a.75.75 0 0 0-.75-.75Z" />
      </svg>
    )
  }
  if (tabId === 'live-monitoring') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden>
        <path d="M5.5 5A2.5 2.5 0 0 0 3 7.5v9A2.5 2.5 0 0 0 5.5 19h13a2.5 2.5 0 0 0 2.5-2.5v-9A2.5 2.5 0 0 0 18.5 5h-13Zm0 1.5h13c.55 0 1 .45 1 1v9c0 .55-.45 1-1 1h-13c-.55 0-1-.45-1-1v-9c0-.55.45-1 1-1Zm2.29 8.96a.75.75 0 0 1-.12-1.05l2.24-2.8a.75.75 0 0 1 1.14-.03l1.69 1.93 2.31-3.07a.75.75 0 1 1 1.2.9l-2.86 3.8a.75.75 0 0 1-1.13.06l-1.7-1.94-1.67 2.08a.75.75 0 0 1-1.05.12Z" />
      </svg>
    )
  }
  return (
    <svg
      className="icon-gear"
      viewBox="0 0 24 24"
      aria-hidden
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82L4.2 7.2a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden>
      <path d="M10.5 4a6.5 6.5 0 0 1 5.14 10.48l3.94 3.94a.75.75 0 1 1-1.06 1.06l-3.94-3.94A6.5 6.5 0 1 1 10.5 4Zm0 1.5a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z" />
    </svg>
  )
}

function SunIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  )
}

function EditIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden>
      <path d="m16.4 3.6 4 4a1 1 0 0 1 0 1.4l-9.6 9.6a1 1 0 0 1-.43.25l-4.35 1.08a.75.75 0 0 1-.9-.9l1.08-4.35a1 1 0 0 1 .25-.43L16.4 3.6Zm-8.17 11.45-.56 2.26 2.26-.56 8.88-8.89-1.7-1.7-8.88 8.9Z" />
    </svg>
  )
}

function DeleteIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden>
      <path d="M9.5 4a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 4v.5h3a.75.75 0 0 1 0 1.5h-.5v11.1A2.4 2.4 0 0 1 14.6 19.5H9.4A2.4 2.4 0 0 1 7 17.1V6h-.5a.75.75 0 0 1 0-1.5h3V4ZM11 4v.5h2V4h-2ZM8.5 6v11.1c0 .5.4.9.9.9h5.2c.5 0 .9-.4.9-.9V6h-7Zm2.2 2.1a.75.75 0 0 1 .75.75v6a.75.75 0 0 1-1.5 0v-6a.75.75 0 0 1 .75-.75Zm3.3.75a.75.75 0 0 0-1.5 0v6a.75.75 0 0 0 1.5 0v-6Z" />
    </svg>
  )
}

function BrandLogo() {
  return (
    <svg viewBox="0 0 42 42" aria-hidden>
      <defs>
        <linearGradient id="oct-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#0f1e43" />
          <stop offset="100%" stopColor="#0a1632" />
        </linearGradient>
        <linearGradient id="oct-spider" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#b9ecff" />
          <stop offset="100%" stopColor="#46a5ff" />
        </linearGradient>
        <clipPath id="oct-circle-clip">
          <circle cx="21" cy="21" r="17.5" />
        </clipPath>
      </defs>
      <circle cx="21" cy="21" r="18.4" fill="url(#oct-bg)" stroke="#bfd6f8" strokeWidth="1.2" />
      <g
        clipPath="url(#oct-circle-clip)"
        stroke="url(#oct-spider)"
        strokeWidth="1.7"
        strokeLinecap="round"
        fill="none"
      >
        <path d="M12 11l4.2 5M30 11l-4.2 5M8.8 17.5l6.2 2M33.2 17.5l-6.2 2M8.5 24.5l6.8-1.3M33.5 24.5l-6.8-1.3M11 30l5.4-4M31 30l-5.4-4" />
      </g>
      <g fill="url(#oct-spider)">
        <ellipse cx="21" cy="16.2" rx="4.7" ry="4" />
        <ellipse cx="21" cy="24.5" rx="5.8" ry="6.5" />
      </g>
      <circle cx="21" cy="20.4" r="2.6" fill="#95ecff" />
    </svg>
  )
}

function App() {
  const [tab, setTab] = useState('gesture-library')
  const [search, setSearch] = useState('')
  const [darkMode, setDarkMode] = useState(() => {
    try {
      return localStorage.getItem('octave:darkMode') === 'true'
    } catch {
      return false
    }
  })
  const [gestures, setGestures] = useState(() => cloneDefaultGestures())
  const [selectedGesture, setSelectedGesture] = useState(null)
  const [editingGesture, setEditingGesture] = useState(null)
  const [showAddTypePopup, setShowAddTypePopup] = useState(false)
  const [showPermissionPopup, setShowPermissionPopup] = useState(false)
  const [pendingGesturePreset, setPendingGesturePreset] = useState(null)
  const [pendingDeleteGesture, setPendingDeleteGesture] = useState(null)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [trainingSession, setTrainingSession] = useState(null)
  const [showAllDefaultGestures, setShowAllDefaultGestures] = useState(false)
  const [settings, setSettings] = useState(() => {
    try {
      const raw = localStorage.getItem('octave:settings')
      if (!raw) return DEFAULT_SETTINGS
      const parsed = JSON.parse(raw)
      return {
        selectedCameraId:
          typeof parsed.selectedCameraId === 'string' ? parsed.selectedCameraId : '',
        selectedMicId: typeof parsed.selectedMicId === 'string' ? parsed.selectedMicId : '',
        gestureSensitivity: readNum(parsed.gestureSensitivity, DEFAULT_SETTINGS.gestureSensitivity),
        actionCooldownMs: readNum(parsed.actionCooldownMs, DEFAULT_SETTINGS.actionCooldownMs),
        launchOnStartup: readBool(parsed.launchOnStartup, DEFAULT_SETTINGS.launchOnStartup),
        notifications: readBool(parsed.notifications, DEFAULT_SETTINGS.notifications),
        confirmBeforeDelete: readBool(
          parsed.confirmBeforeDelete,
          DEFAULT_SETTINGS.confirmBeforeDelete
        ),
        openMonitoringAfterAdd: readBool(
          parsed.openMonitoringAfterAdd,
          DEFAULT_SETTINGS.openMonitoringAfterAdd
        )
      }
    } catch {
      return DEFAULT_SETTINGS
    }
  })
  const [devices, setDevices] = useState({ cameras: [], microphones: [] })
  const [mediaReady, setMediaReady] = useState(false)
  const [startupSupported, setStartupSupported] = useState(true)
  const [cameraStatus, setCameraStatus] = useState('idle')
  const [micStatus, setMicStatus] = useState('idle')
  const [micLevel, setMicLevel] = useState(0)
  const [mediaError, setMediaError] = useState('')
  const videoRef = useRef(null)
  const cameraStreamRef = useRef(null)
  const micStreamRef = useRef(null)
  const micFrameRef = useRef(null)

  const notifyUser = async (title, body, force = false) => {
    if (!force && !settings.notifications) return
    try {
      if (window.api?.notify) {
        await window.api.notify({ title, body })
      }
    } catch {
      // desktop notification is optional
    }
  }

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light')
    try {
      localStorage.setItem('octave:darkMode', String(darkMode))
    } catch {
      // ignore storage failures; theme still works in-memory
    }
  }, [darkMode])

  useEffect(() => {
    try {
      localStorage.setItem('octave:settings', JSON.stringify(settings))
    } catch {
      // ignore storage failures; settings still work in-memory
    }
  }, [settings])

  useEffect(() => {
    let cancelled = false
    const syncStartupSupport = async () => {
      if (!window.api?.isStartupSupported) return
      try {
        const supported = await window.api.isStartupSupported()
        if (!cancelled) setStartupSupported(Boolean(supported))
      } catch {
        if (!cancelled) setStartupSupported(false)
      }
    }

    const syncStartupEnabled = async () => {
      if (!window.api?.getStartupEnabled) return
      try {
        const enabled = await window.api.getStartupEnabled()
        if (!cancelled) {
          setSettings((prev) => ({ ...prev, launchOnStartup: Boolean(enabled) }))
        }
      } catch {
        // ignore sync errors; local preference still works
      }
    }

    void syncStartupSupport()
    void syncStartupEnabled()
    return () => {
      cancelled = true
    }
  }, [])

  const enumerateMediaDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return
    const list = await navigator.mediaDevices.enumerateDevices()
    const cameras = list.filter((d) => d.kind === 'videoinput')
    const microphones = list.filter((d) => d.kind === 'audioinput')
    setDevices({ cameras, microphones })
    setSettings((prev) => ({
      ...prev,
      selectedCameraId: prev.selectedCameraId || cameras[0]?.deviceId || '',
      selectedMicId: prev.selectedMicId || microphones[0]?.deviceId || ''
    }))
  }

  const requestDeviceAccess = async (mode = 'both') => {
    try {
      setMediaError('')
      const constraints =
        mode === 'video'
          ? { video: true, audio: false }
          : mode === 'audio'
            ? { video: false, audio: true }
            : { video: true, audio: true }
      const temp = await navigator.mediaDevices.getUserMedia(constraints)
      temp.getTracks().forEach((track) => track.stop())
      setMediaReady(true)
      await enumerateMediaDevices()
      return true
    } catch (error) {
      const message = error?.message || 'Failed to access camera/microphone.'
      setMediaError(message)
      void notifyUser('Device access failed', message, true)
      return false
    }
  }

  useEffect(() => {
    let mounted = true
    const setup = async () => {
      try {
        if (!navigator.mediaDevices) return
        await enumerateMediaDevices()
        if (mounted && (devices.cameras.length > 0 || devices.microphones.length > 0)) {
          setMediaReady(true)
        }
        navigator.mediaDevices.addEventListener?.('devicechange', enumerateMediaDevices)
      } catch {
        // no-op for initial mount
      }
    }
    setup()
    return () => {
      mounted = false
      navigator.mediaDevices?.removeEventListener?.('devicechange', enumerateMediaDevices)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const videoElement = videoRef.current

    const startCamera = async () => {
      if (tab !== 'live-monitoring' || !settings.selectedCameraId) return
      try {
        setCameraStatus('connecting')
        cameraStreamRef.current?.getTracks().forEach((t) => t.stop())
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { deviceId: { exact: settings.selectedCameraId } },
          audio: false
        })
        cameraStreamRef.current = stream
        if (videoElement) {
          videoElement.srcObject = stream
        }
        setCameraStatus('connected')
      } catch (error) {
        setCameraStatus('error')
        setMediaError(error?.message || 'Camera stream unavailable.')
      }
    }
    startCamera()
    return () => {
      cameraStreamRef.current?.getTracks().forEach((t) => t.stop())
      cameraStreamRef.current = null
      if (videoElement) videoElement.srcObject = null
    }
  }, [tab, settings.selectedCameraId])

  useEffect(() => {
    let audioContext = null
    const startMicLevel = async () => {
      if (tab !== 'live-monitoring' || !settings.selectedMicId) return
      try {
        setMicStatus('connecting')
        micStreamRef.current?.getTracks().forEach((t) => t.stop())
        const stream = await navigator.mediaDevices.getUserMedia({
          video: false,
          audio: { deviceId: { exact: settings.selectedMicId } }
        })
        micStreamRef.current = stream
        const AudioContextClass = window.AudioContext || window.webkitAudioContext
        if (!AudioContextClass) {
          throw new Error('AudioContext is not supported on this device.')
        }
        audioContext = new AudioContextClass()
        const source = audioContext.createMediaStreamSource(stream)
        const analyser = audioContext.createAnalyser()
        analyser.fftSize = 256
        source.connect(analyser)
        const data = new Uint8Array(analyser.frequencyBinCount)

        const tick = () => {
          analyser.getByteFrequencyData(data)
          const sum = data.reduce((acc, value) => acc + value, 0)
          const avg = sum / data.length
          setMicLevel(Math.min(100, Math.round((avg / 255) * 100)))
          micFrameRef.current = requestAnimationFrame(tick)
        }
        tick()
        setMicStatus('connected')
      } catch (error) {
        setMicStatus('error')
        setMediaError(error?.message || 'Microphone stream unavailable.')
      }
    }
    startMicLevel()
    return () => {
      if (micFrameRef.current) cancelAnimationFrame(micFrameRef.current)
      micFrameRef.current = null
      micStreamRef.current?.getTracks().forEach((t) => t.stop())
      micStreamRef.current = null
      if (audioContext) {
        void audioContext.close().catch(() => {})
      }
      setMicLevel(0)
    }
  }, [tab, settings.selectedMicId])

  const showSearch = tab === 'gesture-library' || tab === 'settings'

  const filteredGestures = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return gestures
    return gestures.filter(
      (item) =>
        item.title.toLowerCase().includes(query) ||
        item.subtitle.toLowerCase().includes(query) ||
        (item.phrase && item.phrase.toLowerCase().includes(query)) ||
        (item.family && item.family.toLowerCase().includes(query)) ||
        (item.controlModel && item.controlModel.toLowerCase().includes(query))
    )
  }, [search, gestures])

  const hasSearchQuery = search.trim().length > 0
  const defaultFeatureGestures = filteredGestures.filter((item) => item.locked)
  const customFeatureGestures = filteredGestures.filter((item) => !item.locked)
  const visibleDefaultGestures =
    hasSearchQuery || showAllDefaultGestures
      ? defaultFeatureGestures
      : defaultFeatureGestures.slice(0, DEFAULT_LIBRARY_VISIBLE)
  const canShowMoreDefaults =
    !hasSearchQuery && defaultFeatureGestures.length > visibleDefaultGestures.length
  const canShowLessDefaults =
    !hasSearchQuery &&
    showAllDefaultGestures &&
    defaultFeatureGestures.length > DEFAULT_LIBRARY_VISIBLE

  const trainingStageMeta = useMemo(() => {
    if (!trainingSession) return null
    if (trainingSession.progress >= 100) {
      return { label: 'Saved', detail: 'Profile ready' }
    }
    if (trainingSession.progress < 35) {
      return { label: 'Capture', detail: 'Collecting samples' }
    }
    if (trainingSession.progress < 65) {
      return { label: 'Quality Check', detail: 'Validating consistency' }
    }
    if (trainingSession.progress < 95) {
      return { label: 'Model Training', detail: 'Building recognition profile' }
    }
    return { label: 'Finalizing', detail: 'Preparing command mapping' }
  }, [trainingSession])

  useEffect(() => {
    if (!window.api?.onTrainingProgress) return
    const unsubscribe = window.api.onTrainingProgress((payload = {}) => {
      setTrainingSession((prev) => {
        if (!prev) return prev
        if (payload.cancelled) return null
        if (payload.sessionId && prev.sessionId && payload.sessionId !== prev.sessionId) {
          return prev
        }
        if (payload.gestureId && payload.gestureId !== prev.gestureId) {
          return prev
        }

        const nextProgress = Math.max(0, Math.min(100, Number(payload.progress) || 0))
        return {
          ...prev,
          sessionId: payload.sessionId || prev.sessionId || null,
          source: 'engine',
          progress: nextProgress,
          cueIndex: getCueIndexFromProgress(prev.type, nextProgress)
        }
      })
    })

    return () => {
      if (typeof unsubscribe === 'function') {
        unsubscribe()
      }
    }
  }, [])

  useEffect(() => {
    if (!trainingSession || trainingSession.progress >= 100) return
    if (trainingSession.source !== 'ui-fallback') return
    const timer = setTimeout(() => {
      setTrainingSession((prev) => {
        if (!prev || prev.progress >= 100 || prev.source !== 'ui-fallback') return prev
        const step = prev.type === 'voice' ? 9 : 7
        const nextProgress = Math.min(100, prev.progress + step)
        return {
          ...prev,
          progress: nextProgress,
          cueIndex: getCueIndexFromProgress(prev.type, nextProgress)
        }
      })
    }, 280)

    return () => clearTimeout(timer)
  }, [trainingSession])

  const settingsQuery = search.trim().toLowerCase()
  const matchesSettingsSection = (terms) => {
    if (!settingsQuery) return true
    const tokens = settingsQuery.split(/\s+/).filter(Boolean)
    return tokens.every((token) => terms.some((term) => term.includes(token)))
  }
  const showDeviceSettings = matchesSettingsSection([
    'camera',
    'microphone',
    'device',
    'webcam',
    'audio',
    'video',
    'permissions'
  ])
  const showRuntimeSettings = matchesSettingsSection([
    'sensitivity',
    'cooldown',
    'startup',
    'notifications',
    'runtime'
  ])
  const showBehaviorSettings = matchesSettingsSection([
    'delete',
    'confirm',
    'monitoring',
    'add gesture',
    'flow',
    'dark mode',
    'theme'
  ])

  const systemStatus = useMemo(() => {
    if (mediaError) return { label: 'System Error', tone: 'error' }
    if (tab === 'live-monitoring') {
      if (cameraStatus === 'connecting' || micStatus === 'connecting') {
        return { label: 'Starting...', tone: 'starting' }
      }
      if (cameraStatus === 'connected' || micStatus === 'connected') {
        return { label: 'System Active', tone: 'active' }
      }
    }
    return { label: 'System Idle', tone: 'idle' }
  }, [cameraStatus, mediaError, micStatus, tab])

  const handleEditSave = () => {
    if (!editingGesture) return
    if (editingGesture.locked) {
      setEditingGesture(null)
      return
    }
    const title = editingGesture.title.trim()
    const subtitle = editingGesture.subtitle.trim()
    if (!title || !subtitle) return
    setGestures((prev) =>
      prev.map((item) => (item.id === editingGesture.id ? { ...item, title, subtitle } : item))
    )
    void notifyUser('Gesture updated', `${title} mapping has been saved.`)
    setEditingGesture(null)
  }

  const handleDeleteConfirmed = (id) => {
    const removed = gestures.find((item) => item.id === id)
    if (removed?.locked) {
      setPendingDeleteGesture(null)
      return
    }
    setGestures((prev) => prev.filter((item) => item.id !== id))
    if (selectedGesture?.id === id) setSelectedGesture(null)
    setPendingDeleteGesture(null)
    if (removed) {
      void notifyUser('Gesture deleted', `${removed.title} was removed.`)
    }
  }

  const handleToggleDefaultGesture = (id) => {
    setGestures((prev) =>
      prev.map((item) =>
        item.id === id && item.locked ? { ...item, enabled: item.enabled === false } : item
      )
    )
  }

  const createGesture = (preset) => {
    if (!preset) return null
    const id = `${preset.id}-${Date.now()}`
    const created = {
      id,
      title: preset.templateTitle || 'New Gesture',
      subtitle: preset.templateSubtitle || 'Custom gesture mapping',
      type: preset.type || 'hand',
      controlModel: preset.controlModel || 'static',
      family: preset.family || 'Custom Feature',
      enabled: true,
      locked: false,
      ...(preset.type === 'voice' ? { phrase: preset.phrase || 'Your custom phrase' } : {})
    }
    setGestures((prev) => [created, ...prev])
    void notifyUser('Gesture added', `${created.title} is ready to configure.`)
    return created
  }

  const startTrainingSession = async (gesture, returnTab = null) => {
    if (!gesture) return
    setTrainingSession({
      gestureId: gesture.id,
      type: gesture.type,
      progress: 0,
      cueIndex: 0,
      sessionId: null,
      source: 'pending',
      returnTab
    })

    if (!window.api?.startTraining) {
      setTrainingSession((prev) => (prev ? { ...prev, source: 'ui-fallback' } : prev))
      return
    }

    try {
      const result = await window.api.startTraining({
        gestureId: gesture.id,
        type: gesture.type
      })
      if (result?.ok) {
        setTrainingSession((prev) =>
          prev && prev.gestureId === gesture.id
            ? { ...prev, sessionId: result.sessionId || null, source: 'engine' }
            : prev
        )
        return
      }
    } catch {
      // fall through to ui fallback mode
    }

    setTrainingSession((prev) => (prev ? { ...prev, source: 'ui-fallback' } : prev))
  }

  const handleAddGestureType = (preset) => {
    setPendingGesturePreset(preset)
    setShowAddTypePopup(false)
    setShowPermissionPopup(true)
  }

  const handleConfirmGestureCreation = async () => {
    if (!pendingGesturePreset) return
    const preset = pendingGesturePreset
    const type = preset.type
    const granted = await requestDeviceAccess(type === 'voice' ? 'both' : 'video')
    if (!granted) {
      setShowPermissionPopup(false)
      setPendingGesturePreset(null)
      return
    }
    const returnTab = settings.openMonitoringAfterAdd ? null : tab
    const created = createGesture(preset)
    setTab('live-monitoring')
    await startTrainingSession(created, returnTab)
    setShowPermissionPopup(false)
    setPendingGesturePreset(null)
  }

  const finishTrainingSession = () => {
    const nextTab = trainingSession?.returnTab || null
    setTrainingSession(null)
    if (nextTab) {
      setTab(nextTab)
    }
  }

  const stopTrainingSession = async () => {
    const currentSession = trainingSession
    if (!currentSession) return
    if (currentSession.progress < 100 && window.api?.cancelTraining) {
      try {
        await window.api.cancelTraining()
      } catch {
        // ignore cancellation errors and close local state anyway
      }
    }
    setTrainingSession(null)
    if (currentSession.returnTab) {
      setTab(currentSession.returnTab)
    }
  }

  const handleLaunchOnStartupToggle = async (checked) => {
    setSettings((prev) => ({ ...prev, launchOnStartup: checked }))
    if (!window.api?.setStartupEnabled) return
    try {
      const result = await window.api.setStartupEnabled(checked)
      if (!result?.ok) {
        setSettings((prev) => ({ ...prev, launchOnStartup: false }))
        void notifyUser(
          'Startup setting unavailable',
          'Launch on startup is not supported on this platform.',
          true
        )
        return
      }
      setSettings((prev) => ({ ...prev, launchOnStartup: Boolean(result.enabled) }))
      void notifyUser(
        'Startup setting updated',
        result.enabled
          ? 'Octave will launch when your system starts.'
          : 'Octave will not auto-launch at startup.'
      )
    } catch {
      setSettings((prev) => ({ ...prev, launchOnStartup: false }))
      void notifyUser('Startup update failed', 'Could not update launch on startup.', true)
    }
  }

  const renderGestureDemo = (gesture) => {
    if (!gesture) return null
    const sceneMap = {
      'dyn-magnitude-control': 'magnitude-control',
      'dyn-cursor-control': 'cursor-control',
      'dyn-grab-drag': 'grab-drag',
      'dyn-navigation-control': 'navigation-control',
      'dyn-rotation-dial': 'rotation-dial',
      'dyn-scroll-control': 'scroll-control',
      'st-fist-play-pause': 'fist-play-pause',
      'st-thumbs-up-mute': 'thumbs-up-mute',
      'st-v-sign-next-prev': 'v-sign-next-prev',
      'st-ok-sign-confirm': 'ok-sign-confirm',
      'st-mode-switch-cycle': 'mode-switch-cycle',
      'st-drs-frame-power': 'third-umpire-review'
    }

    const captionMap = {
      'dyn-magnitude-control': 'Open palm up/down for continuous increase/decrease.',
      'dyn-cursor-control': 'Index finger pointing controls cursor movement.',
      'dyn-grab-drag': 'Pinch-hold to grab, move to drag, release to drop.',
      'dyn-navigation-control': 'Index left/right motion for back and forward.',
      'dyn-rotation-dial': 'Rotate wrist clockwise or anticlockwise like a dial.',
      'dyn-scroll-control': 'Two-finger up/down for continuous scroll.',
      'st-fist-play-pause': 'Closed fist triggers a one-time play/pause.',
      'st-thumbs-up-mute': 'Thumbs up toggles mute/unmute.',
      'st-v-sign-next-prev': 'V sign runs next/previous command.',
      'st-ok-sign-confirm': 'OK sign confirms current selection.',
      'st-mode-switch-cycle': 'Hold three-finger gesture to cycle active mode.',
      'st-drs-frame-power': 'Review-frame gesture triggers the power command.'
    }

    const scene =
      sceneMap[gesture.id] || (gesture.type === 'voice' ? 'voice-next-window' : 'magnitude-control')

    const renderHand = (variant = 'open') => (
      <div className={`guide-hand ${variant}`}>
        <span className="palm" />
        <span className="finger f1" />
        <span className="finger f2" />
        <span className="finger f3" />
        <span className="finger f4" />
        <span className="finger f5" />
      </div>
    )

    if (scene === 'voice-next-window' || scene === 'voice-prev-window') {
      return (
        <div className={`guide-scene scene-${scene}`} aria-hidden>
          <div className="guide-stage guide-stage-voice">
            <div className="guide-voice-mic">
              <span className="mic-core" />
              <span className="mic-ring" />
              <span className="mic-ring ring-2" />
            </div>
            <div className="guide-voice-wave">
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>
            <div className="voice-window-stack">
              <span className="window-a" />
              <span className="window-b" />
            </div>
            <span
              className={`guide-arrow ${scene === 'voice-next-window' ? 'arrow-right' : 'arrow-left'}`}
            />
          </div>
          <small className="guide-caption">
            {captionMap[gesture.id] || 'Voice command pattern.'}
          </small>
        </div>
      )
    }

    if (scene === 'third-umpire-review') {
      return (
        <div className={`guide-scene scene-${scene}`} aria-hidden>
          <div className="guide-stage guide-stage-third-umpire">
            <div className="review-hands">
              {renderHand('open')}
              <span className="review-bar" />
              {renderHand('right-open')}
            </div>
            <span className="review-pulse" />
            <span className="review-text">REVIEW</span>
          </div>
          <small className="guide-caption">{captionMap[gesture.id] || 'Review signal hold.'}</small>
        </div>
      )
    }

    const handVariant =
      scene === 'scroll-control'
        ? 'two-finger'
        : scene === 'cursor-control' || scene === 'navigation-control'
          ? 'index-point'
          : scene === 'grab-drag'
            ? 'pinch-grab'
            : scene === 'rotation-dial'
              ? 'curved'
              : scene === 'mode-switch-cycle'
                ? 'three-finger'
                : scene === 'fist-play-pause'
                  ? 'fist'
                  : scene === 'thumbs-up-mute'
                    ? 'thumbs-up'
                    : scene === 'v-sign-next-prev'
                      ? 'two-finger'
                      : scene === 'ok-sign-confirm'
                        ? 'ok-sign'
                        : 'open'

    const withTabs = scene === 'navigation-control'
    const withModePanels = scene === 'mode-switch-cycle'

    return (
      <div className={`guide-scene scene-${scene}`} aria-hidden>
        <div className="guide-stage">
          {withTabs ? (
            <div className="guide-context-tabs">
              <span className="tab one" />
              <span className="tab two" />
              <span className="tab three" />
            </div>
          ) : null}
          {withModePanels ? (
            <div className="guide-context-modes">
              <span className="mode-chip one">Vol</span>
              <span className="mode-chip two">Bri</span>
              <span className="mode-chip three">Zoom</span>
              <span className="mode-chip four">Scroll</span>
              <span className="mode-chip five">Cursor</span>
            </div>
          ) : null}
          {scene === 'cursor-control' ? <span className="guide-cursor-dot" /> : null}
          {scene === 'grab-drag' ? <span className="guide-drag-block" /> : null}
          {scene === 'rotation-dial' ? <span className="guide-dial" /> : null}
          {scene === 'fist-play-pause' ? <span className="guide-badge">Play / Pause</span> : null}
          {scene === 'thumbs-up-mute' ? <span className="guide-badge">Mute Toggle</span> : null}
          {scene === 'ok-sign-confirm' ? <span className="guide-badge">Confirm</span> : null}
          {renderHand(handVariant)}
          <span className="guide-arrow arrow-left" />
          <span className="guide-arrow arrow-right" />
          <span className="guide-arrow arrow-up" />
          <span className="guide-arrow arrow-down" />
          <span className="guide-hold-ring" />
        </div>
        <small className="guide-caption">
          {captionMap[gesture.id] || 'Gesture motion pattern.'}
        </small>
      </div>
    )
  }

  const activeTrainingGesture = useMemo(() => {
    if (!trainingSession) return null
    return gestures.find((gesture) => gesture.id === trainingSession.gestureId) || null
  }, [gestures, trainingSession])

  const activeTrainingCue =
    trainingSession?.type === 'voice'
      ? VOICE_TRAINING_CUES[trainingSession.cueIndex] || VOICE_TRAINING_CUES[0]
      : HAND_TRAINING_CUES[trainingSession?.cueIndex] || HAND_TRAINING_CUES[0]
  const trainingCueList =
    trainingSession?.type === 'voice' ? VOICE_TRAINING_CUES : HAND_TRAINING_CUES
  const currentTrainingStep = trainingSession
    ? Math.min(trainingCueList.length, Math.max(1, trainingSession.cueIndex + 1))
    : 0

  const renderGestureCard = (item) => (
    <article
      key={item.id}
      className={`gesture-card ${item.locked ? 'gesture-card--locked' : ''} ${item.enabled === false ? 'gesture-card--disabled' : ''}`}
      onClick={() => {
        const selectedText = window.getSelection?.()?.toString().trim() || ''
        if (selectedText) return
        setSelectedGesture(item)
      }}
    >
      <div>
        <div className="gesture-card-tags">
          <span className={`gesture-type-tag ${item.type === 'voice' ? 'voice' : 'hand'}`}>
            {item.type === 'voice' ? 'Voice' : 'Hand'}
          </span>
          {item.controlModel ? (
            <span className={`gesture-control-tag ${item.controlModel}`}>
              {item.controlModel === 'dynamic' ? 'Dynamic' : 'Static'}
            </span>
          ) : null}
          {item.locked ? <span className="gesture-lock-tag">Default</span> : null}
        </div>
        <h3>{item.title}</h3>
        <p>{item.subtitle}</p>
        {item.family ? <small className="gesture-family">{item.family}</small> : null}
        {item.type === 'voice' && item.phrase ? (
          <small className="gesture-phrase">Trigger: &ldquo;{item.phrase}&rdquo;</small>
        ) : null}
      </div>
      {item.locked ? (
        <div className="gesture-default-controls">
          <span className={`feature-state ${item.enabled === false ? 'off' : 'on'}`}>
            {item.enabled === false ? 'Disabled' : 'Enabled'}
          </span>
          <button
            className={`feature-toggle-btn ${item.enabled === false ? 'off' : ''}`}
            type="button"
            aria-label={`${item.enabled === false ? 'Enable' : 'Disable'} ${item.title}`}
            onClick={(event) => {
              event.stopPropagation()
              handleToggleDefaultGesture(item.id)
            }}
          >
            {item.enabled === false ? 'Enable' : 'Disable'}
          </button>
        </div>
      ) : (
        <div className="gesture-actions">
          <button
            className="icon-action"
            type="button"
            aria-label={`Edit ${item.title}`}
            onClick={(event) => {
              event.stopPropagation()
              setEditingGesture(item)
            }}
          >
            <EditIcon />
          </button>
          <button
            className="icon-action danger"
            type="button"
            aria-label={`Delete ${item.title}`}
            onClick={(event) => {
              event.stopPropagation()
              if (settings.confirmBeforeDelete) {
                setPendingDeleteGesture(item)
              } else {
                handleDeleteConfirmed(item.id)
              }
            }}
          >
            <DeleteIcon />
          </button>
        </div>
      )}
    </article>
  )

  const isEditableTarget = (target) => {
    if (!(target instanceof HTMLElement)) return false
    const tag = target.tagName
    return tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable
  }

  const handleCopyGuard = (event) => {
    if (isEditableTarget(event.target)) return
    event.preventDefault()
  }

  const handleKeyDownGuard = (event) => {
    if (!(event.ctrlKey || event.metaKey)) return
    if (event.key.toLowerCase() !== 'c') return
    if (isEditableTarget(event.target)) return
    event.preventDefault()
  }

  return (
    <main className="app-shell" onCopy={handleCopyGuard} onKeyDown={handleKeyDownGuard}>
      <aside className="sidebar">
        <div>
          <div className="brand">
            <span className="brand-logo" aria-hidden>
              <BrandLogo />
            </span>
            <h1>Octave</h1>
          </div>
          <nav className="nav-list">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`nav-item ${tab === item.id ? 'active' : ''}`}
                onClick={() => {
                  setTab(item.id)
                  setSearch('')
                }}
              >
                <SidebarIcon tabId={item.id} />
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="sidebar-foot">
          <span className={`status-dot status-dot--${systemStatus.tone}`} />
          <span>{systemStatus.label}</span>
        </div>
      </aside>

      <section className="workspace">
        <header className="workspace-head">
          <h2>
            {
              [...TABS, { id: 'live-monitoring', label: 'Live Monitoring' }].find(
                (item) => item.id === tab
              )?.label
            }
          </h2>

          <div className="head-actions">
            <button
              className="theme-toggle"
              type="button"
              onClick={() => setDarkMode((prev) => !prev)}
              aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
              title={darkMode ? 'Light mode' : 'Dark mode'}
            >
              {darkMode ? <SunIcon /> : <MoonIcon />}
            </button>
            {showSearch ? (
              <label className="search-box">
                <SearchIcon />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={tab === 'settings' ? 'Search settings' : 'Search gestures'}
                />
              </label>
            ) : null}
            {tab === 'gesture-library' ? (
              <>
                <button
                  className="secondary-btn"
                  type="button"
                  onClick={() => setShowResetConfirm(true)}
                >
                  Reset Defaults
                </button>
                <button
                  className="primary-btn"
                  type="button"
                  onClick={() => setShowAddTypePopup(true)}
                >
                  New Gesture
                </button>
              </>
            ) : null}
            {tab === 'live-monitoring' ? (
              <button
                className="secondary-btn"
                type="button"
                onClick={() => {
                  if (trainingSession) {
                    void stopTrainingSession()
                    return
                  }
                  setTab('gesture-library')
                }}
              >
                Close Monitoring
              </button>
            ) : null}
          </div>
        </header>

        <div className="workspace-body">
          {tab === 'gesture-library' ? (
            <>
              <section className="gesture-section">
                <header className="gesture-section-head">
                  <h3>Default Features</h3>
                  <span>{defaultFeatureGestures.length}</span>
                </header>
                {visibleDefaultGestures.length > 0 ? (
                  <div className="gesture-grid">
                    {visibleDefaultGestures.map((item) => renderGestureCard(item))}
                  </div>
                ) : (
                  <div className="empty-state-card">No default features match this search.</div>
                )}
                {canShowMoreDefaults ? (
                  <button
                    className="secondary-btn show-more-btn"
                    type="button"
                    onClick={() => setShowAllDefaultGestures(true)}
                  >
                    Show More Default Features
                  </button>
                ) : null}
                {canShowLessDefaults ? (
                  <button
                    className="secondary-btn show-more-btn"
                    type="button"
                    onClick={() => setShowAllDefaultGestures(false)}
                  >
                    Show Less
                  </button>
                ) : null}
              </section>

              <section className="gesture-section">
                <header className="gesture-section-head">
                  <h3>Custom Features</h3>
                  <span>{customFeatureGestures.length}</span>
                </header>
                {customFeatureGestures.length > 0 ? (
                  <div className="gesture-grid">
                    {customFeatureGestures.map((item) => renderGestureCard(item))}
                  </div>
                ) : (
                  <div className="empty-state-card">
                    No custom features yet. Use <strong>New Gesture</strong> to add one.
                  </div>
                )}
              </section>
            </>
          ) : null}

          {tab === 'live-monitoring' ? (
            <div className="monitor-grid">
              <section className="placeholder-panel">
                <h3>Camera Input</h3>
                <p>Status: {cameraStatus}</p>
                <div className="preview-video-wrap">
                  <video ref={videoRef} className="preview-video" autoPlay muted playsInline />
                  {trainingSession ? (
                    <div
                      className={`training-focus-frame ${trainingSession.type === 'voice' ? 'voice' : 'hand'}`}
                      aria-hidden
                    >
                      <span className="focus-corner tl" />
                      <span className="focus-corner tr" />
                      <span className="focus-corner bl" />
                      <span className="focus-corner br" />
                      <span className="focus-center-dot" />
                      <span className="focus-hint">
                        {trainingSession.type === 'voice'
                          ? 'Speak clearly while keeping your face in frame'
                          : 'Keep your hand inside this guide area'}
                      </span>
                    </div>
                  ) : null}
                </div>
                {trainingSession ? (
                  <div className="training-video-overlay">
                    <div className="training-video-topline">
                      <span className="training-stage-chip">{trainingStageMeta?.label}</span>
                      <span className="training-step-chip">
                        Step {currentTrainingStep}/{trainingCueList.length}
                      </span>
                    </div>
                    <div className="training-video-head">
                      <strong>{activeTrainingGesture?.title || 'Training Gesture'}</strong>
                      <span>{trainingSession.progress}%</span>
                    </div>
                    <div className="training-progress training-progress--overlay">
                      <div style={{ width: `${trainingSession.progress}%` }} />
                    </div>
                    <p className="training-video-stage">{trainingStageMeta?.detail}</p>
                    <p className="training-video-cue">{activeTrainingCue}</p>
                    <ul className="training-cue-list">
                      {trainingCueList.map((cue, index) => (
                        <li
                          key={`${trainingSession.type}-${index}`}
                          className={
                            index < trainingSession.cueIndex
                              ? 'done'
                              : index === trainingSession.cueIndex
                                ? 'current'
                                : ''
                          }
                        >
                          <span className="cue-index">{index + 1}</span>
                          <span>{cue}</span>
                        </li>
                      ))}
                    </ul>
                    {trainingSession.source === 'pending' ? (
                      <p className="training-video-status">Connecting to training engine...</p>
                    ) : null}
                    {trainingSession.type === 'voice' ? (
                      <p className="training-video-phrase">
                        Phrase: &ldquo;{activeTrainingGesture?.phrase || 'Your custom phrase'}
                        &rdquo;
                      </p>
                    ) : null}
                    <div className="training-video-actions">
                      {trainingSession.progress >= 100 ? (
                        <button
                          className="primary-btn training-overlay-btn"
                          type="button"
                          onClick={finishTrainingSession}
                        >
                          Finish
                        </button>
                      ) : (
                        <button
                          className="modal-cancel training-overlay-btn"
                          type="button"
                          onClick={() => {
                            void stopTrainingSession()
                          }}
                        >
                          Stop
                        </button>
                      )}
                    </div>
                  </div>
                ) : null}
              </section>
              <section className="placeholder-panel">
                <h3>Microphone Input</h3>
                <p>Status: {micStatus}</p>
                <div className="meter-wrap">
                  <div className="meter-fill" style={{ width: `${micLevel}%` }} />
                </div>
                <p>Input Level: {micLevel}%</p>
              </section>
              {!mediaReady || mediaError ? (
                <section className="placeholder-panel monitor-alert">
                  <h3>Device Access</h3>
                  <p>
                    {mediaError || 'Camera and microphone access required for live monitoring.'}
                  </p>
                  <button
                    className="primary-btn"
                    type="button"
                    onClick={() => requestDeviceAccess('both')}
                  >
                    Enable Camera & Microphone
                  </button>
                </section>
              ) : null}
            </div>
          ) : null}

          {tab === 'settings' ? (
            <div className="settings-stack">
              {showDeviceSettings ? (
                <section className="settings-form-card">
                  <h3>Device Selection</h3>
                  <div className="form-grid">
                    <label className="form-field">
                      <span>Camera</span>
                      <select
                        value={settings.selectedCameraId}
                        onChange={(event) =>
                          setSettings((prev) => ({
                            ...prev,
                            selectedCameraId: event.target.value
                          }))
                        }
                      >
                        {devices.cameras.map((device, idx) => (
                          <option key={device.deviceId || `camera-${idx}`} value={device.deviceId}>
                            {device.label || `Camera ${idx + 1}`}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="form-field">
                      <span>Microphone</span>
                      <select
                        value={settings.selectedMicId}
                        onChange={(event) =>
                          setSettings((prev) => ({
                            ...prev,
                            selectedMicId: event.target.value
                          }))
                        }
                      >
                        {devices.microphones.map((device, idx) => (
                          <option key={device.deviceId || `mic-${idx}`} value={device.deviceId}>
                            {device.label || `Microphone ${idx + 1}`}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <button
                    className="modal-cancel"
                    type="button"
                    onClick={() => requestDeviceAccess('both')}
                  >
                    Refresh Devices
                  </button>
                </section>
              ) : null}

              {showRuntimeSettings ? (
                <section className="settings-form-card">
                  <h3>Gesture Runtime</h3>
                  <div className="form-grid">
                    <label className="form-field">
                      <span>Gesture Sensitivity ({settings.gestureSensitivity}%)</span>
                      <input
                        type="range"
                        min="10"
                        max="100"
                        value={settings.gestureSensitivity}
                        onChange={(event) =>
                          setSettings((prev) => ({
                            ...prev,
                            gestureSensitivity: Number(event.target.value)
                          }))
                        }
                      />
                    </label>
                    <label className="form-field">
                      <span>Action Cooldown (ms)</span>
                      <input
                        type="number"
                        min="100"
                        step="50"
                        value={settings.actionCooldownMs}
                        onChange={(event) =>
                          setSettings((prev) => ({
                            ...prev,
                            actionCooldownMs: Number(event.target.value || 0)
                          }))
                        }
                      />
                    </label>
                  </div>
                  <div className="toggle-row">
                    <label>
                      <input
                        type="checkbox"
                        checked={settings.launchOnStartup}
                        disabled={!startupSupported}
                        onChange={(event) => {
                          void handleLaunchOnStartupToggle(event.target.checked)
                        }}
                      />
                      Launch on Startup {!startupSupported ? '(Unsupported on this platform)' : ''}
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={settings.notifications}
                        onChange={(event) => {
                          const next = event.target.checked
                          setSettings((prev) => ({
                            ...prev,
                            notifications: next
                          }))
                          if (next) {
                            void notifyUser(
                              'Notifications enabled',
                              'You will now receive Octave updates.',
                              true
                            )
                          }
                        }}
                      />
                      Notifications
                    </label>
                  </div>
                </section>
              ) : null}

              {showBehaviorSettings ? (
                <section className="settings-form-card">
                  <h3>App Behavior</h3>
                  <div className="toggle-row">
                    <label>
                      <input
                        type="checkbox"
                        checked={settings.confirmBeforeDelete}
                        onChange={(event) =>
                          setSettings((prev) => ({
                            ...prev,
                            confirmBeforeDelete: event.target.checked
                          }))
                        }
                      />
                      Confirm before deleting gestures
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={settings.openMonitoringAfterAdd}
                        onChange={(event) =>
                          setSettings((prev) => ({
                            ...prev,
                            openMonitoringAfterAdd: event.target.checked
                          }))
                        }
                      />
                      Keep Live Monitoring open after training starts
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={darkMode}
                        onChange={(event) => setDarkMode(event.target.checked)}
                      />
                      Dark mode
                    </label>
                  </div>
                </section>
              ) : null}

              {!showDeviceSettings && !showRuntimeSettings && !showBehaviorSettings ? (
                <section className="settings-form-card">
                  <h3>No Matching Settings</h3>
                  <p>
                    Try searching for camera, microphone, sensitivity, cooldown, delete, monitoring,
                    or theme.
                  </p>
                </section>
              ) : null}
            </div>
          ) : null}
        </div>
      </section>

      {showAddTypePopup ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setShowAddTypePopup(false)}
        >
          <section
            className="modal-card modal-card-wide"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Add Gesture</h3>
            <p className="add-intro">
              Choose what you want to control. Octave will create a starter gesture that you can
              edit later.
            </p>
            <div className="add-guide">
              <h4>What happens next</h4>
              <p>1) Pick a template 2) Allow camera/microphone access 3) Quick training starts.</p>
              <small>You can rename, remap, or delete it anytime.</small>
            </div>
            <div className="add-sections">
              {ADD_GESTURE_SECTIONS.map((section) => (
                <div key={section.id} className="add-section">
                  <h4>{section.label}</h4>
                  <p className="add-section-help">{section.help}</p>
                  <div className="type-grid">
                    {section.items.map((item) => (
                      <button
                        key={item.id}
                        className="type-card"
                        type="button"
                        onClick={() => handleAddGestureType(item)}
                      >
                        <strong>{item.title}</strong>
                        <small>{item.subtitle}</small>
                        <p className="type-card-user-view">{item.fromUserView}</p>
                        <span className="type-card-example">Example: {item.example}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <button
              className="modal-cancel"
              type="button"
              onClick={() => setShowAddTypePopup(false)}
            >
              Cancel
            </button>
          </section>
        </div>
      ) : null}

      {showPermissionPopup ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => {
            setShowPermissionPopup(false)
            setPendingGesturePreset(null)
          }}
        >
          <section
            className="modal-card modal-card-compact"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Allow Device Access</h3>
            <p>
              Octave needs{' '}
              {pendingGesturePreset?.type === 'voice' ? 'camera and microphone' : 'camera'} access
              to start {pendingGesturePreset?.type === 'voice' ? 'voice' : 'hand'} gesture setup in
              Live Monitoring.
            </p>
            <div className="modal-actions">
              <button
                className="modal-cancel"
                type="button"
                onClick={() => {
                  setShowPermissionPopup(false)
                  setPendingGesturePreset(null)
                }}
              >
                Not now
              </button>
              <button className="primary-btn" type="button" onClick={handleConfirmGestureCreation}>
                Allow & Continue
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {selectedGesture ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setSelectedGesture(null)}
        >
          <section
            className="modal-card"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>{selectedGesture.title}</h3>
            <p>{selectedGesture.subtitle}</p>
            {selectedGesture.locked ? (
              <>
                <div className="guide-demo-panel">{renderGestureDemo(selectedGesture)}</div>
                {selectedGesture.type === 'voice' && selectedGesture.phrase ? (
                  <p className="guide-phrase">
                    Voice trigger: &ldquo;{selectedGesture.phrase}&rdquo;
                  </p>
                ) : null}
                <ul className="guide-howto">
                  {(selectedGesture.howTo || []).map((step, index) => (
                    <li key={`${selectedGesture.id}-step-${index}`}>{step}</li>
                  ))}
                </ul>
                <ul className="guide-meta-list">
                  {selectedGesture.family ? (
                    <li>
                      <strong>Family:</strong> {selectedGesture.family}
                    </li>
                  ) : null}
                  {selectedGesture.controlModel ? (
                    <li>
                      <strong>Control Type:</strong>{' '}
                      {selectedGesture.controlModel === 'dynamic'
                        ? 'Dynamic (Continuous)'
                        : 'Static (One-Time)'}
                    </li>
                  ) : null}
                  {selectedGesture.dynamicTargets?.length ? (
                    <li>
                      <strong>Targets:</strong> {selectedGesture.dynamicTargets.join(', ')}
                    </li>
                  ) : null}
                  {selectedGesture.modeCycle?.length ? (
                    <li>
                      <strong>Mode Cycle:</strong> {selectedGesture.modeCycle.join(' -> ')}
                    </li>
                  ) : null}
                  {selectedGesture.defaultAction ? (
                    <li>
                      <strong>Default Action:</strong> {selectedGesture.defaultAction}
                    </li>
                  ) : null}
                </ul>
                <p className="guide-readonly-note">
                  Default actions are locked. Create a custom gesture if you want to modify
                  behavior.
                </p>
                <p className="guide-readonly-note">
                  Current state:{' '}
                  <strong>{selectedGesture.enabled === false ? 'Disabled' : 'Enabled'}</strong>
                </p>
              </>
            ) : (
              <ul className="sample-meta">
                <li>Sample confidence: 91%</li>
                <li>Mapped action: {selectedGesture.subtitle}</li>
                <li>Last trained: not set</li>
              </ul>
            )}
            <button className="modal-cancel" type="button" onClick={() => setSelectedGesture(null)}>
              Close
            </button>
          </section>
        </div>
      ) : null}

      {editingGesture ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setEditingGesture(null)}>
          <section
            className="modal-card"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Edit Gesture</h3>
            <label className="form-field">
              <span>Name</span>
              <input
                value={editingGesture.title}
                onChange={(event) =>
                  setEditingGesture((prev) =>
                    prev ? { ...prev, title: event.target.value } : prev
                  )
                }
              />
            </label>
            <label className="form-field">
              <span>Action</span>
              <input
                value={editingGesture.subtitle}
                onChange={(event) =>
                  setEditingGesture((prev) =>
                    prev ? { ...prev, subtitle: event.target.value } : prev
                  )
                }
              />
            </label>
            <div className="modal-actions">
              <button
                className="modal-cancel"
                type="button"
                onClick={() => setEditingGesture(null)}
              >
                Cancel
              </button>
              <button className="primary-btn" type="button" onClick={handleEditSave}>
                Save
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {pendingDeleteGesture ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setPendingDeleteGesture(null)}
        >
          <section
            className="modal-card modal-card-compact"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Delete Gesture?</h3>
            <p>
              This will remove <strong>{pendingDeleteGesture.title}</strong>.
            </p>
            <div className="modal-actions">
              <button
                className="modal-cancel"
                type="button"
                onClick={() => setPendingDeleteGesture(null)}
              >
                Cancel
              </button>
              <button
                className="danger-btn"
                type="button"
                onClick={() => handleDeleteConfirmed(pendingDeleteGesture.id)}
              >
                Yes, Delete
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {showResetConfirm ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setShowResetConfirm(false)}
        >
          <section
            className="modal-card modal-card-compact"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Reset Gestures</h3>
            <p>Restore the default gesture set and remove custom edits?</p>
            <div className="modal-actions">
              <button
                className="modal-cancel"
                type="button"
                onClick={() => setShowResetConfirm(false)}
              >
                Cancel
              </button>
              <button
                className="secondary-btn"
                type="button"
                onClick={() => {
                  setGestures(cloneDefaultGestures())
                  setSelectedGesture(null)
                  setEditingGesture(null)
                  setShowResetConfirm(false)
                  void notifyUser('Gestures reset', 'Default gesture set has been restored.')
                }}
              >
                Reset
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  )
}

export default App

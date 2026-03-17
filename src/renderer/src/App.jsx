import { useEffect, useEffectEvent, useMemo, useRef, useState } from 'react'

const TABS = [
  { id: 'gesture-library', label: 'Gesture Library' },
  { id: 'settings', label: 'Settings' }
]

let initialEngineStartRequested = false

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
    engineGestureName: 'Fist',
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
    engineGestureName: 'Thumb',
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
    engineGestureName: 'V Sign',
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
    engineGestureName: 'OK Sign',
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
    engineGestureName: 'Three Fingers',
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
    engineGestureName: 'DRS T-Frame',
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
        phrase: 'Your dynamic command',
        defaultAction: 'Mute/Unmute Audio'
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
        templateSubtitle: 'One-time hand action mapping',
        defaultAction: 'Play/Pause Media'
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
        templateSubtitle: 'Automation trigger mapping',
        defaultAction: 'Launch VS Code'
      }
    ]
  }
]

const AVAILABLE_ACTIONS = [
  {
    group: 'Media',
    actions: [
      'Play/Pause Media',
      'Mute/Unmute Audio',
      'Volume Up',
      'Volume Down',
      'Next Track',
      'Prev Track'
    ]
  },
  {
    group: 'Navigation',
    actions: [
      'Navigate Next/Previous',
      'Switch Tab',
      'Switch Window',
      'Scroll Up',
      'Scroll Down',
      'Go Back',
      'Go Forward'
    ]
  },
  {
    group: 'System',
    actions: [
      'Confirm / Enter',
      'Escape',
      'Screenshot',
      'Lock Screen',
      'Launch VS Code',
      'Launch Browser'
    ]
  },
  {
    group: 'Mouse',
    actions: ['Click', 'Double Click', 'Right Click', 'Middle Click']
  }
]

const ACTION_OPTIONS = AVAILABLE_ACTIONS.flatMap((group) => group.actions)

const UI_ACTION_TO_ENGINE_ACTION = {
  'Play/Pause Media': 'PlayPause',
  'Mute/Unmute Audio': 'MuteToggle',
  'Volume Up': 'VolumeUp',
  'Volume Down': 'VolumeDown',
  'Next Track': 'NextTrack',
  'Prev Track': 'PrevTrack',
  'Navigate Next/Previous': 'AltRight',
  'Switch Tab': 'SwitchTab',
  'Switch Window': 'SwitchWindow',
  'Scroll Up': 'ScrollUp',
  'Scroll Down': 'ScrollDown',
  'Go Back': 'GoBack',
  'Go Forward': 'AltRight',
  'Confirm / Enter': 'ConfirmEnter',
  Escape: 'Escape',
  Screenshot: 'Screenshot',
  'Lock Screen': 'LockScreen',
  'Launch VS Code': 'OpenVSCode',
  'Launch Browser': 'OpenBrowser',
  Click: 'Click',
  'Double Click': 'DoubleClick',
  'Right Click': 'RightClick',
  'Middle Click': 'MiddleClick'
}

const ENGINE_ACTION_TO_UI_ACTION = {
  PlayPause: 'Play/Pause Media',
  MuteToggle: 'Mute/Unmute Audio',
  VolumeUp: 'Volume Up',
  VolumeDown: 'Volume Down',
  NextTrack: 'Next Track',
  PrevTrack: 'Prev Track',
  AltRight: 'Go Forward',
  SwitchTab: 'Switch Tab',
  SwitchWindow: 'Switch Window',
  ScrollUp: 'Scroll Up',
  ScrollDown: 'Scroll Down',
  GoBack: 'Go Back',
  ConfirmEnter: 'Confirm / Enter',
  Escape: 'Escape',
  Screenshot: 'Screenshot',
  LockScreen: 'Lock Screen',
  OpenVSCode: 'Launch VS Code',
  OpenBrowser: 'Launch Browser',
  Click: 'Click',
  DoubleClick: 'Double Click',
  RightClick: 'Right Click',
  MiddleClick: 'Middle Click'
}

const UNSUPPORTED_CUSTOM_PRESET_IDS = new Set(['custom-dynamic-hand', 'custom-dynamic-voice'])

const DEFAULT_ENGINE_GESTURES = new Set(
  DEFAULT_GESTURES.map((gesture) => gesture.engineGestureName).filter(Boolean)
)

const toEngineAction = (action) => {
  if (action && typeof action === 'object') return action
  const normalized = typeof action === 'string' ? action.trim() : ''
  return UI_ACTION_TO_ENGINE_ACTION[normalized] || normalized || 'Click'
}

const describeEngineAction = (action) => {
  if (typeof action === 'string') {
    return ENGINE_ACTION_TO_UI_ACTION[action] || action || 'Click'
  }
  if (!action || typeof action !== 'object') {
    return 'Click'
  }
  const kind = String(action.type || '').toLowerCase()
  if (kind === 'launch_app') return `Launch ${action.target || 'App'}`
  if (kind === 'hotkey') return `Hotkey: ${(action.keys || []).join(' + ')}`
  if (kind === 'key') return `Key: ${action.key || ''}`.trim()
  if (kind === 'command') return 'Custom Command'
  if (kind === 'url') return 'Open URL'
  if (kind === 'open_path') return 'Open Folder'
  return 'Custom Action'
}

const buildVoiceGestureTitle = (phrase) =>
  String(phrase || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ') || 'Voice Command'

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
  const [engineStatus, setEngineStatus] = useState({ running: false, phase: 'unknown' })
  const [cameraStatus, setCameraStatus] = useState('idle')
  const [micStatus, setMicStatus] = useState('idle')
  const [micLevel, setMicLevel] = useState(0)
  const [mediaError, setMediaError] = useState('')
  const [hasStartupPermissions, setHasStartupPermissions] = useState(true)
  const [gestureSetupForm, setGestureSetupForm] = useState(null) // { preset, name, action, phrase }
  const videoRef = useRef(null)
  const cameraStreamRef = useRef(null)
  const micStreamRef = useRef(null)
  const micFrameRef = useRef(null)
  const engineStatusRef = useRef(engineStatus)

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

  const notifyFromEffect = useEffectEvent((title, body, force = false) => {
    void notifyUser(title, body, force)
  })

  const isEngineOwningInputs = (status = engineStatusRef.current) => {
    const phase = status?.phase
    return Boolean(status?.running) || ['training', 'restarting', 'active'].includes(phase)
  }

  const stopCameraPreview = () => {
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop())
    cameraStreamRef.current = null
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
  }

  const stopMicPreview = () => {
    if (micFrameRef.current) cancelAnimationFrame(micFrameRef.current)
    micFrameRef.current = null
    micStreamRef.current?.getTracks().forEach((track) => track.stop())
    micStreamRef.current = null
    setMicLevel(0)
  }

  const syncGestureLibraryFromEngine = async () => {
    if (!window.api?.listGestures) return
    try {
      const result = await window.api.listGestures()
      if (!result || result.ok === false) return

      const mapping = result.mapping || {}
      const disabledStatic = new Set(mapping.disabled_static || [])
      const baseGestures = cloneDefaultGestures().map((gesture) =>
        gesture.engineGestureName
          ? { ...gesture, enabled: !disabledStatic.has(gesture.engineGestureName) }
          : gesture
      )

      const customHandGestures = (result.gestures || [])
        .filter((gesture) => !DEFAULT_ENGINE_GESTURES.has(gesture.name))
        .map((gesture) => {
          const engineAction = mapping.static_actions?.[gesture.name] || 'Click'
          const actionLabel = describeEngineAction(engineAction)
          return {
            id: `hand-${gesture.label}`,
            label: gesture.label,
            title: gesture.name,
            subtitle: actionLabel,
            engineGestureName: gesture.name,
            engineAction,
            defaultAction: actionLabel,
            type: 'hand',
            family: 'Custom Static Gesture',
            controlModel: 'static',
            enabled: true,
            locked: false
          }
        })

      const customVoiceGestures = Object.entries(mapping.voice_actions || {}).map(
        ([phrase, engineAction]) => {
          const actionLabel = describeEngineAction(engineAction)
          return {
            id: `voice-${phrase.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
            title: buildVoiceGestureTitle(phrase),
            subtitle: actionLabel,
            engineAction,
            defaultAction: actionLabel,
            phrase,
            type: 'voice',
            family: 'Static Command Voice Family',
            controlModel: 'static',
            enabled: true,
            locked: false
          }
        }
      )

      setGestures([...customVoiceGestures, ...customHandGestures, ...baseGestures])
    } catch (error) {
      console.error('Failed to sync gestures from engine:', error)
    }
  }

  const persistDisabledStaticGestures = async (nextGestures) => {
    if (!window.api?.updateMapping) return
    const disabledStatic = nextGestures
      .filter((gesture) => gesture.locked && gesture.engineGestureName && gesture.enabled === false)
      .map((gesture) => gesture.engineGestureName)
    try {
      await window.api.updateMapping({ disabled_static: disabledStatic })
    } catch (error) {
      console.error('Failed to persist disabled gestures:', error)
    }
  }

  useEffect(() => {
    if (!window.api?.onEngineStatus) return
    const unsubStatus = window.api.onEngineStatus((payload) => {
      console.log('[App] Received engine status update:', payload)
      setEngineStatus((prev) => {
        console.log('[App] updating engineStatus from', prev, 'to', { ...prev, ...payload })
        const next = { ...prev, ...payload }
        engineStatusRef.current = next
        return next
      })
    })

    let unsubError = () => {}
    if (window.api?.onEngineError) {
      unsubError = window.api.onEngineError((payload) => {
        console.error('[App] Engine error received:', payload)
        const errorMsg =
          payload?.error || payload?.traceback || payload?.stage || 'Unknown engine error'
        setEngineStatus((prev) => ({ ...prev, running: false, phase: 'error' }))
        notifyFromEffect('Engine Error', errorMsg, true)
      })
    }

    // Fetch initial status if available
    if (window.api.getEngineStatus) {
      window.api
        .getEngineStatus()
        .then((status) => {
          if (status) {
            setEngineStatus((prev) => {
              const next = { ...prev, ...status }
              engineStatusRef.current = next
              return next
            })
          }
        })
        .catch(() => {
          // failed to get initial status
        })
    }

    return () => {
      unsubStatus()
      unsubError()
    }
  }, [])

  // ... (keeping other effects unchanged)

  useEffect(() => {
    // Startup: start engine immediately. Electron handles permissions natively.
    // Device enumeration is handled by the dedicated setup effect below — do NOT
    // call enumerateMediaDevices() here too or it fires twice, triggering two
    // selectedCameraId updates and two camera stream restarts.
    if (initialEngineStartRequested) return
    initialEngineStartRequested = true

    const startAppEngine = async () => {
      setHasStartupPermissions(true)

      if (!window.api?.startEngine) {
        console.error('[App] window.api.startEngine is missing')
        return
      }

      setEngineStatus((prev) => ({ ...prev, phase: 'starting' }))
      try {
        const result = await window.api.startEngine()
        if (result && result.ok === false) {
          const err = result.error || 'Failed to start engine'
          console.error('[App] Engine start failed:', err)
          setEngineStatus((prev) => ({ ...prev, running: false, phase: 'error' }))
        }
      } catch (engineErr) {
        console.error('[App] Engine start exception:', engineErr)
        setEngineStatus((prev) => ({ ...prev, running: false, phase: 'error' }))
      }
    }
    void startAppEngine()
  }, [])

  useEffect(() => {
    void syncGestureLibraryFromEngine()
  }, [])

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
    if (!navigator.mediaDevices?.enumerateDevices) return { cameras: [], microphones: [] }
    const list = await navigator.mediaDevices.enumerateDevices()
    const cameras = list.filter((d) => d.kind === 'videoinput')
    const microphones = list.filter((d) => d.kind === 'audioinput')
    setDevices({ cameras, microphones })
    setMediaReady(cameras.length > 0 || microphones.length > 0)
    setSettings((prev) => ({
      ...prev,
      selectedCameraId: prev.selectedCameraId || cameras[0]?.deviceId || '',
      selectedMicId: prev.selectedMicId || microphones[0]?.deviceId || ''
    }))
    return { cameras, microphones }
  }

  const requestDeviceAccess = async (mode = 'both') => {
    const shouldRestartEngine =
      isEngineOwningInputs() && engineStatusRef.current?.phase !== 'training'
    try {
      setMediaError('')
      if (engineStatusRef.current?.phase === 'training') {
        throw new Error('Wait for training to finish before refreshing devices.')
      }
      if (shouldRestartEngine && window.api?.stopEngine) {
        await window.api.stopEngine()
      }
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
    } finally {
      if (shouldRestartEngine && window.api?.startEngine) {
        await window.api.startEngine().catch((error) => {
          console.error('Failed to restart engine after device refresh:', error)
        })
      }
    }
  }

  useEffect(() => {
    let mounted = true
    const setup = async () => {
      try {
        if (!navigator.mediaDevices) return
        const foundDevices = await enumerateMediaDevices()
        if (mounted && (foundDevices.cameras.length > 0 || foundDevices.microphones.length > 0)) {
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
  }, [])

  useEffect(() => {
    if (!window.api?.updateSettings) return
    // Only sync if we have devices enumerated, to avoid sending -1/default unintentionally
    if (devices.cameras.length === 0 && devices.microphones.length === 0) return

    const camIndex = devices.cameras.findIndex((c) => c.deviceId === settings.selectedCameraId)
    const micIndex = devices.microphones.findIndex((m) => m.deviceId === settings.selectedMicId)

    // Map gestureSensitivity (10-100) to min_detection_confidence (0.5-0.95)
    // High sensitivity = Low confidence threshold
    const sensitivity = Math.max(10, Math.min(100, settings.gestureSensitivity))
    const minConf = 0.5 + (100 - sensitivity) / 200.0

    const payload = {
      camera_index: camIndex >= 0 ? camIndex : 0,
      voice_input_index: micIndex >= 0 ? micIndex : -1,
      hand_min_detection_confidence: minConf,
      voice_phrase_cooldown_sec: settings.actionCooldownMs / 1000.0,
      notifications: settings.notifications
    }

    window.api.updateSettings(payload).catch((err) => {
      console.error('Failed to update settings:', err)
    })
  }, [settings, devices])

  const engineOwnsMedia =
    Boolean(trainingSession) ||
    Boolean(engineStatus?.running) ||
    [
      'training',
      'restarting',
      'loading_modules',
      'initializing_models',
      'opening_camera',
      'starting_voice'
    ].includes(engineStatus?.phase)

  // ── Camera status sync (reads engineStatus, never touches the media stream) ──
  useEffect(() => {
    const phase = engineStatus?.phase
    const isRunning = engineStatus?.running
    if (isRunning || phase === 'active') {
      setCameraStatus('connected (engine)')
      setMicStatus('connected (engine)')
    } else if (phase === 'training') {
      setCameraStatus('training')
      setMicStatus('training')
    } else if (phase === 'restarting') {
      setCameraStatus((prev) => (prev === 'training' ? 'idle' : prev))
      setMicStatus((prev) => (prev === 'training' ? 'idle' : prev))
    } else if (phase === 'stopped' || phase === 'error') {
      setCameraStatus((prev) =>
        prev === 'connected (engine)' || prev === 'training' ? 'idle' : prev
      )
      setMicStatus((prev) => (prev === 'connected (engine)' || prev === 'training' ? 'idle' : prev))
    }
  }, [engineStatus])

  // ── Camera stream (getUserMedia for live-monitoring preview) ──
  // NOTE: engineStatus is intentionally NOT in the dep array.
  // Status sync is handled by the effect above; we only want to
  // (re)start the stream when the selected device or active tab changes.
  // Including engineStatus would restart/stop the stream on every phase
  // event (starting → loading_modules → active …) causing the visible
  // connect/disconnect cycle.
  useEffect(() => {
    const videoElement = videoRef.current
    let cancelled = false

    // Short debounce so rapid selectedCameraId changes (e.g. from two quick
    // enumerateDevices calls on mount) settle before we open the stream.
    const timer = setTimeout(async () => {
      if (cancelled) return
      if (tab !== 'live-monitoring' || !settings.selectedCameraId || engineOwnsMedia) return

      // If the engine is already running, it owns the camera — skip getUserMedia.
      // We read engineStatus via the closure so this doesn't become a dep.
      if (engineOwnsMedia) return

      try {
        setCameraStatus('connecting')
        cameraStreamRef.current?.getTracks().forEach((t) => t.stop())
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { deviceId: { exact: settings.selectedCameraId } },
          audio: false
        })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        cameraStreamRef.current = stream
        if (videoElement) videoElement.srcObject = stream
        setCameraStatus('connected')
      } catch (error) {
        if (!cancelled) {
          setCameraStatus('error')
          setMediaError(error?.message || 'Camera stream unavailable.')
        }
      }
    }, 300)

    return () => {
      cancelled = true
      clearTimeout(timer)
      stopCameraPreview()
    }
  }, [tab, settings.selectedCameraId, engineOwnsMedia])

  useEffect(() => {
    let audioContext = null
    const startMicLevel = async () => {
      if (tab !== 'live-monitoring' || !settings.selectedMicId || engineOwnsMedia) return
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
      stopMicPreview()
      if (audioContext) {
        void audioContext.close().catch(() => {})
      }
    }
  }, [tab, settings.selectedMicId, engineOwnsMedia])

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

  // NOTE: Startup engine launch is handled by the first useEffect above.

  useEffect(() => {
    if (!window.api?.onTrainingProgress) return
    const unsubscribe = window.api.onTrainingProgress((payload = {}) => {
      if (payload.cancelled) {
        if (payload.gestureId) {
          setGestures((prev) => prev.filter((gesture) => gesture.id !== payload.gestureId))
        }
        void syncGestureLibraryFromEngine()
        setTrainingSession(null)
        return
      }

      setTrainingSession((prev) => {
        if (!prev) return prev
        // Ignore events for other sessions
        if (payload.sessionId && prev.sessionId && payload.sessionId !== prev.sessionId) {
          return prev
        }
        if (payload.gestureId && payload.gestureId !== prev.gestureId) {
          return prev
        }

        if (payload.failed || payload.error) {
          if (payload.gestureId) {
            setGestures((items) => items.filter((gesture) => gesture.id !== payload.gestureId))
          }
          notifyFromEffect('Training Failed', payload.error || 'Training failed', true)
          if (window.api?.completeTraining) {
            void window.api.completeTraining()
          }
          void syncGestureLibraryFromEngine()
          return null
        }

        const nextProgress = Math.max(0, Math.min(100, Number(payload.progress) || 0))
        const updated = {
          ...prev,
          sessionId: payload.sessionId || prev.sessionId || null,
          source: 'engine',
          progress: nextProgress,
          cueIndex: getCueIndexFromProgress(prev.type, nextProgress),
          stats: payload.result || {}
        }

        if (payload.done && nextProgress >= 100) {
          if (window.api?.completeTraining) {
            void window.api.completeTraining()
          }
          void syncGestureLibraryFromEngine()
        }

        return updated
      })
    })

    return () => {
      if (typeof unsubscribe === 'function') {
        unsubscribe()
      }
    }
  }, [])

  useEffect(() => {
    if (!window.api?.onEngineVoice) return
    const unsubscribe = window.api.onEngineVoice((payload = {}) => {
      if (payload.executed && payload.action) {
        notifyFromEffect(
          'Voice Command',
          `Executed: ${describeEngineAction(payload.action)}`,
          false
        )
      }
    })
    return () => {
      if (typeof unsubscribe === 'function') unsubscribe()
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
    const phase = engineStatus?.phase

    // Error states always take precedence
    if (phase === 'error') return { label: 'Engine Error', tone: 'error' }
    if (mediaError && !engineStatus?.running) return { label: 'System Error', tone: 'error' }

    // Granular startup phases — must be checked BEFORE the generic running check
    if (phase === 'loading_modules') return { label: 'Loading AI Modules...', tone: 'starting' }
    if (phase === 'initializing_models')
      return { label: 'Initializing Models...', tone: 'starting' }
    if (phase === 'opening_camera') return { label: 'Connecting Camera...', tone: 'starting' }
    if (phase === 'starting_voice') return { label: 'Starting Voice Engine...', tone: 'starting' }
    if (phase === 'starting') return { label: 'Starting Engine...', tone: 'starting' }
    if (phase === 'restarting') return { label: 'Restarting Engine...', tone: 'starting' }

    // Training in progress (runtime is stopped; training owns camera)
    if (phase === 'training' || trainingSession) {
      if (trainingSession?.progress >= 100) return { label: 'Training Complete', tone: 'active' }
      return { label: 'Training in Progress...', tone: 'starting' }
    }

    // Engine fully active
    if (engineStatus?.running || phase === 'active') {
      if (mediaError) return { label: 'Engine Active (Input Error)', tone: 'error' }
      return { label: 'Engine Active', tone: 'active' }
    }

    // Non-engine states (engine stopped, using browser media)
    if (tab === 'live-monitoring') {
      if (cameraStatus === 'connecting' || micStatus === 'connecting') {
        return { label: 'Connecting Input...', tone: 'starting' }
      }
      if (
        cameraStatus === 'connected' ||
        cameraStatus === 'connected (engine)' ||
        micStatus === 'connected'
      ) {
        return { label: 'Input Connected', tone: 'active' }
      }
    }

    return { label: 'System Idle', tone: 'idle' }
  }, [cameraStatus, mediaError, micStatus, tab, engineStatus, trainingSession])

  const handleEditSave = async () => {
    if (!editingGesture) return
    if (editingGesture.locked) {
      setEditingGesture(null)
      return
    }
    const title = editingGesture.title.trim()
    const subtitle = editingGesture.subtitle.trim()
    if (!title || !subtitle) return
    const nextGesture = {
      ...editingGesture,
      title,
      subtitle,
      defaultAction: subtitle,
      engineAction: toEngineAction(subtitle),
      engineGestureName: editingGesture.type === 'hand' ? title : editingGesture.engineGestureName
    }
    const nextGestures = gestures.map((item) =>
      item.id === editingGesture.id ? nextGesture : item
    )

    try {
      if (window.api?.updateGesture) {
        const updateResult = await window.api.updateGesture({
          type: editingGesture.type,
          oldName: editingGesture.engineGestureName || editingGesture.title,
          newName: title,
          oldPhrase: editingGesture.phrase,
          phrase: nextGesture.phrase,
          action: nextGesture.engineAction
        })
        if (updateResult?.ok === false) {
          throw new Error(updateResult.error || 'Failed to update gesture')
        }
      }

      setGestures(nextGestures)
      void syncGestureLibraryFromEngine()
      void notifyUser('Gesture updated', `${title} mapping has been saved.`)
      setEditingGesture(null)
    } catch (error) {
      void notifyUser('Gesture update failed', error?.message || 'Please try again.', true)
    }
  }

  const handleDeleteConfirmed = async (id) => {
    const removed = gestures.find((item) => item.id === id)
    if (removed?.locked) {
      setPendingDeleteGesture(null)
      return
    }
    const nextGestures = gestures.filter((item) => item.id !== id)
    try {
      if (removed && window.api?.deleteGesture) {
        const result = await window.api.deleteGesture({
          type: removed.type,
          label: removed.label,
          gestureName: removed.engineGestureName || removed.title,
          phrase: removed.phrase
        })
        if (result?.ok === false) {
          throw new Error(result.error || 'Failed to delete gesture')
        }
      }

      setGestures(nextGestures)
      void syncGestureLibraryFromEngine()
    } catch (error) {
      void notifyUser('Gesture delete failed', error?.message || 'Please try again.', true)
      setPendingDeleteGesture(null)
      return
    }

    if (selectedGesture?.id === id) setSelectedGesture(null)
    setPendingDeleteGesture(null)
    if (removed) {
      void notifyUser('Gesture deleted', `${removed.title} was removed.`)
    }
  }

  const handleToggleDefaultGesture = (id) => {
    const nextGestures = gestures.map((item) =>
      item.id === id && item.locked ? { ...item, enabled: item.enabled === false } : item
    )
    setGestures(nextGestures)
    void persistDisabledStaticGestures(nextGestures)
  }

  const createGesture = (preset) => {
    if (!preset) return null
    const id = `${preset.id}-${Date.now()}`
    const actionLabel = preset.defaultAction || preset.templateSubtitle || 'Click'
    const created = {
      id,
      title: preset.templateTitle || 'New Gesture',
      subtitle: actionLabel,
      type: preset.type || 'hand',
      controlModel: preset.controlModel || 'static',
      family: preset.family || 'Custom Feature',
      defaultAction: actionLabel,
      engineAction: toEngineAction(actionLabel),
      enabled: true,
      locked: false,
      ...(preset.type === 'hand'
        ? { engineGestureName: preset.templateTitle || 'New Gesture' }
        : {}),
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
      setTrainingSession(null)
      setGestures((prev) => prev.filter((item) => item.id !== gesture.id))
      void notifyUser('Training unavailable', 'The training engine is not ready yet.', true)
      return
    }

    try {
      const result = await window.api.startTraining({
        gestureId: gesture.id,
        gestureName: gesture.title,
        action: gesture.engineAction || toEngineAction(gesture.defaultAction),
        type: gesture.type,
        ...(gesture.type === 'voice' ? { phrase: gesture.phrase } : {}),
        locked: gesture.locked
      })
      // Backend returns { ok, sessionId, gestureId, type } — check sessionId as availability signal
      if (result?.ok === false) {
        throw new Error(result.error || 'Training could not be started')
      }

      setTrainingSession((prev) =>
        prev && prev.gestureId === gesture.id
          ? { ...prev, sessionId: result.sessionId || null, source: 'engine' }
          : prev
      )
    } catch (error) {
      setTrainingSession(null)
      setGestures((prev) => prev.filter((item) => item.id !== gesture.id))
      void notifyUser('Training start failed', error?.message || 'Please try again.', true)
      if (returnTab) {
        setTab(returnTab)
      }
    }
  }

  const handleAddGestureType = (preset) => {
    if (UNSUPPORTED_CUSTOM_PRESET_IDS.has(preset.id)) {
      void notifyUser(
        'Dynamic training not ready',
        'Custom dynamic gesture training is not implemented yet. Use the built-in dynamic families or add a static command instead.',
        true
      )
      setShowAddTypePopup(false)
      return
    }

    // Instead of going straight to permissions, show the setup form
    setGestureSetupForm({
      preset,
      name: preset.templateTitle || 'New Gesture',
      action: preset.defaultAction || 'Click',
      phrase: preset.phrase || ''
    })
    setShowAddTypePopup(false)
  }

  const handleStartGestureTraining = async () => {
    if (!gestureSetupForm) return
    const { preset, name, action, phrase } = gestureSetupForm
    setGestureSetupForm(null)

    // Build the gesture using user-provided name and action
    const enrichedPreset = {
      ...preset,
      templateTitle: name.trim() || preset.templateTitle || 'New Gesture',
      defaultAction: action,
      ...(preset.type === 'voice' ? { phrase: phrase.trim() || 'your command' } : {})
    }
    const returnTab = settings.openMonitoringAfterAdd ? null : tab
    const created = createGesture(enrichedPreset)
    setTab('live-monitoring')
    await startTrainingSession(created, returnTab)
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

  const handleRestartEngine = async () => {
    if (!window.api?.stopEngine || !window.api?.startEngine) return
    try {
      await notifyUser('Restarting Engine', 'Stopping background service...', true)
      await window.api.stopEngine()
      // Brief pause to ensure port release
      await new Promise((resolve) => setTimeout(resolve, 1000))
      await window.api.startEngine()
      await notifyUser('Engine Restarted', 'Background service is active.', true)
    } catch (error) {
      console.error('Failed to restart engine:', error)
      await notifyUser('Restart Failed', error?.message || 'Unknown error', true)
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

  if (!hasStartupPermissions) {
    return (
      <div className="app-shell startup-shell">
        <section className="modal-card">
          <div className="brand" style={{ justifyContent: 'center', marginBottom: '1.5rem' }}>
            <span className="brand-logo" style={{ width: 64, height: 64 }}>
              <BrandLogo />
            </span>
          </div>
          <h2 style={{ textAlign: 'center', marginBottom: '1rem' }}>Welcome to Octave</h2>
          <p style={{ textAlign: 'center', color: 'var(--text-secondary)', marginBottom: '2rem' }}>
            To enable gesture control and voice commands, Octave needs access to your camera and
            microphone.
          </p>
          <div className="modal-actions" style={{ justifyContent: 'center' }}>
            <button
              className="primary-btn"
              type="button"
              style={{ fontSize: '1.1rem', padding: '0.8rem 2rem' }}
              onClick={async () => {
                const granted = await requestDeviceAccess('both')
                if (granted) {
                  setHasStartupPermissions(true)
                  if (window.api?.startEngine) {
                    void notifyUser('Starting Engine', 'Initializing gesture recognition...', false)
                    try {
                      const result = await window.api.startEngine()
                      if (result && result.ok !== false) {
                        void notifyUser('Engine Active', 'Gesture control is ready.', false)
                      } else {
                        void notifyUser(
                          'Engine Error',
                          result.error || 'Failed to start engine',
                          true
                        )
                      }
                    } catch (e) {
                      void notifyUser('Engine Error', e.message || 'Unknown error', true)
                    }
                  }
                }
              }}
            >
              Grant Access & Start
            </button>
          </div>
        </section>
      </div>
    )
  }

  const isEngineLoading = systemStatus.tone === 'starting' && engineStatus?.phase !== 'training'

  return (
    <main className="app-shell" onCopy={handleCopyGuard} onKeyDown={handleKeyDownGuard}>
      {isEngineLoading && (
        <div className="app-loading-overlay" aria-live="polite" aria-label="Loading">
          <div className="app-loading-inner">
            <span className="app-loading-logo" aria-hidden>
              <BrandLogo />
            </span>
            <p className="app-loading-label">{systemStatus.label}</p>
            <div className="app-loading-dots" aria-hidden>
              <span />
              <span />
              <span />
            </div>
          </div>
        </div>
      )}
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
          <span style={{ marginRight: 'auto' }}>{systemStatus.label}</span>
          {!engineStatus.running && engineStatus.phase !== 'starting' ? (
            <button
              className="icon-action"
              style={{ width: 'auto', padding: '0 0.5rem', fontSize: '0.8rem', height: '24px' }}
              onClick={() => void handleRestartEngine()}
              title="Start Engine"
            >
              Start
            </button>
          ) : null}
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
                  New Gesture (Beta Testing)
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
                  {engineOwnsMedia ? (
                    <img
                      className="preview-video"
                      src={
                        trainingSession
                          ? 'http://127.0.0.1:5000/training_feed'
                          : 'http://127.0.0.1:5000/video_feed'
                      }
                      alt={trainingSession ? 'Training Stream' : 'Engine Stream'}
                      style={{ objectFit: 'contain', width: '100%', height: '100%' }}
                    />
                  ) : (
                    <video ref={videoRef} className="preview-video" autoPlay muted playsInline />
                  )}
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
                    {trainingSession.stats && trainingSession.stats.epoch ? (
                      <div className="training-stats-overlay">
                        <span>
                          Epoch: {trainingSession.stats.epoch} / {trainingSession.stats.totalEpochs}
                        </span>
                        {trainingSession.stats.loss !== undefined ? (
                          <span>Loss: {Number(trainingSession.stats.loss).toFixed(4)}</span>
                        ) : null}
                      </div>
                    ) : null}
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
                  <div className="form-row-actions" style={{ marginTop: '1rem' }}>
                    <button
                      className="secondary-btn"
                      type="button"
                      onClick={() => void handleRestartEngine()}
                      disabled={engineStatus.phase === 'starting'}
                    >
                      {engineStatus.phase === 'starting' ? 'Starting...' : 'Restart Engine Service'}
                    </button>
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

      {gestureSetupForm ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setGestureSetupForm(null)}
        >
          <section
            className="modal-card modal-card-wide gesture-setup-modal"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Set Up Your Gesture</h3>
            <p className="add-intro">
              Give your gesture a name and choose what it should do. You can change this later.
            </p>

            {/* Name Field */}
            <label className="form-field gesture-setup-name-field">
              <span>Gesture Name</span>
              <input
                type="text"
                value={gestureSetupForm.name}
                maxLength={48}
                placeholder="e.g. Open Browser, Play Music..."
                onChange={(e) =>
                  setGestureSetupForm((prev) => (prev ? { ...prev, name: e.target.value } : prev))
                }
              />
            </label>

            {/* Phrase Field for voice */}
            {gestureSetupForm.preset?.type === 'voice' ? (
              <label className="form-field gesture-setup-name-field">
                <span>Voice Phrase</span>
                <input
                  type="text"
                  value={gestureSetupForm.phrase}
                  maxLength={64}
                  placeholder="e.g. next tab, mute audio..."
                  onChange={(e) =>
                    setGestureSetupForm((prev) =>
                      prev ? { ...prev, phrase: e.target.value } : prev
                    )
                  }
                />
              </label>
            ) : null}

            {/* Action Picker */}
            <div className="gesture-setup-actions-label">
              <span>What should this gesture do?</span>
            </div>
            <div className="gesture-setup-action-groups">
              {AVAILABLE_ACTIONS.map((group) => (
                <div key={group.group} className="gesture-action-group">
                  <span className="gesture-action-group-label">{group.group}</span>
                  <div className="gesture-action-toggles">
                    {group.actions.map((action) => (
                      <button
                        key={action}
                        type="button"
                        className={`gesture-action-toggle ${gestureSetupForm.action === action ? 'selected' : ''}`}
                        onClick={() =>
                          setGestureSetupForm((prev) => (prev ? { ...prev, action } : prev))
                        }
                      >
                        {action}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="modal-actions" style={{ marginTop: '1.5rem' }}>
              <button
                className="modal-cancel"
                type="button"
                onClick={() => setGestureSetupForm(null)}
              >
                Cancel
              </button>
              <button
                className="primary-btn"
                type="button"
                disabled={!gestureSetupForm.name.trim()}
                onClick={() => void handleStartGestureTraining()}
              >
                Start Training
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
              <span>{editingGesture.type === 'voice' ? 'Voice Phrase Name' : 'Name'}</span>
              <input
                value={editingGesture.title}
                disabled={editingGesture.type === 'voice'}
                onChange={(event) =>
                  setEditingGesture((prev) =>
                    prev ? { ...prev, title: event.target.value } : prev
                  )
                }
              />
            </label>
            <label className="form-field">
              <span>Action</span>
              <select
                value={editingGesture.subtitle}
                onChange={(event) =>
                  setEditingGesture((prev) =>
                    prev ? { ...prev, subtitle: event.target.value } : prev
                  )
                }
              >
                {ACTION_OPTIONS.map((action) => (
                  <option key={action} value={action}>
                    {action}
                  </option>
                ))}
              </select>
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

# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Octave gesture-control backend.
# Output: python_dist/service/service.exe  (folder-mode, not onefile)
# Run with:  .venv\Scripts\pyinstaller service.spec
#

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# ── Data files to bundle ──────────────────────────────────────────────────────
# mediapipe ships its model files as package data
mediapipe_datas = collect_data_files('mediapipe')

# vosk ships model files as package data
vosk_datas = collect_data_files('vosk')

# Our own ml_engine/data directory (label maps, trained models, voice model)
project_datas = [
    ('ml_engine/data',   'ml_engine/data'),
    ('config',           'config'),
]

all_datas = project_datas + mediapipe_datas + vosk_datas

# ── Hidden imports ────────────────────────────────────────────────────────────
# Modules that PyInstaller misses because they're imported conditionally/lazily
hidden_imports = [
    # Flask / gevent
    'flask',
    'flask.templating',
    'gevent',
    'gevent.pywsgi',
    'gevent.socket',
    'gevent._hub_primitives',
    'gevent._fileobjectposix',
    'gevent._greenlet_primitives',
    'gevent._local',
    'gevent._semaphore',
    'gevent.subprocess',
    'geventwebsocket',
    # Mediapipe
    'mediapipe',
    'mediapipe.python',
    'mediapipe.python.solutions',
    'mediapipe.python.solutions.hands',
    'mediapipe.python.solutions.drawing_utils',
    # CV2
    'cv2',
    # Torch
    'torch',
    'torch.nn',
    'torch.nn.functional',
    # Vosk
    'vosk',
    # SoundDevice
    'sounddevice',
    # PyAutoGUI / related
    'pyautogui',
    'pycaw',
    'pycaw.pycaw',
    'comtypes',
    'comtypes.client',
    # MSS screen capture
    'mss',
    'mss.windows',
    # Screen brightness
    'screen_brightness_control',
    'screen_brightness_control.windows',
    # Numpy / Pandas
    'numpy',
    'pandas',
    # Pillow
    'PIL',
    'PIL.Image',
    # Our local packages
    'action_engine',
    'api_engine',
    'config',
    'dynamic_engine',
    'intent_engine',
    'ml_engine',
    'screen_engine',
    'utils',
    'voice_engine',
]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['service.py'],
    pathex=['.'],
    binaries=[],
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Things we definitely don't need in the backend bundle
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
        'PyQt5',
        'PySide2',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # folder mode (COLLECT below)
    name='service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX can break native extensions (cv2, torch, etc.)
    console=True,            # must stay True – Electron reads stdout/stderr
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='build/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='service',
)

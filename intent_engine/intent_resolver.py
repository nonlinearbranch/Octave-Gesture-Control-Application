from intent_engine.mode_manager import switch_mode
from intent_engine.cooldown_manager import can_execute

from dynamic_engine.cursor_control import move_cursor
from dynamic_engine.grasp_control import grasp_control
from dynamic_engine.navigation_control import navigate
from dynamic_engine.rotation_control import rotate_delta
from dynamic_engine.scroll_control import scroll
from dynamic_engine.magnitude_control import magnitude_delta, apply_value, zoom_control

from action_engine.volume_control import get_volume, set_volume
from action_engine.brightness_control import get_brightness, set_brightness
from action_engine.app_launcher import open_vscode, open_app, open_folder
from action_engine.system_actions import play_pause, mute, playback_speed
from utils.helpers import load_gesture_mapping
import subprocess
import webbrowser

import pyautogui


def _run_dynamic_intent(hand, family, intent):
    if hand is None or family is None or intent is None:
        return

    if family == "MAGNITUDE":
        delta = magnitude_delta(hand)
        if not delta:
            return
        if intent == "Volume":
            val = apply_value(get_volume(), delta)
            set_volume(val)
        elif intent == "Brightness":
            val = apply_value(get_brightness(), delta)
            set_brightness(val)
        elif intent == "Zoom":
            zoom_control(delta)
        elif intent == "ScrollSpeed":
            pyautogui.scroll(int(600 * delta))
        elif intent == "PlaybackSpeed":
            playback_speed(delta)

    elif family == "CURSOR":
        move_cursor(hand)

    elif family == "GRAB":
        move_cursor(hand)
        grasp_control(hand)

    elif family == "NAVIGATION":
        navigate(hand)

    elif family == "ROTATION":
        d = rotate_delta(hand)
        if d:
            pyautogui.scroll(int(800 * d))

    elif family == "SCROLL":
        scroll(hand)


def execute_custom_action(action):
    if not action:
        return False

    if isinstance(action, str):
        name = action.strip()
        if name == "PlayPause":
            play_pause()
            return True
        if name == "MuteToggle":
            mute()
            return True
        if name == "AltRight":
            pyautogui.hotkey("alt", "right")
            return True
        if name == "Click":
            pyautogui.click()
            return True
        if name == "ModeSwitch":
            switch_mode()
            return True
        if name == "OpenVSCode":
            open_vscode()
            return True
        if name.startswith("launch:"):
            return open_app(name.split(":", 1)[1].strip())
        return False

    if not isinstance(action, dict):
        return False

    kind = str(action.get("type", "")).strip().lower()
    if kind == "launch_app":
        return open_app(action.get("target"))
    if kind == "hotkey":
        keys = action.get("keys", [])
        if isinstance(keys, list) and keys:
            pyautogui.hotkey(*[str(k) for k in keys])
            return True
        return False
    if kind == "key":
        key = action.get("key")
        if key:
            pyautogui.press(str(key))
            return True
        return False
    if kind == "command":
        cmd = action.get("command")
        if cmd:
            subprocess.Popen(str(cmd), shell=True)
            return True
        return False
    if kind == "url":
        url = action.get("url")
        if url:
            webbrowser.open(str(url))
            return True
        return False
    if kind == "open_path":
        path = action.get("path")
        if path:
            open_folder(str(path))
            return True
        return False
    return False


def _run_static_gesture(gesture_name):
    if not gesture_name:
        return

    if not can_execute(gesture_name):
        return

    mapping = load_gesture_mapping()
    static_actions = mapping.get("static_actions", {})
    action = static_actions.get(gesture_name)
    if execute_custom_action(action):
        return

    if gesture_name == "Three Fingers":
        switch_mode()
    elif gesture_name == "Fist":
        play_pause()
    elif gesture_name == "Thumb":
        mute()
    elif gesture_name == "V Sign":
        pyautogui.hotkey("alt", "right")
    elif gesture_name == "OK Sign":
        pyautogui.click()
    elif gesture_name == "DRS T-Frame":
        open_vscode()


def resolve_intent(hand, gesture_name=None, family=None, intent=None):
    _run_dynamic_intent(hand, family, intent)
    _run_static_gesture(gesture_name)

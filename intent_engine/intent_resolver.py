from intent_engine.mode_manager import get_mode, switch_mode
from intent_engine.cooldown_manager import can_execute

from dynamic_engine.cursor_control import move_cursor
from dynamic_engine.grasp_control import grasp_control
from dynamic_engine.navigation_control import navigate
from dynamic_engine.rotation_control import rotate_delta
from dynamic_engine.scroll_control import scroll
from dynamic_engine.magnitude_control import magnitude_delta, apply_value, zoom_control

from action_engine.volume_control import get_volume, set_volume
from action_engine.brightness_control import get_brightness, set_brightness
from action_engine.app_launcher import open_vscode
from action_engine.system_actions import play_pause, mute

import pyautogui


def resolve_intent(hand, gesture_name):
    mode = get_mode()

    # ---------- Dynamic families ----------

    if mode == "CURSOR":
        move_cursor(hand)
        grasp_control(hand)

    elif mode == "VOLUME":
        delta = magnitude_delta(hand)
        if delta:
            val = apply_value(get_volume(), delta)
            set_volume(val)

    elif mode == "BRIGHTNESS":
        delta = magnitude_delta(hand)
        if delta:
            val = apply_value(get_brightness(), delta)
            set_brightness(val)

    elif mode == "SCROLL":
        scroll(hand)

    elif mode == "ZOOM":
        delta = magnitude_delta(hand)
        if delta:
            zoom_control(delta)

    elif mode == "NAVIGATION":
        navigate(hand)

    elif mode == "ROTATION":
        rotate_delta(hand)

    # ---------- Static gestures with cooldown ----------

    if not gesture_name:
        return

    if not can_execute(gesture_name):
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

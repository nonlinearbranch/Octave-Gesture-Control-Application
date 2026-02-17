import os
import time
import shutil
import pyautogui
from utils.helpers import get_setting

last_call = {}


def can_run(name):
    cooldown = float(get_setting("system_action_cooldown_sec", 2.0))
    now = time.time()
    if name not in last_call:
        last_call[name] = 0
    if now - last_call[name] > cooldown:
        last_call[name] = now
        return True
    return False


def play_pause():
    cmd = (get_setting("system_commands", {}) or {}).get("play_pause", "nircmd sendkeypress space")
    if can_run("PLAY"):
        if cmd and shutil.which(cmd.split()[0]):
            os.system(cmd)
        else:
            pyautogui.press("space")


def mute():
    cmd = (get_setting("system_commands", {}) or {}).get("mute_toggle", "nircmd mutesysvolume 2")
    if can_run("MUTE"):
        if cmd and shutil.which(cmd.split()[0]):
            os.system(cmd)
        else:
            pyautogui.press("volumemute")


def playback_speed(delta):
    if not can_run("PLAYBACK_SPEED"):
        return
    if delta > 0:
        pyautogui.hotkey("shift", ".")
    elif delta < 0:
        pyautogui.hotkey("shift", ",")

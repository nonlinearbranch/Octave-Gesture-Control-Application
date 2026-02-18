import time
from utils.helpers import get_setting

last_trigger_time = {}


def can_execute(gesture_name):
    cooldowns = get_setting("gesture_cooldowns", {
        "Fist": 1.5,
        "Thumb": 1.5,
        "V Sign": 1.5,
        "OK Sign": 1.0,
        "Three Fingers": 1.5,
        "DRS T-Frame": 2.0
    })
    now = time.time()

    if gesture_name not in cooldowns:
        return True

    if gesture_name not in last_trigger_time:
        last_trigger_time[gesture_name] = 0

    if now - last_trigger_time[gesture_name] >= cooldowns[gesture_name]:
        last_trigger_time[gesture_name] = now
        return True

    return False

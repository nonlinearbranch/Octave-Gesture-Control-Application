import time
from utils.helpers import get_setting

modes = get_setting("dynamic_modes", [
    "CURSOR",
    "VOLUME",
    "BRIGHTNESS",
    "SCROLL",
    "ZOOM",
    "NAVIGATION",
    "ROTATION"
])

index = 0
last_switch = 0


def get_mode():
    if not modes:
        return "CURSOR"
    return modes[index]


def switch_mode():
    global index, last_switch
    cooldown = float(get_setting("mode_switch_cooldown_sec", 1.5))

    now = time.time()
    if now - last_switch < cooldown:
        return get_mode()

    index = (index + 1) % len(modes)
    last_switch = now
    return get_mode()

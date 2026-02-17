import time

modes = [
    "CURSOR",
    "VOLUME",
    "BRIGHTNESS",
    "SCROLL",
    "ZOOM",
    "NAVIGATION",
    "ROTATION"
]

index = 0
last_switch = 0
cooldown = 1.5


def get_mode():
    return modes[index]


def switch_mode():
    global index, last_switch

    now = time.time()
    if now - last_switch < cooldown:
        return get_mode()

    index = (index + 1) % len(modes)
    last_switch = now
    return get_mode()

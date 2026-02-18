import screen_brightness_control as sbc
from utils.helpers import get_setting


def get_brightness():
    display = int(get_setting("brightness_display_index", 0))
    return sbc.get_brightness(display=display)[0] / 100


def set_brightness(value):
    display = int(get_setting("brightness_display_index", 0))
    value = max(0, min(1, value))
    sbc.set_brightness(int(value * 100), display=display)

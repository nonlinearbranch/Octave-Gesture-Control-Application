import screen_brightness_control as sbc


def get_brightness():
    return sbc.get_brightness(display=0)[0] / 100


def set_brightness(value):
    value = max(0, min(1, value))
    sbc.set_brightness(int(value * 100), display=0)

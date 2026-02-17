from dynamic_engine.motion_utils import smooth
import pyautogui

last_y = None
smooth_val = None

deadzone = 0.01
speed = 2.0
alpha = 0.2


def magnitude_delta(hand):
    global last_y

    y = hand.landmark[9].y

    if last_y is None:
        last_y = y
        return 0

    diff = last_y - y
    last_y = y

    if abs(diff) < deadzone:
        return 0

    return diff * speed


def apply_value(current, delta):
    global smooth_val

    target = current + delta
    target = max(0, min(1, target))
    smooth_val = smooth(smooth_val, target, alpha)

    return smooth_val


def zoom_control(delta):
    if delta > 0:
        pyautogui.keyDown("ctrl")
        pyautogui.scroll(200)
        pyautogui.keyUp("ctrl")
    elif delta < 0:
        pyautogui.keyDown("ctrl")
        pyautogui.scroll(-200)
        pyautogui.keyUp("ctrl")

import pyautogui

last_x = None
threshold = 0.08


def navigate(hand):
    global last_x

    x = hand.landmark[8].x

    if last_x is None:
        last_x = x
        return

    diff = x - last_x

    if diff > threshold:
        pyautogui.hotkey("alt", "right")
        last_x = None

    elif diff < -threshold:
        pyautogui.hotkey("alt", "left")
        last_x = None

import pyautogui

last_y = None
speed = 300


def scroll(hand):
    global last_y

    y = hand.landmark[8].y

    if last_y is None:
        last_y = y
        return

    diff = last_y - y

    if diff > 0.02:
        pyautogui.scroll(speed)

    elif diff < -0.02:
        pyautogui.scroll(-speed)

    last_y = y

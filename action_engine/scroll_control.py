import pyautogui

speed = 300


def scroll_up():
    pyautogui.scroll(speed)


def scroll_down():
    pyautogui.scroll(-speed)

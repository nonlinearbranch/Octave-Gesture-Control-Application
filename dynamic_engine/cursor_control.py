import pyautogui
from dynamic_engine.motion_utils import smooth

screen_w, screen_h = pyautogui.size()

sx = None
sy = None
alpha = 0.3


def move_cursor(hand):
    global sx, sy

    tip = hand.landmark[8]

    x = tip.x * screen_w
    y = tip.y * screen_h

    sx = smooth(sx, x, alpha)
    sy = smooth(sy, y, alpha)

    pyautogui.moveTo(int(sx), int(sy))

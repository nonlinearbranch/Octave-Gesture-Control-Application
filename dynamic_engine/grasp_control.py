import pyautogui
from dynamic_engine.motion_utils import distance

dragging = False


def grasp_control(hand):
    global dragging

    d = distance(hand.landmark[4], hand.landmark[8])

    if d < 0.035 and not dragging:
        pyautogui.mouseDown()
        dragging = True

    elif d > 0.06 and dragging:
        pyautogui.mouseUp()
        dragging = False

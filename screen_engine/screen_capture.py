import mss
import numpy as np
import cv2


def capture_resized(scale=0.25):
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)

    frame = np.array(img)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    small = cv2.resize(frame, (0, 0), fx=scale, fy=scale)

    return small

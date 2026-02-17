import mss
import numpy as np
import cv2
from utils.helpers import get_setting


def capture_resized(scale=0.25):
    with mss.mss() as sct:
        idx = int(get_setting("mss_monitor_index", 1))
        if idx < 1 or idx >= len(sct.monitors):
            idx = 1
        monitor = sct.monitors[idx]
        img = sct.grab(monitor)

    frame = np.array(img)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    small = cv2.resize(frame, (0, 0), fx=scale, fy=scale)

    return small

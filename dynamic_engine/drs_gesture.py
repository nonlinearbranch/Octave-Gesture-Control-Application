import math
import time

last_valid_time = 0
hold_time = 0.5


def palm_normal(hand):
    wrist = hand.landmark[0]
    index = hand.landmark[5]
    pinky = hand.landmark[17]

    v1 = (
        index.x - wrist.x,
        index.y - wrist.y,
        index.z - wrist.z
    )

    v2 = (
        pinky.x - wrist.x,
        pinky.y - wrist.y,
        pinky.z - wrist.z
    )

    nx = v1[1]*v2[2] - v1[2]*v2[1]
    ny = v1[2]*v2[0] - v1[0]*v2[2]
    nz = v1[0]*v2[1] - v1[1]*v2[0]

    mag = math.sqrt(nx*nx + ny*ny + nz*nz)
    if mag == 0:
        return None

    return (nx/mag, ny/mag, nz/mag)


def angle_between(a, b):
    dot = a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
    return math.degrees(math.acos(max(-1, min(1, dot))))


def detect_drs(hand1, hand2):
    global last_valid_time

    n1 = palm_normal(hand1)
    n2 = palm_normal(hand2)

    if n1 is None or n2 is None:
        last_valid_time = 0
        return False

    angle = angle_between(n1, n2)

    if 70 < angle < 110:
        now = time.time()

        if last_valid_time == 0:
            last_valid_time = now

        if now - last_valid_time > hold_time:
            last_valid_time = 0
            return True

    else:
        last_valid_time = 0

    return False

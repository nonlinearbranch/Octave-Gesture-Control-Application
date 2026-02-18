last_angle = None
threshold = 0.03


def rotate_delta(hand):
    global last_angle

    wrist = hand.landmark[0]
    index = hand.landmark[5]

    angle = index.x - wrist.x

    if last_angle is None:
        last_angle = angle
        return 0

    diff = angle - last_angle
    last_angle = angle

    if abs(diff) < threshold:
        return 0

    return diff

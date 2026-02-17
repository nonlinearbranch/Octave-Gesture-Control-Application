from collections import deque, Counter

buffer_size = 12
accept_ratio = 0.7

gesture_buffer = deque(maxlen=buffer_size)


def stable_gesture(new_gesture):
    gesture_buffer.append(new_gesture)

    if len(gesture_buffer) < buffer_size:
        return None

    counts = Counter(gesture_buffer)
    gesture, freq = counts.most_common(1)[0]

    if freq >= buffer_size * accept_ratio:
        return gesture

    return None

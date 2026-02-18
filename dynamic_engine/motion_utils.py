import math


def distance(a, b):
    return math.sqrt(
        (a.x - b.x) ** 2 +
        (a.y - b.y) ** 2 +
        (a.z - b.z) ** 2
    )


def smooth(prev, new, alpha):
    if prev is None:
        return new
    return prev + (new - prev) * alpha

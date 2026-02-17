import cv2
import numpy as np

prev_frame = None


def motion_energy(frame):
    global prev_frame

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if prev_frame is None:
        prev_frame = gray
        return 0.0

    diff = cv2.absdiff(prev_frame, gray)
    prev_frame = gray

    energy = diff.mean() / 255.0
    return min(energy * 5.0, 1.0)

def detect_scrollbar(gray):
    edges = cv2.Canny(gray, 80, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=80, maxLineGap=5)

    if lines is None:
        return 0.0

    count = 0
    for l in lines:
        x1, y1, x2, y2 = l[0]
        if abs(x1 - x2) < 5 and abs(y2 - y1) > 100:
            count += 1

    return min(count / 3.0, 1.0)


def detect_horizontal_slider(gray):
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=120, maxLineGap=5)

    if lines is None:
        return 0.0

    count = 0
    for l in lines:
        x1, y1, x2, y2 = l[0]
        if abs(y1 - y2) < 5 and abs(x2 - x1) > 150:
            count += 1

    return min(count / 3.0, 1.0)


def detect_circular_controls(gray):
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        1.2,
        120,
        param1=50,
        param2=30,
        minRadius=15,
        maxRadius=90,
    )

    if circles is None:
        return 0.0

    return min(len(circles[0]) / 3.0, 1.0)


def text_density(gray):
    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11,
        2,
    )
    density = np.sum(thresh) / (255 * thresh.size)
    return min(density * 2.0, 1.0)


def edge_density(gray):
    edges = cv2.Canny(gray, 50, 150)
    return np.sum(edges > 0) / edges.size


def small_object_density(gray):
    _, th = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    small = 0
    for c in contours:
        area = cv2.contourArea(c)
        if 20 < area < 300:
            small += 1

    return min(small / 120.0, 1.0)


def large_rect_presence(gray):
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = gray.shape
    large = 0

    for c in contours:
        if cv2.contourArea(c) > (h * w * 0.15):
            large += 1

    return min(large / 2.0, 1.0)


def border_edge_density(gray):
    h, w = gray.shape
    border = np.zeros_like(gray)

    border[:30, :] = gray[:30, :]
    border[-30:, :] = gray[-30:, :]
    border[:, :30] = gray[:, :30]
    border[:, -30:] = gray[:, -30:]

    edges = cv2.Canny(border, 50, 150)
    return np.sum(edges > 0) / edges.size


def extract_semantic_features(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    return {
        "scrollbar_score": detect_scrollbar(gray),
        "slider_score": detect_horizontal_slider(gray),
        "circular_score": detect_circular_controls(gray),
        "text_density": text_density(gray),
        "edge_density": edge_density(gray),
        "small_object_density": small_object_density(gray),
        "large_rect_score": large_rect_presence(gray),
        "border_edge_score": border_edge_density(gray),
        "motion_score": motion_energy(frame)
    }

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


def detect_bottom_timeline(gray):
    h, w = gray.shape
    y0 = int(h * 0.72)
    roi = gray[y0:, :]
    edges = cv2.Canny(roi, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 70, minLineLength=int(w * 0.2), maxLineGap=8)
    if lines is None:
        return 0.0
    count = 0
    for l in lines:
        x1, y1, x2, y2 = l[0]
        if abs(y1 - y2) < 4 and abs(x2 - x1) > w * 0.18:
            count += 1
    return min(count / 4.0, 1.0)


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


def centered_object_score(gray):
    h, w = gray.shape
    x0, x1 = int(w * 0.2), int(w * 0.8)
    y0, y1 = int(h * 0.2), int(h * 0.8)
    center = gray[y0:y1, x0:x1]
    edges = cv2.Canny(center, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = 0
    area = center.shape[0] * center.shape[1]
    for k in contours:
        a = cv2.contourArea(k)
        if a > area * 0.08:
            c += 1
    return min(c / 3.0, 1.0)


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
    timeline_score = detect_bottom_timeline(gray)
    slider_score = detect_horizontal_slider(gray)
    text_score = text_density(gray)
    large_rect_score = large_rect_presence(gray)
    center_score = centered_object_score(gray)

    media_ui = min(
        1.0,
        timeline_score * 0.7 +
        slider_score * 0.4 +
        large_rect_score * 0.3 +
        (1.0 - text_score) * 0.3 +
        center_score * 0.3
    )

    return {
        "scrollbar_score": detect_scrollbar(gray),
        "slider_score": slider_score,
        "timeline_score": timeline_score,
        "media_ui_score": media_ui,
        "circular_score": detect_circular_controls(gray),
        "text_density": text_score,
        "edge_density": edge_density(gray),
        "small_object_density": small_object_density(gray),
        "large_rect_score": large_rect_score,
        "center_object_score": center_score,
        "border_edge_score": border_edge_density(gray),
        "motion_score": motion_energy(frame)
    }

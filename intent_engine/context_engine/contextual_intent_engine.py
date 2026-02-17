SAFETY_THRESHOLD = 0.55


def choose_intent(scores):
    best = max(scores, key=scores.get)
    if scores[best] > SAFETY_THRESHOLD:
        return best, scores[best]
    return None, 0.0


# ===================== MAGNITUDE FAMILY =====================

def score_magnitude(features):
    scores = {
        "Volume": 0.0,
        "Brightness": 0.0,
        "Zoom": 0.0,
        "ScrollSpeed": 0.0,
        "PlaybackSpeed": 0.0
    }

    media = features["motion_score"]

    scores["PlaybackSpeed"] += media * 0.8
    scores["Volume"] += media * 0.6

    scores["ScrollSpeed"] += features["scrollbar_score"] * (1 - media) * 0.9

    scores["Zoom"] += features["text_density"] * (1 - media) * 0.6

    scores["Brightness"] += features["slider_score"] * 0.4

    return scores


# ===================== CURSOR FAMILY =====================

def score_cursor(features):
    scores = {
        "FreeMove": 0.0,
        "HoverFocus": 0.0,
        "PrecisionPoint": 0.0,
        "TextFieldFocus": 0.0
    }

    scores["FreeMove"] += (1 - features["edge_density"]) * 0.6
    scores["FreeMove"] += (1 - features["small_object_density"]) * 0.4

    scores["HoverFocus"] += features["small_object_density"] * 0.6
    scores["HoverFocus"] += features["edge_density"] * 0.3

    scores["PrecisionPoint"] += features["small_object_density"] * 0.8

    scores["TextFieldFocus"] += features["text_density"] * 0.7

    return scores


# ===================== GRAB & DRAG FAMILY =====================

def score_grab(features):
    scores = {
        "WindowDrag": 0.0,
        "ObjectMove": 0.0,
        "Resize": 0.0,
        "SelectionBox": 0.0
    }

    scores["WindowDrag"] += features["large_rect_score"] * 0.8
    scores["WindowDrag"] += features["border_edge_score"] * 0.4

    scores["ObjectMove"] += features["small_object_density"] * 0.7

    scores["Resize"] += features["border_edge_score"] * 0.8

    scores["SelectionBox"] += features["text_density"] * 0.6

    return scores


# ===================== ROTATION FAMILY =====================

def score_rotation(features):
    scores = {
        "KnobAdjust": 0.0,
        "ObjectRotate": 0.0
    }

    scores["KnobAdjust"] += features["circular_score"] * 0.8

    scores["ObjectRotate"] += features["edge_density"] * 0.4
    scores["ObjectRotate"] += features["large_rect_score"] * 0.3

    return scores


# ===================== NAVIGATION FAMILY =====================

def score_navigation(features):
    scores = {
        "TabSwitch": 0.0,
        "DesktopSwitch": 0.0,
        "SlideNavigate": 0.0,
        "TimelineJump": 0.0
    }

    scores["TabSwitch"] += features["small_object_density"] * 0.6
    scores["TabSwitch"] += features["edge_density"] * 0.3

    scores["DesktopSwitch"] += (1 - features["text_density"]) * 0.6

    scores["SlideNavigate"] += features["large_rect_score"] * 0.7

    scores["TimelineJump"] += features["slider_score"] * 0.7

    return scores


# ===================== SCROLL FAMILY =====================

def score_scroll(features):
    scores = {
        "VerticalScroll": 0.0
    }

    scores["VerticalScroll"] += features["scrollbar_score"] * 0.8
    scores["VerticalScroll"] += features["text_density"] * 0.3

    return scores


# ===================== MAIN INFERENCE =====================

def infer_intent(gesture_family, semantic_features):

    if gesture_family == "MAGNITUDE":
        scores = score_magnitude(semantic_features)

    elif gesture_family == "CURSOR":
        scores = score_cursor(semantic_features)

    elif gesture_family == "GRAB":
        scores = score_grab(semantic_features)

    elif gesture_family == "ROTATION":
        scores = score_rotation(semantic_features)

    elif gesture_family == "NAVIGATION":
        scores = score_navigation(semantic_features)

    elif gesture_family == "SCROLL":
        scores = score_scroll(semantic_features)

    else:
        return None, 0.0

    return choose_intent(scores)

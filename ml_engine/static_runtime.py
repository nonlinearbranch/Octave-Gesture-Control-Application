import json
import os
import shutil

import numpy as np
import torch
import torch.nn.functional as F

from ml_engine.static_model import StaticGestureModel
from utils.helpers import get_setting

try:
    import pandas as pd
except Exception:
    pd = None

model = None
num_classes = None

_label_map_cache = None
_label_map_mtime = 0.0
_centroids_cache = None
_centroids_mtime = 0.0


def _data_paths():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_root = os.environ.get("OCTAVE_DATA_DIR", "").strip() or base_dir
    if not os.path.isabs(data_root):
        data_root = os.path.abspath(os.path.join(base_dir, data_root))
    data_dir = os.path.join(data_root, "ml_engine", "data")
    template_data_dir = os.path.join(base_dir, "ml_engine", "data")
    label_map_path = os.path.join(data_dir, "label_map.json")
    csv_path = os.path.join(data_dir, "static_gestures.csv")

    template_map_path = os.path.join(template_data_dir, "label_map.json")
    if not os.path.exists(label_map_path) and os.path.exists(template_map_path):
        os.makedirs(os.path.dirname(label_map_path), exist_ok=True)
        shutil.copyfile(template_map_path, label_map_path)

    return label_map_path, csv_path


def _load_label_map(force=False):
    global _label_map_cache, _label_map_mtime
    label_map_path, _ = _data_paths()
    if not os.path.exists(label_map_path):
        _label_map_cache = {}
        _label_map_mtime = 0.0
        return {}

    mtime = os.path.getmtime(label_map_path)
    if not force and _label_map_cache is not None and mtime == _label_map_mtime:
        return _label_map_cache

    try:
        with open(label_map_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _label_map_cache = {str(k): str(v) for k, v in raw.items()}
    except Exception:
        _label_map_cache = {}
    _label_map_mtime = mtime
    return _label_map_cache


def _name_to_label_id(name):
    if not name:
        return -1
    needle = str(name).strip().lower()
    label_map = _load_label_map()
    for key, value in label_map.items():
        if str(value).strip().lower() == needle:
            try:
                return int(key)
            except Exception:
                return -1
    return -1


def _normalize_vec(v):
    arr = np.asarray(v, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm > 0:
        arr = arr / norm
    return arr


def _load_centroids(force=False):
    global _centroids_cache, _centroids_mtime
    _, csv_path = _data_paths()
    if pd is None or not os.path.exists(csv_path):
        _centroids_cache = {}
        _centroids_mtime = 0.0
        return {}

    mtime = os.path.getmtime(csv_path)
    if not force and _centroids_cache is not None and mtime == _centroids_mtime:
        return _centroids_cache

    try:
        data = pd.read_csv(csv_path, header=None)
        if data.empty:
            _centroids_cache = {}
            _centroids_mtime = mtime
            return {}

        X = data.iloc[:, :-1].to_numpy(dtype=np.float32)
        y = data.iloc[:, -1].to_numpy(dtype=np.int32)
        centroids = {}
        for label in sorted(set(y.tolist())):
            rows = X[y == label]
            if rows.size == 0:
                continue
            mean = rows.mean(axis=0)
            centroids[int(label)] = _normalize_vec(mean)
        _centroids_cache = centroids
    except Exception:
        _centroids_cache = {}

    _centroids_mtime = mtime
    return _centroids_cache


def _is_extended(hand, tip, pip):
    return hand.landmark[tip].y < hand.landmark[pip].y


def _distance(hand, a, b):
    la = hand.landmark[a]
    lb = hand.landmark[b]
    dx = la.x - lb.x
    dy = la.y - lb.y
    dz = la.z - lb.z
    return float((dx * dx + dy * dy + dz * dz) ** 0.5)


def _rule_based_name(hand):
    index = _is_extended(hand, 8, 6)
    middle = _is_extended(hand, 12, 10)
    ring = _is_extended(hand, 16, 14)
    pinky = _is_extended(hand, 20, 18)
    thumb = abs(hand.landmark[4].x - hand.landmark[3].x) > 0.04

    pinch = _distance(hand, 4, 8)
    v_gap = _distance(hand, 8, 12)

    if pinch < 0.045 and middle and ring and pinky:
        return "OK Sign"
    if thumb and not index and not middle and not ring and not pinky:
        return "Thumb"
    if index and middle and ring and not pinky:
        return "Three Fingers"
    if index and middle and not ring and not pinky and v_gap > 0.055:
        return "V Sign"
    if not index and not middle and not ring and not pinky and pinch > 0.055:
        return "Fist"
    return None


def init_static_model(model_path, input_size, classes):
    global model, num_classes
    num_classes = classes
    if not os.path.exists(model_path):
        model = None
        return
    try:
        loaded = StaticGestureModel(input_size, classes)
        loaded.load_state_dict(torch.load(model_path))
        loaded.eval()
        model = loaded
    except Exception:
        model = None


def _nn_inference(features, confidence_threshold):
    centroids = _load_centroids()
    if not centroids:
        return -1
    vec = _normalize_vec(features)
    best_label = -1
    best_score = -1.0
    for label, centroid in centroids.items():
        score = float(np.dot(vec, centroid))
        if score > best_score:
            best_score = score
            best_label = int(label)
    min_similarity = max(0.55, min(0.9, confidence_threshold * 0.78))
    if best_score < min_similarity:
        return -1
    return best_label


def run_static_inference(features, hand_landmarks=None):
    confidence_threshold = float(get_setting("static_confidence_threshold", 0.7))

    if model is not None:
        try:
            with torch.no_grad():
                x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
                out = model(x)
                probs = F.softmax(out, dim=1)
                conf, pred = torch.max(probs, dim=1)
                if conf.item() >= confidence_threshold:
                    return int(pred.item())
        except Exception:
            # If model inference fails, continue with fallbacks.
            pass

    if hand_landmarks is not None:
        name = _rule_based_name(hand_landmarks)
        label_id = _name_to_label_id(name)
        if label_id != -1:
            return label_id

    return _nn_inference(features, confidence_threshold)

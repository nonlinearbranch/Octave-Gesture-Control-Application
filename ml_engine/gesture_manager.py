import os
import json
import time
import pandas as pd

from utils.helpers import get_setting, load_gesture_mapping, save_gesture_mapping

try:
    from ml_engine.feature_extraction import extract_features
    from ml_engine.train_static import train_static_model
except Exception:
    from feature_extraction import extract_features
    from train_static import train_static_model


def _paths():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "ml_engine", "data", "static_gestures.csv")
    map_path = os.path.join(base_dir, "ml_engine", "data", "label_map.json")
    model_path = os.path.join(base_dir, "ml_engine", "data", "models", "static_model.pth")
    return csv_path, map_path, model_path


def load_label_map(map_path=None):
    _, default_map_path, _ = _paths()
    map_path = map_path or default_map_path
    if not os.path.exists(map_path):
        return {}
    with open(map_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): str(v) for k, v in data.items()}


def save_label_map(label_map, map_path=None):
    _, default_map_path, _ = _paths()
    map_path = map_path or default_map_path
    os.makedirs(os.path.dirname(map_path), exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=4)


def list_gestures(map_path=None):
    label_map = load_label_map(map_path)
    return [(int(k), label_map[k]) for k in sorted(label_map, key=lambda x: int(x))]


def _next_label(label_map):
    if not label_map:
        return 0
    return max(int(k) for k in label_map.keys()) + 1


def add_gesture(name, map_path=None):
    name = str(name).strip()
    if not name:
        raise ValueError("Gesture name required")
    label_map = load_label_map(map_path)
    if name.lower() in {v.lower() for v in label_map.values()}:
        for k, v in label_map.items():
            if v.lower() == name.lower():
                return int(k)
    label = _next_label(label_map)
    label_map[str(label)] = name
    save_label_map(label_map, map_path)
    return label


def rename_gesture(old_name_or_label, new_name, map_path=None):
    new_name = str(new_name).strip()
    if not new_name:
        raise ValueError("New name required")
    label_map = load_label_map(map_path)
    key = None
    if str(old_name_or_label).isdigit() and str(old_name_or_label) in label_map:
        key = str(old_name_or_label)
    else:
        needle = str(old_name_or_label).strip().lower()
        for k, v in label_map.items():
            if v.lower() == needle:
                key = k
                break
    if key is None:
        raise KeyError("Gesture not found")
    label_map[key] = new_name
    save_label_map(label_map, map_path)
    return int(key)


def _resolve_label(name_or_label, label_map):
    if str(name_or_label).isdigit() and str(name_or_label) in label_map:
        return int(name_or_label)
    needle = str(name_or_label).strip().lower()
    for k, v in label_map.items():
        if v.lower() == needle:
            return int(k)
    return None


def normalize_labels(csv_path=None, map_path=None):
    default_csv, default_map, _ = _paths()
    csv_path = csv_path or default_csv
    map_path = map_path or default_map

    label_map = load_label_map(map_path)
    if not label_map:
        save_label_map({}, map_path)
        if os.path.exists(csv_path):
            pd.DataFrame().to_csv(csv_path, index=False, header=False)
        return {}

    old_labels = sorted(int(k) for k in label_map.keys())
    remap = {old: new for new, old in enumerate(old_labels)}
    new_map = {str(remap[int(k)]): v for k, v in label_map.items()}
    save_label_map(new_map, map_path)

    if os.path.exists(csv_path):
        data = pd.read_csv(csv_path, header=None)
        if not data.empty:
            y = data.iloc[:, -1].astype(int)
            data = data[y.isin(old_labels)]
            if not data.empty:
                data.iloc[:, -1] = data.iloc[:, -1].astype(int).map(remap)
            data.to_csv(csv_path, index=False, header=False)
    return new_map


def delete_gesture(name_or_label, csv_path=None, map_path=None):
    default_csv, default_map, _ = _paths()
    csv_path = csv_path or default_csv
    map_path = map_path or default_map

    label_map = load_label_map(map_path)
    label = _resolve_label(name_or_label, label_map)
    if label is None:
        raise KeyError("Gesture not found")

    del label_map[str(label)]
    save_label_map(label_map, map_path)

    if os.path.exists(csv_path):
        data = pd.read_csv(csv_path, header=None)
        if not data.empty:
            data = data[data.iloc[:, -1].astype(int) != label]
            data.to_csv(csv_path, index=False, header=False)

    normalize_labels(csv_path=csv_path, map_path=map_path)
    return label


def collect_samples_for_label(label, target_samples=None, capture_interval=None):
    import cv2
    import mediapipe as mp

    if target_samples is None:
        target_samples = int(get_setting("dataset_target_samples", 320))
    if capture_interval is None:
        capture_interval = float(get_setting("dataset_capture_interval_sec", 0.09))

    csv_path, _, _ = _paths()
    rows = []
    samples = 0
    last_capture_time = 0

    mp_hands = mp.solutions.hands
    max_hands = int(get_setting("max_hands", 2))
    hands = mp_hands.Hands(max_num_hands=max_hands)
    cap = cv2.VideoCapture(0)

    while samples < target_samples:
        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)
        now = time.time()

        if result.multi_hand_landmarks:
            hand = result.multi_hand_landmarks[0]
            if now - last_capture_time >= capture_interval:
                feat = extract_features(hand)
                rows.append(list(feat) + [int(label)])
                samples += 1
                last_capture_time = now

            cv2.putText(
                frame,
                f"Collecting {samples}/{target_samples}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

        cv2.imshow("Collecting Gesture Data", frame)
        if cv2.waitKey(1) & 255 == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

    df = pd.DataFrame(rows)
    if os.path.exists(csv_path):
        df.to_csv(csv_path, mode="a", index=False, header=False)
    else:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        df.to_csv(csv_path, index=False, header=False)

    return samples


def retrain_static_model():
    csv_path, _, model_path = _paths()
    normalize_labels(csv_path=csv_path)
    return train_static_model(csv_path=csv_path, model_path=model_path)


def set_static_action(gesture_name, action):
    gesture_name = str(gesture_name).strip()
    if not gesture_name:
        raise ValueError("gesture_name required")
    mapping = load_gesture_mapping(force=True)
    mapping.setdefault("static_actions", {})
    mapping["static_actions"][gesture_name] = action
    save_gesture_mapping(mapping)
    return True


def delete_static_action(gesture_name):
    gesture_name = str(gesture_name).strip()
    mapping = load_gesture_mapping(force=True)
    mapping.setdefault("static_actions", {})
    if gesture_name in mapping["static_actions"]:
        del mapping["static_actions"][gesture_name]
        save_gesture_mapping(mapping)
    return True


def set_voice_action(phrase, action):
    phrase = str(phrase).strip().lower()
    if not phrase:
        raise ValueError("phrase required")
    mapping = load_gesture_mapping(force=True)
    mapping.setdefault("voice_actions", {})
    mapping["voice_actions"][phrase] = action
    save_gesture_mapping(mapping)
    return True


def delete_voice_action(phrase):
    phrase = str(phrase).strip().lower()
    mapping = load_gesture_mapping(force=True)
    mapping.setdefault("voice_actions", {})
    if phrase in mapping["voice_actions"]:
        del mapping["voice_actions"][phrase]
        save_gesture_mapping(mapping)
    return True

import cv2
import mediapipe as mp
import threading
import json
import time
import os
import shutil

from ml_engine.feature_extraction import extract_features
from ml_engine.static_runtime import init_static_model, run_static_inference

from intent_engine.intent_resolver import resolve_intent
from intent_engine.intent_resolver import execute_custom_action
from intent_engine.mode_manager import get_mode
from intent_engine.stability_filter import stable_gesture

from dynamic_engine.drs_gesture import detect_drs
from dynamic_engine.family_detector import DynamicFamilyDetector

from screen_engine.screen_capture import capture_resized
from screen_engine.semantic_extractor import extract_semantic_features
from intent_engine.context_engine.intent_adapter import get_active_intent, cycle_override
from utils.helpers import get_setting, write_runtime_state, append_engine_event
from api_engine.command_bridge import CommandBridge
from voice_engine.vosk_listener import VoskVoiceListener

running = True

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=int(get_setting("max_hands", 2)),
    model_complexity=int(get_setting("hand_model_complexity", 0)),
    min_detection_confidence=float(get_setting("hand_min_detection_confidence", 0.6)),
    min_tracking_confidence=float(get_setting("hand_min_tracking_confidence", 0.55))
)
draw = mp.solutions.drawing_utils
family_detector = DynamicFamilyDetector()
draw_landmarks = bool(get_setting("draw_landmarks", True))
command_bridge = CommandBridge()

last_semantic = None
last_time = 0
SEMANTIC_INTERVAL = float(get_setting("semantic_interval_sec", 0.4))
STATE_INTERVAL = float(get_setting("runtime_state_interval_sec", 0.2))
COMMAND_INTERVAL = float(get_setting("command_poll_interval_sec", 0.25))


base_dir = os.path.dirname(os.path.abspath(__file__))
data_root = os.environ.get("OCTAVE_DATA_DIR", "").strip() or base_dir
if not os.path.isabs(data_root):
    data_root = os.path.abspath(os.path.join(base_dir, data_root))

data_dir = os.path.join(data_root, "ml_engine", "data")
template_data_dir = os.path.join(base_dir, "ml_engine", "data")

label_map_path = os.path.join(data_dir, "label_map.json")
model_path = os.path.join(data_dir, "models", "static_model.pth")
template_label_map_path = os.path.join(template_data_dir, "label_map.json")
if not os.path.exists(label_map_path) and os.path.exists(template_label_map_path):
    os.makedirs(os.path.dirname(label_map_path), exist_ok=True)
    shutil.copyfile(template_label_map_path, label_map_path)

voice_model_dir = str(get_setting("voice_model_dir", "vosk-model-small-en-us-0.15"))
voice_model_data_path = os.path.join(data_dir, voice_model_dir)
voice_model_template_path = os.path.join(template_data_dir, voice_model_dir)
vosk_model_path = (
    voice_model_data_path
    if os.path.exists(voice_model_data_path)
    else voice_model_template_path
)
MODEL_RELOAD_INTERVAL = float(get_setting("model_reload_interval_sec", 2.0))

label_map = {}


def load_label_map():
    global label_map
    try:
        with open(label_map_path, "r", encoding="utf-8") as f:
            label_map = json.load(f)
    except Exception:
        label_map = {}


load_label_map()


def get_gesture_name(gesture_id):
    return label_map.get(str(gesture_id), "UNKNOWN")


def detection_loop():
    global running, last_semantic, last_time

    cv2.setUseOptimized(True)
    cap = cv2.VideoCapture(int(get_setting("camera_index", 0)))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(get_setting("camera_width", 960)))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(get_setting("camera_height", 540)))

    last_family = None
    last_intent = None
    last_conf = 0.0
    last_static = None
    last_voice_phrase = None
    last_state_write = 0.0
    prev_t = time.time()
    fps = 0.0
    last_reload_check = 0.0
    last_command_poll = 0.0
    last_label_mtime = os.path.getmtime(label_map_path) if os.path.exists(label_map_path) else 0.0
    last_model_mtime = os.path.getmtime(model_path) if os.path.exists(model_path) else 0.0
    voice_listener = VoskVoiceListener(vosk_model_path)
    voice_listener.start()
    append_engine_event("engine_started", {"voice_model_path": vosk_model_path})

    while running:
        ret, frame = cap.read()
        if not ret:
            continue

        now_t = time.time()
        dt = max(1e-6, now_t - prev_t)
        prev_t = now_t
        fps = 0.88 * fps + 0.12 * (1.0 / dt)

        if now_t - last_reload_check >= MODEL_RELOAD_INTERVAL:
            current_label_mtime = os.path.getmtime(label_map_path) if os.path.exists(label_map_path) else 0.0
            current_model_mtime = os.path.getmtime(model_path) if os.path.exists(model_path) else 0.0
            if current_label_mtime != last_label_mtime:
                load_label_map()
                last_label_mtime = current_label_mtime
            if current_model_mtime != last_model_mtime and label_map:
                try:
                    init_static_model(model_path, 63, len(label_map))
                    last_model_mtime = current_model_mtime
                except Exception:
                    pass
            last_reload_check = now_t

        if now_t - last_command_poll >= COMMAND_INTERVAL:
            command_bridge.poll_once()
            last_command_poll = now_t

        voice_event = voice_listener.poll_event()
        if voice_event:
            executed = execute_custom_action(voice_event.get("action"))
            last_voice_phrase = voice_event.get("phrase")
            append_engine_event("voice_action", {
                "phrase": voice_event.get("phrase"),
                "executed": bool(executed)
            })

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        result = hands.process(rgb)

        # ---------- THROTTLED SEMANTIC ANALYSIS ----------
        now = time.time()

        if last_semantic is None or now - last_time > SEMANTIC_INTERVAL:
            screen_small = capture_resized()
            last_semantic = extract_semantic_features(screen_small)
            last_time = now

        semantic_features = last_semantic

        gesture_name = None
        family = None
        intent = None
        confidence = 0.0

        if result.multi_hand_landmarks:
            hands_list = result.multi_hand_landmarks

            if len(hands_list) == 2:
                if detect_drs(hands_list[0], hands_list[1]):
                    resolve_intent(None, gesture_name="DRS T-Frame")

            hand = hands_list[0]

            features = extract_features(hand)
            gesture_id = run_static_inference(features, hand)

            if gesture_id != -1:
                raw = get_gesture_name(gesture_id)
                gesture_name = stable_gesture(raw)

            family = family_detector.detect(hand)
            if family:
                intent, confidence = get_active_intent(family, semantic_features)

            if gesture_name == "Three Fingers" and family:
                cycle_override(family, intent)
                intent, confidence = get_active_intent(family, semantic_features)

            if intent:
                print("Intent:", intent, "Conf:", round(confidence, 2))
                resolve_intent(hand, gesture_name=gesture_name, family=family, intent=intent)
            else:
                resolve_intent(hand, gesture_name=gesture_name)

            if draw_landmarks:
                for h in hands_list:
                    draw.draw_landmarks(frame, h, mp_hands.HAND_CONNECTIONS)

        if family:
            last_family = family
        if intent:
            last_intent = intent
            last_conf = confidence
        if gesture_name:
            last_static = gesture_name

        if now_t - last_state_write >= STATE_INTERVAL:
            write_runtime_state({
                "dynamic_family": last_family,
                "dynamic_intent": last_intent,
                "confidence": round(float(last_conf), 4),
                "static_gesture": last_static,
                "static_label_map": label_map,
                "voice_phrase": last_voice_phrase,
                "mode": get_mode(),
                "fps": round(float(fps), 2),
                "semantic_features": semantic_features or {}
            })
            last_state_write = now_t

        cv2.putText(
            frame,
            f"Mode: {get_mode()}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )
        cv2.putText(
            frame,
            f"Family: {last_family or '-'}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2
        )
        cv2.putText(
            frame,
            f"Intent: {last_intent or '-'} ({round(last_conf, 2)})",
            (20, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 220, 0),
            2
        )
        cv2.putText(
            frame,
            f"Static: {last_static or '-'}",
            (20, 148),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 180, 255),
            2
        )
        cv2.putText(
            frame,
            f"FPS: {int(fps)}",
            (20, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (160, 255, 160),
            2
        )

        cv2.imshow("Gesture System", frame)

        if cv2.waitKey(1) & 255 == 27:
            running = False

    cap.release()
    voice_listener.stop()
    append_engine_event("engine_stopped", {})
    cv2.destroyAllWindows()


def main():
    if label_map:
        init_static_model(model_path, 63, len(label_map))

    t = threading.Thread(target=detection_loop)
    t.start()
    t.join()


if __name__ == "__main__":
    main()

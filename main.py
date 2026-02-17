import cv2
import mediapipe as mp
import threading
import json
import time

from ml_engine.feature_extraction import extract_features
from ml_engine.static_runtime import init_static_model, run_static_inference

from intent_engine.intent_resolver import resolve_intent
from intent_engine.mode_manager import get_mode
from intent_engine.stability_filter import stable_gesture

from dynamic_engine.drs_gesture import detect_drs

from screen_engine.screen_capture import capture_resized
from screen_engine.semantic_extractor import extract_semantic_features
from intent_engine.context_engine.intent_adapter import get_active_intent, set_override

running = True

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2)
draw = mp.solutions.drawing_utils

last_semantic = None
last_time = 0
SEMANTIC_INTERVAL = 0.40


with open("ml_engine/data/label_map.json", "r") as f:
    label_map = json.load(f)


def get_gesture_name(gesture_id):
    return label_map.get(str(gesture_id), "UNKNOWN")


def detection_loop():
    global running, last_semantic, last_time

    cap = cv2.VideoCapture(0)

    last_family = None

    while running:
        ret, frame = cap.read()
        if not ret:
            continue

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

        if result.multi_hand_landmarks:

            hands_list = result.multi_hand_landmarks

            # -------- DRS POWER GESTURE --------
            if len(hands_list) == 2:
                if detect_drs(hands_list[0], hands_list[1]):
                    resolve_intent(None, "DRS T-Frame")

            # -------- STATIC ML --------
            hand = hands_list[0]

            features = extract_features(hand)
            gesture_id = run_static_inference(features)

            if gesture_id != -1:
                raw = get_gesture_name(gesture_id)
                gesture_name = stable_gesture(raw)

            # -------- MANUAL OVERRIDE --------
            if gesture_name == "Three Fingers" and last_family:
                next_map = {
                    "Volume": "Brightness",
                    "Brightness": "Zoom",
                    "Zoom": "ScrollSpeed",
                    "ScrollSpeed": "PlaybackSpeed",
                    "PlaybackSpeed": "Volume"
                }
                set_override(next_map[last_family])

            # -------- DYNAMIC FAMILY DETECTION (TEMP FIX) --------
            # TODO: later replace with real family detection logic
            last_family = "MAGNITUDE"

            # -------- CONTEXTUAL INTENT --------
            intent, confidence = get_active_intent(last_family, semantic_features)

            if intent:
                print("Intent:", intent, "Conf:", round(confidence, 2))
                resolve_intent(hand, intent)

            for h in hands_list:
                draw.draw_landmarks(frame, h, mp_hands.HAND_CONNECTIONS)

        cv2.putText(
            frame,
            f"Mode: {get_mode()}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        cv2.imshow("Gesture System", frame)

        if cv2.waitKey(1) & 255 == 27:
            running = False

    cap.release()
    cv2.destroyAllWindows()


def main():
    init_static_model(
        "ml_engine/data/models/static_model.pth",
        63,
        len(label_map)
    )

    t = threading.Thread(target=detection_loop)
    t.start()
    t.join()


if __name__ == "__main__":
    main()

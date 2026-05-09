from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from pathlib import Path
from typing import Literal

import cv2
import mediapipe as mp

from ml.feature_extraction import extract_features


TargetName = Literal["default", "custom"]
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
STATIC_DIR = DATA_DIR / "static"
DYNAMIC_DIR = DATA_DIR / "dynamic"


def sanitize_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return sanitized[:128].strip("_.-") or "gesture"


def load_gesture_mapping(target: TargetName) -> dict[str, dict[str, dict[str, str]]]:
    config_path = CONFIG_DIR / ("default_mapping.json" if target == "default" else "user_mapping.json")
    if not config_path.exists():
        raise FileNotFoundError(f"Gesture config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    if not isinstance(config, dict):
        raise ValueError(f"Invalid gesture config structure: {config_path}")

    return config


def gesture_labels(gesture_type: str, target: TargetName) -> list[str]:
    mapping = load_gesture_mapping(target)
    labels = []
    entries = mapping.get(gesture_type, {})
    if not isinstance(entries, dict):
        return labels

    sorted_items = sorted(entries.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else item[0])
    for _, item in sorted_items:
        if isinstance(item, dict) and item.get("name"):
            labels.append(str(item[ "name"]))
        else:
            labels.append(str(item))
    return labels


def ensure_data_folder(data_type: str, target: TargetName) -> Path:
    folder = (STATIC_DIR if data_type == "static" else DYNAMIC_DIR) / target
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def countdown(cap: cv2.VideoCapture, window_name: str, seconds: int = 3) -> bool:
    start = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        elapsed = time.time() - start
        remaining = seconds - int(elapsed)
        if remaining < 0:
            return True

        frame = cv2.flip(frame, 1)
        cv2.putText(
            frame,
            f"Recording starts in {remaining}...",
            (30, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(window_name, frame)
        key = cv2.waitKey(100) & 0xFF
        if key == 27:
            return False


def collect_static_frames(gesture: str, target: TargetName, capture_count: int = 300) -> int:
    window_name = "Gesture Collector"
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Unable to open camera")

    hands = mp.solutions.hands.Hands(max_num_hands=2, min_detection_confidence=0.5)
    rows: list[list[float]] = []

    try:
        if not countdown(cap, window_name, 3):
            return 0

        captured = 0
        while captured < capture_count:
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            if results.multi_hand_landmarks:
                try:
                    features = extract_features(results.multi_hand_landmarks)
                    rows.append(list(features))
                    captured += 1
                except Exception:
                    pass

            cv2.putText(
                frame,
                f"{gesture}: {captured}/{capture_count}",
                (24, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()

    if captured <= 0:
        return 0

    output_path = ensure_data_folder("static", target) / f"{sanitize_filename(gesture)}.csv"
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)

    return captured


def collect_dynamic_frames(gesture: str, target: TargetName, sequences: int = 30, sequence_length: int = 30) -> int:
    window_name = "Gesture Collector"
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Unable to open camera")

    hands = mp.solutions.hands.Hands(max_num_hands=2, min_detection_confidence=0.5)
    rows: list[list[float]] = []

    try:
        if not countdown(cap, window_name, 3):
            return 0

        completed_sequences = 0
        frame_in_sequence = 0

        while completed_sequences < sequences:
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            if results.multi_hand_landmarks:
                try:
                    features = extract_features(results.multi_hand_landmarks)
                    rows.append(list(features))
                    frame_in_sequence += 1
                except Exception:
                    pass

            cv2.putText(
                frame,
                f"{gesture}: Seq {completed_sequences + 1}/{sequences} Frame {frame_in_sequence + 1}/{sequence_length}",
                (24, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break

            if frame_in_sequence >= sequence_length:
                completed_sequences += 1
                frame_in_sequence = 0
                
                # ==========================================
                # 🟢 THE LIVE-VIDEO COOLDOWN BLOCK 🟢
                # ==========================================
                if completed_sequences < sequences:
                    print(f"✅ Sequence {completed_sequences} captured. RESET your hand.")
                    
                    for countdown_val in range(2, 0, -1):
                        tick_start = time.time()
                        # Keep reading the camera for 1 second per countdown tick
                        while time.time() - tick_start < 1.0:
                            ret, c_frame = cap.read()
                            if not ret:
                                continue
                                
                            c_frame = cv2.flip(c_frame, 1)
                            cv2.putText(
                                c_frame,
                                f"RESET HAND! Next in {countdown_val}...",
                                (50, 100),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                1.2,
                                (0, 0, 255),
                                3,
                                cv2.LINE_AA,
                            )
                            cv2.imshow(window_name, c_frame)
                            cv2.waitKey(1)
                            
                    print(f"🎬 ACTION! Recording sequence {completed_sequences + 1} NOW!")
                # ==========================================

    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()

    if completed_sequences <= 0:
        return 0

    output_path = ensure_data_folder("dynamic", target) / f"{sanitize_filename(gesture)}.csv"
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)

    return completed_sequences * sequence_length


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect gesture landmark data for static or dynamic training.")
    parser.add_argument("--type", choices=["static", "dynamic"], required=True)
    parser.add_argument("--target", choices=["default", "custom"], required=True)
    args = parser.parse_args()

    labels = gesture_labels(args.type, args.target)
    if not labels:
        raise ValueError(f"No gesture labels found for type={args.type} target={args.target}")

    for gesture in labels:
        print(f"Ready to record '{gesture}'")
        input("Press ENTER to start recording. Press ESC in the preview window to abort.\n")
        if args.type == "static":
            captured = collect_static_frames(gesture, args.target, capture_count=300)
            print(f"Recorded {captured} frames for gesture '{gesture}'.")
        else:
            captured = collect_dynamic_frames(gesture, args.target, sequences=30, sequence_length=30)
            print(f"Recorded {captured} frames ({captured // 30} sequences) for gesture '{gesture}'.")

    print("Collection complete.")


if __name__ == "__main__":
    main()
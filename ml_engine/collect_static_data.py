import cv2
import mediapipe as mp
import pandas as pd
import os
import json
import time

from feature_extraction import extract_features

csv_path = "C:\\Users\\HP\\OneDrive\\RISHI GARG LAB\\GESTURE CONTROLLED SYSTEM(GF)\\ml_engine\\data\\static_gestures.csv"
map_path = "C:\\Users\\HP\\OneDrive\\RISHI GARG LAB\\GESTURE CONTROLLED SYSTEM(GF)\\ml_engine\\data\\label_map.json"

gesture_name = input("Enter gesture name: ")

if os.path.exists(map_path):
    with open(map_path, "r") as f:
        label_map = json.load(f)
else:
    label_map = {}

existing_labels = list(label_map.keys())
if len(existing_labels) == 0:
    label = 0
else:
    label = max([int(k) for k in existing_labels]) + 1

label_map[str(label)] = gesture_name

with open(map_path, "w") as f:
    json.dump(label_map, f, indent=4)

print("Gesture assigned label:", label)
print("Starting in 3 seconds...")
time.sleep(3)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2)

cap = cv2.VideoCapture(0)

samples = 0
rows = []
target_samples = 320

last_capture_time = 0
capture_interval = 0.09

while samples < target_samples:
    ret, frame = cap.read()
    if not ret:
        continue

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    result = hands.process(rgb)

    current_time = time.time()

    if result.multi_hand_landmarks:
        hand = result.multi_hand_landmarks[0]

        if current_time - last_capture_time >= capture_interval:
            features = extract_features(hand)

            row = list(features) + [label]
            rows.append(row)

            samples += 1
            last_capture_time = current_time

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
    df.to_csv(csv_path, index=False)

print("Saved", samples, "samples for", gesture_name)

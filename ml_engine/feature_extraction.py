import numpy as np


def extract_features(hand_landmarks):
    features = []

    wrist = hand_landmarks.landmark[0]

    for lm in hand_landmarks.landmark:
        x = lm.x - wrist.x
        y = lm.y - wrist.y
        z = lm.z - wrist.z

        features.extend([x, y, z])

    features = np.array(features)

    norm = np.linalg.norm(features)
    if norm != 0:
        features = features / norm

    return features

from __future__ import annotations

import math
from typing import Any

from ml.feature_extraction import extract_features
from ml.runtime.types import CameraFrame, HandDetection, NormalizedHandFrame

mp_error = ""
try:
    import mediapipe as mp
except ImportError as exc:  # pragma: no cover - depends on local runtime
    mp = None  # type: ignore[assignment]
    mp_error = str(exc)

cv2_error = ""
try:
    import cv2
except ImportError as exc:  # pragma: no cover - depends on local runtime
    cv2 = None  # type: ignore[assignment]
    cv2_error = str(exc)


class HandIngestion:
    """
    Run MediaPipe Hands on camera frames and convert the result into the shared
    runtime contracts used by the rest of Phase 1.

    This module deliberately sits between camera capture and gating. That gives
    us one place to answer the basic questions:
    - did we see a hand?
    - what were the 21 landmarks?
    - how confident was tracking?
    - do we have a lightweight hint that the pose looks like an open palm?

    It does not decide whether inference should run. That decision belongs to
    the gate pipeline. Keeping ingestion "honest but neutral" makes the system
    easier to reason about and test.
    """

    def __init__(self, min_detection_confidence: float = 0.5) -> None:
        self._min_detection_confidence = float(min_detection_confidence)
        self._last_error = ""
        self._last_hand_count = 0
        self._hands = self._create_hands(self._min_detection_confidence)

    def close(self) -> None:
        """Release MediaPipe resources if they were created successfully."""

        if self._hands is not None:
            try:
                self._hands.close()
            except Exception:
                # MediaPipe cleanup should never crash shutdown paths.
                pass
        self._hands = None

    def get_last_error(self) -> str:
        """Return the last ingestion-layer error message for logs or status UI."""

        return self._last_error

    def get_last_hand_count(self) -> int:
        """Return the hand count from the most recent MediaPipe result."""

        return self._last_hand_count

    def process_frame(self, frame: CameraFrame) -> HandDetection:
        """
        Run MediaPipe on a single camera frame and return a raw detection object.

        Returns:
            `HandDetection` for the given frame. The object is always returned
            even if no hand is present, because downstream gates should be able
            to see "empty frame" events explicitly instead of inferring them
            from missing values or exceptions.
        """

        self._last_hand_count = 0

        if mp is None:
            self._last_error = f"MediaPipe is not available: {mp_error}"
            return HandDetection(
                frame_id=frame.frame_id,
                timestamp=frame.timestamp,
                frame_bgr=frame.frame_bgr,
                landmarks_xyz=None,
                all_landmarks_xyz=None,
                tracking_confidence=0.0,
                hand_present=False,
                hand_count=0,
                bbox_norm=None,
                raw_gesture_hint=None,
            )

        if cv2 is None:
            self._last_error = f"OpenCV is not available for color conversion: {cv2_error}"
            return HandDetection(
                frame_id=frame.frame_id,
                timestamp=frame.timestamp,
                frame_bgr=frame.frame_bgr,
                landmarks_xyz=None,
                all_landmarks_xyz=None,
                tracking_confidence=0.0,
                hand_present=False,
                hand_count=0,
                bbox_norm=None,
                raw_gesture_hint=None,
            )

        if self._hands is None:
            self._last_error = "MediaPipe Hands is not initialized."
            return HandDetection(
                frame_id=frame.frame_id,
                timestamp=frame.timestamp,
                frame_bgr=frame.frame_bgr,
                landmarks_xyz=None,
                all_landmarks_xyz=None,
                tracking_confidence=0.0,
                hand_present=False,
                hand_count=0,
                bbox_norm=None,
                raw_gesture_hint=None,
            )

        try:
            rgb_frame = cv2.cvtColor(frame.frame_bgr, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            result = self._hands.process(rgb_frame)
        except Exception as exc:
            self._last_error = f"MediaPipe processing failed: {exc}"
            return HandDetection(
                frame_id=frame.frame_id,
                timestamp=frame.timestamp,
                frame_bgr=frame.frame_bgr,
                landmarks_xyz=None,
                all_landmarks_xyz=None,
                tracking_confidence=0.0,
                hand_present=False,
                hand_count=0,
                bbox_norm=None,
                raw_gesture_hint=None,
            )

        all_landmarks_xyz = self._extract_all_landmarks(result)
        if all_landmarks_xyz is None:
            self._last_error = ""
            return HandDetection(
                frame_id=frame.frame_id,
                timestamp=frame.timestamp,
                frame_bgr=frame.frame_bgr,
                landmarks_xyz=None,
                all_landmarks_xyz=None,
                tracking_confidence=0.0,
                hand_present=False,
                hand_count=0,
                bbox_norm=None,
                raw_gesture_hint=None,
            )

        landmarks_xyz = all_landmarks_xyz[0]
        hand_count = len(all_landmarks_xyz)
        tracking_confidence = self._estimate_tracking_confidence(result)
        bbox_norm = self._compute_bbox(landmarks_xyz)
        raw_gesture_hint = self._infer_pair_gesture_hint(all_landmarks_xyz)
        self._last_error = ""

        return HandDetection(
            frame_id=frame.frame_id,
            timestamp=frame.timestamp,
            frame_bgr=frame.frame_bgr,
            landmarks_xyz=landmarks_xyz,
            all_landmarks_xyz=all_landmarks_xyz,
            tracking_confidence=tracking_confidence,
            hand_present=True,
            hand_count=hand_count,
            bbox_norm=bbox_norm,
            raw_gesture_hint=raw_gesture_hint,
        )

    def normalize_hand(self, detection: HandDetection) -> NormalizedHandFrame | None:
        """
        Convert a raw detection into the stable 63-feature representation used
        by the existing static model.

        Returns:
            `NormalizedHandFrame` when landmarks are present and valid;
            otherwise `None`.

        Why this returns `None` instead of raising:
        ingestion is part of a live frame loop. We want malformed or missing
        hand data to become a normal "not usable this frame" outcome so the
        gate layer can reset cleanly rather than crashing the service.
        """

        if not detection.hand_present or detection.landmarks_xyz is None:
            return None

        try:
            features = extract_features(detection.landmarks_xyz)
        except Exception as exc:
            self._last_error = f"Feature normalization failed: {exc}"
            return None

        normalized_features = [float(value) for value in features.tolist()]
        return NormalizedHandFrame(
            frame_id=detection.frame_id,
            timestamp=detection.timestamp,
            frame_bgr=detection.frame_bgr,
            landmarks_xyz=[[float(v) for v in point] for point in detection.landmarks_xyz],
            all_landmarks_xyz=[[ [float(v) for v in point] for point in hand ] for hand in detection.all_landmarks_xyz] if detection.all_landmarks_xyz else None,
            normalized_features=normalized_features,
            tracking_confidence=float(detection.tracking_confidence),
            hand_present=bool(detection.hand_present),
            hand_count=int(detection.hand_count),
            raw_gesture_hint=detection.raw_gesture_hint,
        )

    def _create_hands(self, min_detection_confidence: float) -> Any | None:
        """
        Create the MediaPipe Hands runtime.

        We keep this creation logic behind a helper so construction and failure
        handling stay localized. MediaPipe can fail because of environment or
        binary mismatches, and that should not ripple through the rest of the
        system as a confusing import-time crash.
        """

        if mp is None:
            return None

        try:
            return mp.solutions.hands.Hands(
                static_image_mode=False,
                model_complexity=0,
                max_num_hands=2,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=0.5,
            )
        except Exception as exc:
            self._last_error = f"Failed to initialize MediaPipe Hands: {exc}"
            return None

    def _extract_all_landmarks(self, mediapipe_result: Any) -> list[list[list[float]]] | None:
        """Extract each detected hand as 21 `[x, y, z]` triples."""

        multi_hand_landmarks = getattr(mediapipe_result, "multi_hand_landmarks", None)
        if not multi_hand_landmarks:
            self._last_hand_count = 0
            return None

        self._last_hand_count = len(multi_hand_landmarks)

        all_landmarks: list[list[list[float]]] = []
        for hand in multi_hand_landmarks:
            landmarks: list[list[float]] = []
            for landmark in hand.landmark:
                landmarks.append([float(landmark.x), float(landmark.y), float(landmark.z)])
            if len(landmarks) != 21:
                return None
            all_landmarks.append(landmarks)
        return all_landmarks

    def _estimate_tracking_confidence(self, mediapipe_result: Any) -> float:
        """
        Derive a usable confidence score from the MediaPipe result.

        MediaPipe Hands does not always expose one obvious "tracking confidence"
        field in the classic solutions API. In practice, the handedness
        classification score is often the most stable lightweight confidence-like
        signal available per result, so we use it as our gate input.

        If that score is absent, we fall back to 1.0 for "a hand was returned".
        This keeps the system functional across environments while still letting
        Gate 1 enforce a stricter threshold when score data exists.
        """

        multi_handedness = getattr(mediapipe_result, "multi_handedness", None)
        if not multi_handedness:
            return 1.0

        try:
            classification = multi_handedness[0].classification[0]
            return float(getattr(classification, "score", 1.0))
        except Exception:
            return 1.0

    def _compute_bbox(
        self,
        landmarks_xyz: list[list[float]],
    ) -> tuple[float, float, float, float] | None:
        """
        Compute a normalized `(min_x, min_y, width, height)` bounding box.

        This is useful for overlays and future centering guidance. We calculate
        it once in ingestion so later modules do not each re-scan the landmarks.
        """

        if len(landmarks_xyz) != 21:
            return None

        xs = [point[0] for point in landmarks_xyz]
        ys = [point[1] for point in landmarks_xyz]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        return (
            float(min_x),
            float(min_y),
            float(max_x - min_x),
            float(max_y - min_y),
        )

    def _infer_raw_gesture_hint(self, landmarks_xyz: list[list[float]]) -> str | None:
        """
        Return a lightweight geometric pose hint used only for the clutch gate.

        This is intentionally not a general-purpose classifier. We only need a
        cheap answer to one question: "does this look enough like an open palm
        to count toward clutch hold?"

        This version uses a simple 2D Euclidean-distance heuristic because
        distance from the wrist is much more stable under hand tilt and camera
        angle changes than Y-axis comparisons.

        The logic is intentionally narrow:
        - ignore the thumb entirely
        - only evaluate the four main fingers
        - for each finger, compare:
          wrist -> tip distance
          wrist -> PIP distance
        - if the tip is meaningfully farther from the wrist than the PIP, the
          finger is likely extended rather than folded

        For clutch activation we now want to be deliberately strict: the user
        asked for activation only when both hands are fully open, meaning all
        ten fingers are visible/open together. So for a *single* hand to count
        as OPEN_PALM here, all four main fingers plus the thumb must look
        extended in the same frame.

        The `0.85` multiplier stays intentionally tolerant of tiny landmark
        noise, but the voting rule is no longer tolerant. This is what blocks
        partial poses such as "three fingers" from being misread as a clutch
        candidate.
        """

        if len(landmarks_xyz) != 21:
            return None

        wrist_x = float(landmarks_xyz[0][0])
        wrist_y = float(landmarks_xyz[0][1])

        def wrist_distance_2d(point_index: int) -> float:
            point = landmarks_xyz[point_index]
            return float(math.hypot(float(point[0]) - wrist_x, float(point[1]) - wrist_y))

        finger_pairs = [
            (8, 6),    # index tip, index PIP
            (12, 10),  # middle tip, middle PIP
            (16, 14),  # ring tip, ring PIP
            (20, 18),  # pinky tip, pinky PIP
        ]

        extended_count = 0
        for tip_idx, pip_idx in finger_pairs:
            wrist_to_tip_distance = wrist_distance_2d(tip_idx)
            wrist_to_pip_distance = wrist_distance_2d(pip_idx)

            if wrist_to_tip_distance > (wrist_to_pip_distance * 0.85):
                extended_count += 1

        # Thumb handling is separated because its geometry is different from
        # the vertical fingers. We still use the same rotation-friendly wrist
        # distance idea, but compare tip (4) to the thumb IP joint (3). The
        # slight >1.0 margin keeps a bent thumb from qualifying as "fully open".
        thumb_tip_distance = wrist_distance_2d(4)
        thumb_ip_distance = wrist_distance_2d(3)
        thumb_extended = thumb_tip_distance > (thumb_ip_distance * 1.05)

        bbox = self._compute_bbox(landmarks_xyz)
        if bbox is None:
            return None

        _, _, width, height = bbox
        hand_spread_ok = width > 0.08 and height > 0.08

        if extended_count == 4 and thumb_extended and hand_spread_ok:
            return "OPEN_PALM"

        return None

    def _infer_pair_gesture_hint(self, all_landmarks_xyz: list[list[list[float]]]) -> str | None:
        """
        Return a two-hand clutch hint when both visible hands look open.
        """

        if not all_landmarks_xyz:
            return None

        hand_hints = [self._infer_raw_gesture_hint(hand) for hand in all_landmarks_xyz[:2]]
        if len(hand_hints) >= 2 and all(hint == "OPEN_PALM" for hint in hand_hints[:2]):
            return "OPEN_PALM_PAIR"
        if hand_hints and any(hint == "OPEN_PALM" for hint in hand_hints):
            return "OPEN_PALM"
        return None

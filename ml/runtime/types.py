from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CameraFrame:
    """
    A single frame captured from a camera device.

    We keep the frame object intentionally simple:
    - `frame_bgr` is the raw OpenCV frame in BGR format because that is the
      most common format produced by `cv2.VideoCapture.read()`.
    - `frame_rgb` is optional because not every downstream consumer needs an
      RGB copy. Keeping it optional avoids doing extra work too early.
    - `timestamp` uses a float so callers can store `time.monotonic()` values
      directly without conversion.
    """

    frame_bgr: Any
    frame_rgb: Any | None
    timestamp: float
    frame_id: int
    camera_index: int


@dataclass(slots=True)
class HandDetection:
    """
    Raw hand-tracking output for a single frame.

    This object is the boundary between camera capture and higher-level
    gesture logic. It contains the frame plus the tracking result so later
    stages can make decisions without reaching back into the camera layer.
    """

    frame_id: int
    timestamp: float
    frame_bgr: Any
    landmarks_xyz: list[list[float]] | None
    all_landmarks_xyz: list[list[list[float]]] | None
    tracking_confidence: float
    hand_present: bool
    hand_count: int
    bbox_norm: tuple[float, float, float, float] | None
    raw_gesture_hint: str | None


@dataclass(slots=True)
class NormalizedHandFrame:
    """
    A frame that successfully produced hand landmarks and normalized features.

    `normalized_features` is the stable contract for the existing static
    PyTorch model. Phase 1 is specifically trying not to break that path.
    """

    frame_id: int
    timestamp: float
    frame_bgr: Any
    landmarks_xyz: list[list[float]]
    all_landmarks_xyz: list[list[list[float]]] | None
    normalized_features: list[float]
    tracking_confidence: float
    hand_present: bool
    hand_count: int
    raw_gesture_hint: str | None


@dataclass(slots=True)
class GateDecision:
    """
    The combined outcome of Gate 1 and Gate 2 for a single frame.

    Keeping the individual gate results alongside the final `accepted` flag
    makes debugging much easier. The UI and logs can explain *why* a frame was
    blocked instead of only saying "nothing happened".
    """

    accepted: bool
    reason: str
    gate1_passed: bool
    gate2_passed: bool
    clutch_active: bool
    clutch_progress: int
    required_clutch_frames: int


@dataclass(slots=True)
class StaticInferenceResult:
    """
    The model's answer for a gated frame.

    `is_unknown` is explicit instead of relying on magic label names because
    downstream code should not need to guess whether a prediction was accepted.
    """

    label_idx: int
    label_name: str
    confidence: float
    is_unknown: bool


@dataclass(slots=True)
class DynamicInferenceResult:
    """
    The dynamic model's answer for a completed sequence window.

    Dynamic inference has the same high-level contract as static inference:
    downstream code should be told explicitly whether the result is trusted
    instead of inferring that from label names or confidence thresholds.
    """

    label_idx: int
    label_name: str
    confidence: float
    is_unknown: bool


@dataclass(slots=True)
class ClutchState:
    """
    Stateful hold-progress data for the Open Palm clutch gate.

    The clutch gate must remember what happened in previous frames. Putting the
    whole state in a single dataclass keeps that memory explicit and easy to
    pass around, log, or reset.
    """

    active: bool
    candidate_label: str | None
    hold_frames: int
    required_frames: int
    last_seen_frame_id: int | None


@dataclass(slots=True)
class PreviewState:
    """
    UI-facing state for overlay rendering and preview streaming.

    The preview layer should not need to know about gate internals or model
    objects. It only needs a plain summary of what the system wants the user to
    see right now.
    """

    camera_ready: bool
    hand_present: bool
    hand_count: int
    tracking_confidence: float
    gate1_passed: bool
    clutch_active: bool
    clutch_progress: int
    required_clutch_frames: int
    hint_text: str
    status_text: str
    inference_label: str | None

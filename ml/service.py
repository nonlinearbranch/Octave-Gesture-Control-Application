from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import traceback
import csv
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    import winsound
except ImportError:  # pragma: no cover - Windows-only helper
    winsound = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
VENV_SITE = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if (
    VENV_SITE.exists()
    and sys.version_info[:2] == (3, 10)
    and str(VENV_SITE) not in sys.path
):
    sys.path.insert(0, str(VENV_SITE))
VENDOR = ROOT / "vendor"
if VENDOR.exists() and str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

os.environ.setdefault("PYTHONNOUSERSITE", "1")

from ml.feature_extraction import diagnose_environment
from ml.runtime.camera_manager import CameraManager
from ml.runtime.dynamic_inference_runner import DynamicInferenceRunner, SequenceBuffer
from ml.runtime.gates import InferenceGatePipeline
from ml.runtime.hand_ingestion import (
    HandIngestion,
    mp as runtime_mediapipe,
    mp_error as runtime_mediapipe_error,
)
from ml.runtime.preview_overlay import PreviewOverlayRenderer
from ml.runtime.static_inference_runner import StaticInferenceRunner
from ml.runtime.priority_router import PriorityRouter
from ml.runtime.types import DynamicInferenceResult, PreviewState, StaticInferenceResult
from ml.training.train_dynamic import train_dynamic_model
from ml.training.train_static import train_static_model

cv2_error = ""
try:
    import cv2
except ImportError as exc:  # pragma: no cover - depends on local runtime
    cv2 = None  # type: ignore[assignment]
    cv2_error = str(exc)

np_error = ""
try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - depends on local runtime
    np = None  # type: ignore[assignment]
    np_error = str(exc)

vosk_error = ""
try:
    from vosk import KaldiRecognizer, Model as VoskModel
    import sounddevice as sd
except ImportError as exc:  # pragma: no cover - depends on local runtime
    KaldiRecognizer = None  # type: ignore[assignment]
    VoskModel = None  # type: ignore[assignment]
    sd = None  # type: ignore[assignment]
    vosk_error = str(exc)

try:
    from flask import Flask, Response
except ImportError:  # pragma: no cover - depends on local runtime
    Flask = None  # type: ignore[assignment]
    Response = None  # type: ignore[assignment]

HOST = "127.0.0.1"
PORT = 50555
STARTUP_TRACE = ROOT / "startup_trace.log"
CONFIG_DIR = ROOT / "config"
DEFAULT_MAPPING_PATH = CONFIG_DIR / "default_mapping.json"
USER_MAPPING_PATH = CONFIG_DIR / "user_mapping.json"
OVERRIDE_STATE_PATH = CONFIG_DIR / "override_state.json"
CUSTOM_STATIC_CSV_PATH = ROOT / "data" / "static" / "custom" / "samples.csv"
CUSTOM_DYNAMIC_DATA_DIR = ROOT / "data" / "dynamic" / "custom"
DEFAULT_STATIC_MODEL_PATH = ROOT / "models" / "static" / "default_model.pth"
CUSTOM_STATIC_MODEL_PATH = ROOT / "models" / "static" / "custom_model.pth"
DEFAULT_DYNAMIC_MODEL_PATH = ROOT / "models" / "dynamic" / "default_model.pth"
CUSTOM_DYNAMIC_MODEL_PATH = ROOT / "models" / "dynamic" / "custom_model.pth"


@dataclass(slots=True)
class InferenceResult:
    """
    A small internal result type used by the stabilizer/cooldown stage.

    This is intentionally narrower than the richer runtime dataclasses because
    the stabilizer only needs a label and a confidence value.
    """

    label: str
    confidence: float


class GestureStabilizer:
    """
    Confirmation filter for recognized gesture labels.

    Why this still exists in Phase 1:
    the new gate pipeline controls *whether* a frame may reach inference, but
    it does not replace the existing output confirmation policy. We still want
    to demand a few consistent model predictions before emitting a gesture over
    IPC, otherwise the runtime will feel twitchy.
    """

    def __init__(
        self,
        window_size: int = 5,
        min_confirmation_frames: int = 2,
        min_confidence: float = 0.85,
    ) -> None:
        self.window_size = int(window_size)
        self.min_confirmation_frames = int(min_confirmation_frames)
        self.min_confidence = float(min_confidence)
        self.history: list[str] = []

    def reset(self) -> None:
        """Clear stabilizer history on mode changes or hard tracking loss."""

        self.history.clear()

    def __call__(self, result: InferenceResult) -> InferenceResult:
        """
        Confirm only labels that appear consistently in the recent history.

        Unknown or low-confidence results are still pushed into history as
        UNKNOWN so that the stabilizer naturally cools off when tracking gets
        noisy.
        """

        if result.label == "UNKNOWN" or result.confidence < self.min_confidence:
            self.history.append("UNKNOWN")
            if len(self.history) > self.window_size:
                self.history.pop(0)
            return InferenceResult(label="UNKNOWN", confidence=result.confidence)

        self.history.append(result.label)
        if len(self.history) > self.window_size:
            self.history.pop(0)

        counts = {label: self.history.count(label) for label in set(self.history)}
        if counts.get(result.label, 0) >= self.min_confirmation_frames:
            return result

        return InferenceResult(label="UNKNOWN", confidence=result.confidence)


def resolve_vosk_model_dir() -> Path | None:
    candidates = [
        Path(os.environ.get("SPIDER_VOSK_MODEL_DIR", "")).expanduser()
        if "SPIDER_VOSK_MODEL_DIR" in os.environ
        else None,
        ROOT / "vosk_model",
        ROOT.parent / "vosk-model-small-en-us-0.15",
        ROOT.parent / "vosk-model-small-en-us-0.15" / "vosk-model-small-en-us-0.15",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


def describe_runtime() -> Dict[str, Any]:
    return {
        "python": sys.executable,
        "cv2": bool(cv2),
        "cv2_error": cv2_error,
        "numpy": bool(np),
        "numpy_error": np_error,
        "mediapipe": bool(runtime_mediapipe),
        "mediapipe_error": runtime_mediapipe_error,
        "vosk": bool(KaldiRecognizer and VoskModel and sd),
        "vosk_error": vosk_error,
        "venv_site": str(VENV_SITE) if VENV_SITE.exists() else "",
    }


def trace_startup(message: str) -> None:
    try:
        STARTUP_TRACE.parent.mkdir(parents=True, exist_ok=True)
        with STARTUP_TRACE.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def _load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _save_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _mapping_sections() -> tuple[dict[str, Any], dict[str, Any]]:
    default_mapping = _load_json_file(DEFAULT_MAPPING_PATH, default={})
    user_mapping = _load_json_file(USER_MAPPING_PATH, default={})
    if not isinstance(default_mapping, dict):
        default_mapping = {}
    if not isinstance(user_mapping, dict):
        user_mapping = {}
    return default_mapping, user_mapping


def _static_section(mapping: dict[str, Any]) -> dict[str, Any]:
    section = mapping.get("static", {})
    return section if isinstance(section, dict) else {}


def _dynamic_section(mapping: dict[str, Any]) -> dict[str, Any]:
    section = mapping.get("dynamic", {})
    return section if isinstance(section, dict) else {}


def _list_custom_static_gestures() -> list[tuple[int, str]]:
    _, user_mapping = _mapping_sections()
    static_mapping = _static_section(user_mapping)
    gestures: list[tuple[int, str]] = []
    for key in sorted(static_mapping, key=lambda item: int(item)):
        value = static_mapping[key]
        if isinstance(value, dict) and "name" in value:
            gestures.append((int(key), str(value.get("name", "")).strip()))
    return gestures


def _label_name_map(section: dict[str, Any]) -> dict[int, str]:
    return {
        int(key): str(value.get("name", "")).strip()
        for key, value in section.items()
        if isinstance(value, dict) and "name" in value
    }


def _merged_label_map(kind: str) -> dict[int, str]:
    default_mapping, user_mapping = _mapping_sections()
    if kind == "dynamic":
        merged = _label_name_map(_dynamic_section(default_mapping))
        merged.update(_label_name_map(_dynamic_section(user_mapping)))
        return merged

    merged = _label_name_map(_static_section(default_mapping))
    merged.update(_label_name_map(_static_section(user_mapping)))
    return merged


def _default_label_floor(kind: str) -> int:
    default_mapping, _ = _mapping_sections()
    if kind == "dynamic":
        label_map = _label_name_map(_dynamic_section(default_mapping))
    else:
        label_map = _label_name_map(_static_section(default_mapping))
    return max(label_map.keys(), default=-1)


def _load_runtime_static_labels() -> tuple[dict[int, str], str]:
    default_mapping, user_mapping = _mapping_sections()
    user_static = _static_section(user_mapping)
    if user_static and CUSTOM_STATIC_MODEL_PATH.exists():
        return _merged_label_map("static"), str(CUSTOM_STATIC_MODEL_PATH)
    return _label_name_map(_static_section(default_mapping)), str(DEFAULT_STATIC_MODEL_PATH)


def _load_runtime_dynamic_labels() -> tuple[dict[int, str], str]:
    default_mapping, user_mapping = _mapping_sections()
    user_dynamic = _dynamic_section(user_mapping)
    if user_dynamic and CUSTOM_DYNAMIC_MODEL_PATH.exists():
        return _merged_label_map("dynamic"), str(CUSTOM_DYNAMIC_MODEL_PATH)
    return _label_name_map(_dynamic_section(default_mapping)), str(DEFAULT_DYNAMIC_MODEL_PATH)


def _next_custom_static_label() -> int:
    gestures = _list_custom_static_gestures()
    if not gestures:
        return _default_label_floor("static") + 1
    return max(_default_label_floor("static"), max(label for label, _ in gestures)) + 1


def _add_custom_static_gesture(name: str, action: str = "Click") -> int:
    clean_name = str(name).strip()
    if not clean_name:
        raise ValueError("Gesture name required")
    clean_action = str(action).strip() or "Click"

    _, user_mapping = _mapping_sections()
    if not isinstance(user_mapping, dict) or not user_mapping:
        user_mapping = {"static": {}, "dynamic": {}}
    static_mapping = _static_section(user_mapping)

    for key, value in static_mapping.items():
        if isinstance(value, dict) and str(value.get("name", "")).strip().lower() == clean_name.lower():
            value["action"] = clean_action
            _save_json_file(USER_MAPPING_PATH, user_mapping)
            return int(key)

    label = _next_custom_static_label()
    static_mapping[str(label)] = {"name": clean_name, "action": clean_action}
    user_mapping["static"] = static_mapping
    if "dynamic" not in user_mapping or not isinstance(user_mapping.get("dynamic"), dict):
        user_mapping["dynamic"] = {}
    _save_json_file(USER_MAPPING_PATH, user_mapping)
    return label


def _add_custom_dynamic_gesture(name: str, action: str = "Adjust") -> int:
    clean_name = str(name).strip()
    if not clean_name:
        raise ValueError("Gesture name required")
    clean_action = str(action).strip() or "Adjust"

    _, user_mapping = _mapping_sections()
    if not isinstance(user_mapping, dict) or not user_mapping:
        user_mapping = {"static": {}, "dynamic": {}}
    dynamic_mapping = _dynamic_section(user_mapping)

    for key, value in dynamic_mapping.items():
        if isinstance(value, dict) and str(value.get("name", "")).strip().lower() == clean_name.lower():
            value["action"] = clean_action
            _save_json_file(USER_MAPPING_PATH, user_mapping)
            return int(key)

    label = max(
        (int(key) for key in dynamic_mapping.keys()),
        default=_default_label_floor("dynamic"),
    ) + 1
    dynamic_mapping[str(label)] = {"name": clean_name, "action": clean_action}
    user_mapping["dynamic"] = dynamic_mapping
    if "static" not in user_mapping or not isinstance(user_mapping.get("static"), dict):
        user_mapping["static"] = {}
    _save_json_file(USER_MAPPING_PATH, user_mapping)
    return label


def _normalize_custom_static_labels() -> dict[str, str]:
    _, user_mapping = _mapping_sections()
    static_mapping = _static_section(user_mapping)
    if not static_mapping:
        _save_json_file(USER_MAPPING_PATH, {"static": {}, "dynamic": _dynamic_section(user_mapping)})
        if CUSTOM_STATIC_CSV_PATH.exists():
            CUSTOM_STATIC_CSV_PATH.write_text("", encoding="utf-8")
        return {}

    old_labels = sorted(int(key) for key in static_mapping.keys())
    start_label = _default_label_floor("static") + 1
    remap = {old: start_label + index for index, old in enumerate(old_labels)}
    new_static = {str(remap[int(key)]): value for key, value in static_mapping.items()}
    user_mapping["static"] = new_static
    if "dynamic" not in user_mapping or not isinstance(user_mapping.get("dynamic"), dict):
        user_mapping["dynamic"] = {}
    _save_json_file(USER_MAPPING_PATH, user_mapping)

    if CUSTOM_STATIC_CSV_PATH.exists():
        rows: list[list[str]] = []
        with CUSTOM_STATIC_CSV_PATH.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if not row:
                    continue
                label = int(float(row[-1]))
                if label in remap:
                    row[-1] = str(remap[label])
                    rows.append(row)
        with CUSTOM_STATIC_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)

    return {
        str(key): str(value.get("name", "")).strip()
        for key, value in new_static.items()
        if isinstance(value, dict)
    }


def _normalize_custom_dynamic_labels() -> dict[str, str]:
    _, user_mapping = _mapping_sections()
    dynamic_mapping = _dynamic_section(user_mapping)
    if not dynamic_mapping:
        if "static" not in user_mapping or not isinstance(user_mapping.get("static"), dict):
            user_mapping["static"] = {}
        user_mapping["dynamic"] = {}
        _save_json_file(USER_MAPPING_PATH, user_mapping)
        return {}

    old_labels = sorted(int(key) for key in dynamic_mapping.keys())
    start_label = _default_label_floor("dynamic") + 1
    remap = {old: start_label + index for index, old in enumerate(old_labels)}
    new_dynamic = {str(remap[int(key)]): value for key, value in dynamic_mapping.items()}
    user_mapping["dynamic"] = new_dynamic
    if "static" not in user_mapping or not isinstance(user_mapping.get("static"), dict):
        user_mapping["static"] = {}
    _save_json_file(USER_MAPPING_PATH, user_mapping)

    return {
        str(key): str(value.get("name", "")).strip()
        for key, value in new_dynamic.items()
        if isinstance(value, dict)
    }


def _delete_custom_static_gesture(name_or_label: str) -> int:
    _, user_mapping = _mapping_sections()
    static_mapping = _static_section(user_mapping)
    key_to_delete: str | None = None

    if str(name_or_label).isdigit() and str(name_or_label) in static_mapping:
        key_to_delete = str(name_or_label)
    else:
        needle = str(name_or_label).strip().lower()
        for key, value in static_mapping.items():
            if isinstance(value, dict) and str(value.get("name", "")).strip().lower() == needle:
                key_to_delete = key
                break

    if key_to_delete is None:
        raise KeyError("Gesture not found")

    label = int(key_to_delete)
    del static_mapping[key_to_delete]
    user_mapping["static"] = static_mapping
    if "dynamic" not in user_mapping or not isinstance(user_mapping.get("dynamic"), dict):
        user_mapping["dynamic"] = {}
    _save_json_file(USER_MAPPING_PATH, user_mapping)

    if CUSTOM_STATIC_CSV_PATH.exists():
        rows: list[list[str]] = []
        with CUSTOM_STATIC_CSV_PATH.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if row and int(float(row[-1])) != label:
                    rows.append(row)
        with CUSTOM_STATIC_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)

    _normalize_custom_static_labels()
    return label


def _retrain_custom_static_model(progress_cb: Any = None) -> dict[str, Any]:
    _normalize_custom_static_labels()
    result = train_static_model(
        target="custom",
        csv_path=str(CUSTOM_STATIC_CSV_PATH),
        model_path=str(CUSTOM_STATIC_MODEL_PATH),
        progress_cb=progress_cb,
    )
    merged_labels = _merged_label_map("static")
    result["labels"] = [merged_labels[key] for key in sorted(merged_labels)]
    return result


def _retrain_custom_dynamic_model() -> dict[str, Any]:
    _normalize_custom_dynamic_labels()
    result = train_dynamic_model(target="custom")
    merged_labels = _merged_label_map("dynamic")
    result["accuracy"] = result.get("val_accuracy", 0.0)
    result["labels"] = [merged_labels[key] for key in sorted(merged_labels)]
    return result


class MlService:
    def __init__(self) -> None:
        trace_startup("MlService.__init__ start")

        # --- RUNTIME STATE ---
        self._running = True
        self._client: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._model_lock = threading.Lock()
        self._state_lock = threading.Lock()

        self._status: Dict[str, Any] = {"state": "starting"}
        self._interaction_mode = "HAND"
        # Camera index 0 is the built-in/default webcam. Change this to 1 when
        # diagnosing a second camera or OBS Virtual Camera input.
        self._camera_index = 0
        self._voice_input_index = -1
        # Keep the default moderate. Very low thresholds make MediaPipe work
        # harder on weak frames and can make the preview feel unstable.
        self._hand_min_detection_confidence = 0.5
        self._voice_phrase_cooldown_sec = 0.5
        self._camera_state = "idle"
        self._mic_state = "idle"

        self._labels: dict[int, str] = {}
        self._gesture_stabilizer = GestureStabilizer(min_confidence=0.72)
        self._last_action_time = 0.0
        self._action_cooldown_sec = 1.5
        self._last_action_label: str | None = None
        self._last_voice_emit = 0.0
        self._send_fail_count = 0
        self._send_fail_max = 5
        self._last_tracking_status_emit = 0.0
        self._last_no_hand_debug_print = 0.0
        self._tracking_fail_count = 0
        self._camera_read_fail_count = 0
        self._hand_present_prev = False
        self._clutch_active_prev = False
        self._clutch_last_activity_at = 0.0
        self._clutch_idle_timeout_sec = 2.5
        # Give the user enough time to arm the system and then naturally move
        # into the intended gesture without feeling rushed. Around 25 seconds
        # keeps the clutch deliberate without forcing constant re-arming.
        self._clutch_session_duration_sec = 25.0
        self._clutch_session_expires_at = 0.0
        self._clutch_session_armed = False
        self._continuous_seen_at = 0.0
        self._active_continuous_label: str | None = None
        self._continuous_smoothed_value = 0.0
        self._continuous_prev_index_y: float | None = None
        self._dynamic_capture_active = False
        self._dynamic_frames: list[list[float]] = []
        self._dynamic_last_motion_at = 0.0
        self._dynamic_motion_history: deque[float] = deque(maxlen=6)
        self._dynamic_prev_wrist: tuple[float, float] | None = None
        self._dynamic_motion_threshold = 0.020
        self._dynamic_idle_timeout_sec = 0.14
        self._dynamic_min_frames = 8

        # --- PHASE 1 COMPONENTS ---
        self._camera_manager = CameraManager(camera_index=self._camera_index, width=640, height=480)
        self._hand_ingestion = HandIngestion(
            min_detection_confidence=self._hand_min_detection_confidence
        )
        self._gate_pipeline = InferenceGatePipeline(
            min_confidence=0.75,
            required_hold_frames=1,
        )
        self._preview_renderer = PreviewOverlayRenderer()
        self._static_runner: StaticInferenceRunner | None = None
        self._sequence_buffer = SequenceBuffer()
        self._dynamic_runner = DynamicInferenceRunner()
        self._router = PriorityRouter()
        self._load_runtime_model()
        trace_startup("phase1 components ready")

        # --- PREVIEW STATE ---
        self._latest_frame_jpeg: bytes | None = None
        self._latest_frame_lock = threading.Lock()

        # --- RECORDING/TRAINING STATE ---
        self._recording_label_name = ""
        self._recording_samples = 0
        self._recording_target_samples = 320
        self._recording_capture_interval = 0.05
        self._last_capture_time = 0.0
        self._recording_buffer: list[list[float]] = []
        self._recording_label_idx: int | None = None
        self._recording_gesture_type = "static"
        self._pending_train_type = "static"

        self._preview_thread: Optional[threading.Thread] = None
        self._voice_thread: Optional[threading.Thread] = None
        self._training_thread: Optional[threading.Thread] = None
        self._pipeline_thread: Optional[threading.Thread] = None

    # ---------------------------------------------------------------------
    # Model and label management
    # ---------------------------------------------------------------------
    def _load_runtime_model(self) -> None:
        """
        Refresh the runtime label map and static model wrapper.

        This is used both at startup and after retraining. The service remains
        the orchestrator; the actual model loading work lives in
        `StaticInferenceRunner`.
        """

        self._labels, model_path = _load_runtime_static_labels()
        dynamic_labels, dynamic_model_path = _load_runtime_dynamic_labels()

        if self._static_runner is None:
                self._static_runner = StaticInferenceRunner(
                model_path=model_path,
                label_map=self._labels,
                input_size=126,
                confidence_threshold=0.72,
            )
        else:
            self._static_runner.reload(model_path=model_path, label_map=self._labels)

        self._dynamic_runner.reload(
            label_map=dynamic_labels,
            model_path=dynamic_model_path,
        )

    def _available_labels(self) -> list[str]:
        return sorted(list(self._labels.values()))

    # ---------------------------------------------------------------------
    # IPC and status helpers
    # ---------------------------------------------------------------------
    def _send(self, payload: Dict[str, Any]) -> None:
        if self._client is None:
            return
        message = json.dumps(payload) + "\n"
        try:
            with self._send_lock:
                self._client.sendall(message.encode("utf-8"))
            self._send_fail_count = 0
        except OSError:
            self._send_fail_count += 1
            if self._send_fail_count >= self._send_fail_max:
                self._running = False

    def _set_status(self, **fields: Any) -> None:
        with self._state_lock:
            self._status.update(fields)
            payload = dict(self._status)
        payload["labels"] = self._available_labels()
        payload["mode"] = self._interaction_mode
        self._send({"type": "status", **payload})

    def _build_gesture_payload(
        self,
        label: str,
        confidence: float,
        normalized_hand: "NormalizedHandFrame" | None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": "gesture",
            "label": label,
            "class": label,
            "mode": self._interaction_mode,
            "confidence": confidence,
        }
        if normalized_hand is not None:
            payload["index_tip"] = {
                "x": float(normalized_hand.landmarks_xyz[8][0]),
                "y": float(normalized_hand.landmarks_xyz[8][1]),
            }
            payload["thumb_tip"] = {
                "x": float(normalized_hand.landmarks_xyz[4][0]),
                "y": float(normalized_hand.landmarks_xyz[4][1]),
            }
        return payload

    def _reset_clutch_session(self) -> None:
        """
        Reset all state that belongs to one live clutch episode.

        This is intentionally broader than just resetting the gate counter. The
        clutch now scopes one gesture session, so when that session ends we also
        clear any continuous-stream smoothing and any partial dynamic recording.
        """

        self._gesture_stabilizer.reset()
        self._gate_pipeline.reset()
        self._sequence_buffer.clear()
        self._clutch_active_prev = False
        self._clutch_last_activity_at = 0.0
        self._clutch_session_expires_at = 0.0
        self._clutch_session_armed = False
        self._continuous_seen_at = 0.0
        self._active_continuous_label = None
        self._continuous_smoothed_value = 0.0
        self._continuous_prev_index_y = None
        self._dynamic_capture_active = False
        self._dynamic_frames = []
        self._dynamic_last_motion_at = 0.0
        self._dynamic_motion_history.clear()
        self._dynamic_prev_wrist = None
        self._camera_read_fail_count = 0

    def _is_clutch_session_active(self, now: float | None = None) -> bool:
        if not self._clutch_session_armed:
            return False
        current_time = now if now is not None else time.monotonic()
        return current_time < self._clutch_session_expires_at

    def _measure_motion(self, normalized_hand: "NormalizedHandFrame" | None) -> float:
        if normalized_hand is None or not normalized_hand.landmarks_xyz:
            self._dynamic_prev_wrist = None
            self._dynamic_motion_history.clear()
            return 0.0

        wrist_x, wrist_y = normalized_hand.landmarks_xyz[0][0], normalized_hand.landmarks_xyz[0][1]
        if self._dynamic_prev_wrist is None:
            self._dynamic_prev_wrist = (wrist_x, wrist_y)
            self._dynamic_motion_history.append(0.0)
            return 0.0

        prev_x, prev_y = self._dynamic_prev_wrist
        self._dynamic_prev_wrist = (wrist_x, wrist_y)
        motion = ((wrist_x - prev_x) ** 2 + (wrist_y - prev_y) ** 2) ** 0.5
        self._dynamic_motion_history.append(float(motion))
        return max(self._dynamic_motion_history, default=0.0)

    def _build_continuous_payload(
        self,
        label: str,
        action: str,
        normalized_hand: "NormalizedHandFrame" | None,
    ) -> Dict[str, Any] | None:
        if normalized_hand is None or len(normalized_hand.landmarks_xyz) < 21:
            return None

        index_tip = normalized_hand.landmarks_xyz[8]
        
        if label == "Two_Fingers_Extended":
            middle_tip = normalized_hand.landmarks_xyz[12]
            current_y = (index_tip[1] + middle_tip[1]) / 2.0
        else:
            current_y = index_tip[1]
            
        value = 0.0

        if self._continuous_prev_index_y is not None:
            # raw_delta is the per-frame Y movement in
            # normalised coordinates (0.0–1.0).  Positive means the hand moved
            # UP in screen space (y decreases for upward movement in MediaPipe).
            raw_delta = float(self._continuous_prev_index_y - current_y)

            # Lighter smoothing (0.4 / 0.6) keeps the slider responsive to
            # real-time hand movement instead of lagging behind.  The old
            # 0.72/0.28 split was so sluggish that moderate movements were
            # dampened below the C++ dead-zone threshold of 0.05.
            self._continuous_smoothed_value = (
                self._continuous_smoothed_value * 0.4
            ) + (raw_delta * 0.6)

            # Scale up to a range the C++ action executor can act on.  The
            # per-frame raw_delta from MediaPipe landmarks is typically
            # 0.005–0.03 for normal hand movement.  After smoothing, values
            # sit around 0.01–0.04 — well below the C++ dead-zone (0.05).
            # A 6× gain brings comfortable movements into the 0.06–0.24
            # range, producing 1-4 volume/scroll steps per frame.
            value = self._continuous_smoothed_value * 6.0
        self._continuous_prev_index_y = float(current_y)

        payload = self._build_gesture_payload(label, 1.0, normalized_hand)
        payload["action"] = action
        payload["value"] = float(value)
        return payload

    def _should_start_dynamic_episode(
        self,
        *,
        clutch_session_active: bool,
        gate1_passed: bool,
        normalized_hand: "NormalizedHandFrame" | None,
        is_recording: bool,
        motion_score: float,
        resolved_action: str,
    ) -> bool:
        """
        Decide whether post-clutch motion should claim the interaction for the
        dynamic pipeline.

        Dynamic gestures should not depend on static classification collapsing
        to UNKNOWN. Once the clutch is open and motion clearly starts, we lock
        into a bounded dynamic episode unless the current pose is an explicit
        continuous-control mode.
        """

        if not clutch_session_active or not gate1_passed:
            return False
        if normalized_hand is None or is_recording:
            return False
        if motion_score < self._dynamic_motion_threshold:
            return False
        if resolved_action.startswith("Mode:"):
            return False
        return True

    def _set_mode(self, mode: str) -> None:
        if self._recording_label_idx is not None:
            self._stop_recording(reason="recording_stopped_mode_change")

        self._reset_clutch_session()
        self._interaction_mode = mode
        self._send({"type": "mode", "mode": mode})

        if mode == "VOICE":
            self._close_camera()
        else:
            self._close_voice_stream()

    def _set_device_settings(self, payload: Dict[str, Any]) -> None:
        new_camera_index = self._camera_index
        try:
            if "camera_index" in payload:
                new_camera_index = int(payload.get("camera_index", self._camera_index))
        except (TypeError, ValueError):
            pass
        new_voice_input_index = self._voice_input_index
        try:
            if "voice_input_index" in payload:
                new_voice_input_index = int(payload.get("voice_input_index", self._voice_input_index))
        except (TypeError, ValueError):
            pass
        new_hand_min_detection_confidence = self._hand_min_detection_confidence
        try:
            value = float(
                payload.get(
                    "hand_min_detection_confidence",
                    self._hand_min_detection_confidence,
                )
            )
            new_hand_min_detection_confidence = max(0.3, min(0.85, value))
        except (TypeError, ValueError):
            pass
        new_voice_phrase_cooldown_sec = self._voice_phrase_cooldown_sec
        try:
            value = float(
                payload.get(
                    "voice_phrase_cooldown_sec",
                    self._voice_phrase_cooldown_sec,
                )
            )
            new_voice_phrase_cooldown_sec = max(0.1, min(5.0, value))
        except (TypeError, ValueError):
            pass

        camera_changed = new_camera_index != self._camera_index
        confidence_changed = (
            abs(new_hand_min_detection_confidence - self._hand_min_detection_confidence) > 1e-6
        )

        self._camera_index = new_camera_index
        self._voice_input_index = new_voice_input_index
        self._hand_min_detection_confidence = new_hand_min_detection_confidence
        self._voice_phrase_cooldown_sec = new_voice_phrase_cooldown_sec

        # Only rebuild the piece that actually changed. A sensitivity tweak
        # should not tear down the camera and risk breaking the live preview.
        if camera_changed:
            self._camera_manager.close()
            self._camera_manager = CameraManager(
                camera_index=self._camera_index,
                width=640,
                height=480,
            )
            self._camera_state = "closed"

        if confidence_changed:
            self._hand_ingestion.close()
            self._hand_ingestion = HandIngestion(
                min_detection_confidence=self._hand_min_detection_confidence
            )

        if camera_changed or confidence_changed:
            self._reset_clutch_session()

        self._send(
            {
                "type": "status",
                "state": self._status.get("state", "ready"),
                "message": "settings_applied",
                "mode": self._interaction_mode,
                "camera_index": self._camera_index,
                "voice_input_index": self._voice_input_index,
            }
        )

    # ---------------------------------------------------------------------
    # Camera and preview helpers
    # ---------------------------------------------------------------------
    def _ensure_camera_ready(self) -> bool:
        if self._camera_manager.is_open() and self._camera_manager.is_running():
            self._camera_state = "ready"
            return True

        self._camera_state = "opening"
        self._set_status(state=self._status.get("state", "ready"), message="opening_camera")

        # Phase 1 now boots the camera in the background. Starting the camera
        # manager here ensures the preview system and inference loop both have
        # access to a continuously refreshed frame source.
        if not self._camera_manager.start():
            self._camera_state = "error"
            self._set_status(
                state="error",
                message="camera_open_failed",
                error=self._camera_manager.get_last_error(),
            )
            return False

        self._camera_state = "ready"
        self._set_status(state=self._status.get("state", "ready"), message="camera_ready")
        return True

    def _close_camera(self) -> None:
        if self._camera_state == "closed" and not self._camera_manager.is_open():
            return
        self._camera_manager.close()
        self._camera_state = "closed"
        self._set_status(state=self._status.get("state", "ready"), message="camera_closed")

    def _close_voice_stream(self) -> None:
        if self._mic_state == "closed":
            return
        self._mic_state = "closed"
        self._set_status(state=self._status.get("state", "ready"), message="mic_closed")

    def _encode_preview_frame(self, frame: Any | None) -> None:
        if frame is None or cv2 is None:
            return

        preview_width = 960
        h, w = frame.shape[:2]
        if w > preview_width:
            ratio = preview_width / float(w)
            frame = cv2.resize(
                frame,
                (preview_width, int(h * ratio)),
                interpolation=cv2.INTER_AREA,
            )

        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 75],
        )
        if ok:
            with self._latest_frame_lock:
                self._latest_frame_jpeg = encoded.tobytes()

    def generate_preview_stream(self) -> Iterable[bytes]:
        def placeholder_frame() -> bytes | None:
            if cv2 is None or np is None:
                return None

            canvas = np.full((480, 640, 3), 30, dtype=np.uint8)
            status_text = str(self._status.get("message", "unknown"))
            error_text = str(self._status.get("error", "none"))

            cv2.putText(
                canvas,
                "OCTAVE Live Monitor",
                (140, 170),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (110, 160, 255),
                2,
            )
            cv2.putText(
                canvas,
                f"Status: {status_text}",
                (50, 250),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.72,
                (220, 220, 220),
                1,
            )
            cv2.putText(
                canvas,
                f"Error: {error_text}",
                (50, 290),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (170, 170, 170),
                1,
            )
            cv2.putText(
                canvas,
                f"Camera Index: {self._camera_index}",
                (50, 330),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (170, 170, 170),
                1,
            )
            cv2.putText(
                canvas,
                "Check camera access and service status",
                (120, 395),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (110, 110, 110),
                1,
            )
            ok, encoded = cv2.imencode(".jpg", canvas)
            return encoded.tobytes() if ok else None

        frame_interval = 1.0 / 12.0
        last_emit = time.time()

        while self._running:
            with self._latest_frame_lock:
                frame = self._latest_frame_jpeg

            if frame is None:
                frame = placeholder_frame()

            if frame is None:
                time.sleep(0.1)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )

            sleep_time = frame_interval - (time.time() - last_emit)
            if sleep_time > 0:
                time.sleep(sleep_time)
            last_emit = time.time()

    def _start_http_preview(self) -> None:
        if Flask is None:
            trace_startup("preview disabled: flask unavailable")
            return

        app = Flask(__name__)
        trace_startup("preview app created")

        @app.route("/video_feed")
        def video_feed() -> Response:
            return Response(
                self.generate_preview_stream(),
                mimetype="multipart/x-mixed-replace; boundary=frame",
            )

        @app.route("/training_feed")
        def training_feed() -> Response:
            return Response(
                self.generate_preview_stream(),
                mimetype="multipart/x-mixed-replace; boundary=frame",
            )

        trace_startup("preview server starting")
        app.run(host=HOST, port=5000, threaded=True, use_reloader=False)

    # ---------------------------------------------------------------------
    # Recording helpers
    # ---------------------------------------------------------------------
    def _flush_recording_buffer(self) -> int:
        if not self._recording_buffer:
            return 0

        rows = list(self._recording_buffer)
        self._recording_buffer.clear()

        CUSTOM_STATIC_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if CUSTOM_STATIC_CSV_PATH.exists() else "w"
        with CUSTOM_STATIC_CSV_PATH.open(mode, newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)

        return len(rows)

    def _flush_dynamic_recording_buffer(self) -> int:
        if not self._recording_buffer:
            return 0

        rows = [row[:126] for row in self._recording_buffer]
        self._recording_buffer.clear()
        usable_count = (len(rows) // 30) * 30
        rows = rows[:usable_count]
        if not rows:
            return 0

        safe_name = "".join(
            ch if ch.isalnum() or ch in {"_", "-"} else "_"
            for ch in self._recording_label_name.strip()
        ) or "CustomDynamic"
        CUSTOM_DYNAMIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = CUSTOM_DYNAMIC_DATA_DIR / f"{safe_name}.csv"
        mode = "a" if csv_path.exists() else "w"
        with csv_path.open(mode, newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)
        return len(rows)

    def _stop_recording(self, reason: str = "recording_stopped") -> None:
        was_recording = self._recording_label_idx is not None
        recording_type = self._recording_gesture_type
        self._recording_label_idx = None
        if was_recording:
            flushed = (
                self._flush_dynamic_recording_buffer()
                if recording_type == "dynamic"
                else self._flush_recording_buffer()
            )
            self._pending_train_type = recording_type
            self._set_status(
                state="ready",
                message=reason,
                active_label="",
                sample_count=self._recording_samples,
                target_samples=self._recording_target_samples,
                samples_saved=flushed,
            )

    def _record_sample_if_due(self, normalized_features: list[float]) -> None:
        """
        Append one training sample to the in-memory recording buffer if the
        capture interval has elapsed.

        Recording remains independent from the clutch gate. We want training to
        keep the current data collection behavior while still flowing through
        the new ingestion pipeline.
        """

        if self._recording_label_idx is None:
            return

        now = time.monotonic()
        if now - self._last_capture_time < self._recording_capture_interval:
            return

        self._last_capture_time = now
        if self._recording_gesture_type == "dynamic":
            self._recording_buffer.append(list(normalized_features))
        else:
            self._recording_buffer.append(
                list(normalized_features) + [int(self._recording_label_idx)]
            )
        self._recording_samples += 1

        if self._recording_samples >= self._recording_target_samples:
            self._stop_recording(reason="recording_complete")
            return

        self._set_status(
            state="recording",
            message=f"recording:{self._recording_label_name}",
            active_label=self._recording_label_name,
            sample_count=self._recording_samples,
            target_samples=self._recording_target_samples,
        )

    def _emit_tracking_status(
        self,
        message: str,
        *,
        error: str = "",
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        if not force and now - self._last_tracking_status_emit < 1.0:
            return
        self._last_tracking_status_emit = now

        fields: Dict[str, Any] = {
            "state": "recording"
            if self._recording_label_idx is not None
            else self._status.get("state", "ready"),
            "message": message,
            "sample_count": self._recording_samples,
            "target_samples": self._recording_target_samples,
            "active_label": self._recording_label_name,
            "tracking_fail_count": self._tracking_fail_count,
        }
        if error:
            fields["error"] = error
        self._set_status(**fields)

    # ---------------------------------------------------------------------
    # Preview state builder
    # ---------------------------------------------------------------------
    def _build_preview_state(
        self,
        *,
        camera_ready: bool,
        hand_present: bool,
        hand_count: int,
        tracking_confidence: float,
        gate1_passed: bool,
        clutch_active: bool,
        clutch_progress: int,
        required_clutch_frames: int,
        raw_gesture_hint: str | None,
        inference_result: StaticInferenceResult | None,
        is_recording: bool,
        clutch_seconds_remaining: float = 0.0,
    ) -> PreviewState:
        status_text = "Detecting hand"
        hint_text = "Move your hand into frame"
        inference_label: str | None = None

        if is_recording:
            status_text = "Recording"
            if not hand_present:
                hint_text = "Show your gesture clearly to collect samples"
            else:
                hint_text = (
                    f"Collecting {self._recording_samples}/{self._recording_target_samples}"
                )
        elif not camera_ready:
            status_text = "Camera unavailable"
            hint_text = "Check camera access and service status"
        elif clutch_active and not hand_present:
            status_text = "Clutch armed"
            hint_text = f"Clutch stays open. Raise one hand and make your gesture. {max(0, int(clutch_seconds_remaining))}s remaining"
        elif not hand_present:
            status_text = "Detecting hand"
            hint_text = "Move your hand into frame"
        elif not gate1_passed:
            status_text = "Confidence too low"
            hint_text = "Move closer and keep your hand clearly visible"
        elif not clutch_active:
            if raw_gesture_hint == "OPEN_PALM_PAIR":
                status_text = "Clutch activating"
                hint_text = "Both open palms detected. Gesture control is enabling now"
            elif raw_gesture_hint == "OPEN_PALM":
                status_text = "Show both open palms"
                hint_text = "One open palm is visible. Raise the second fully open palm to activate"
            else:
                status_text = "Show both open palms"
                hint_text = (
                    "Raise both hands with fully open palms to start gesture recognition"
                    if hand_count < 2
                    else "Open both palms fully so all ten fingers are visible"
                )
        elif inference_result is not None and not inference_result.is_unknown:
            status_text = "Gesture active"
            hint_text = "Gesture recognized and ready for dispatch"
            inference_label = inference_result.label_name
        else:
            status_text = "Clutch armed"
            hint_text = f"Make your gesture now with one hand. {max(0, int(clutch_seconds_remaining))}s remaining"

        return PreviewState(
            camera_ready=camera_ready,
            hand_present=hand_present,
            hand_count=int(hand_count),
            tracking_confidence=float(tracking_confidence),
            gate1_passed=gate1_passed,
            clutch_active=clutch_active,
            clutch_progress=int(clutch_progress),
            required_clutch_frames=int(required_clutch_frames),
            hint_text=hint_text,
            status_text=status_text,
            inference_label=inference_label,
        )

    # ---------------------------------------------------------------------
    # Main pipeline loop
    # ---------------------------------------------------------------------
    def run_pipeline(self) -> None:
        """
        Run the Phase 1 camera -> ingestion -> gating -> inference pipeline.

        This loop is intentionally independent from the TCP client connection.
        The preview feed should remain alive even if no mock/C++ backend is
        attached yet, and gesture IPC emission is already naturally guarded by
        `_send()` only transmitting when a client exists.
        """

        while self._running:
            now = time.monotonic()
            is_recording = self._recording_label_idx is not None

            if self._interaction_mode == "VOICE" and not is_recording:
                self._close_camera()
                time.sleep(0.4)
                continue

            if not self._ensure_camera_ready():
                time.sleep(0.4)
                continue

            # --- PIPELINE STAGE 1: CAMERA ---
            camera_frame = self._camera_manager.get_latest_frame()
            if camera_frame is None:
                camera_frame = self._camera_manager.read_frame()
            if camera_frame is None:
                self._camera_read_fail_count += 1
                self._tracking_fail_count += 1
                self._emit_tracking_status(
                    "camera_read_failed",
                    error=self._camera_manager.get_last_error(),
                    force=True,
                )
                if self._camera_read_fail_count >= 6:
                    self._camera_manager.close()
                    self._camera_state = "closed"
                    self._camera_read_fail_count = 0
                time.sleep(0.02)
                continue
            self._camera_read_fail_count = 0

            # --- PIPELINE STAGE 2: INGESTION ---
            detection = self._hand_ingestion.process_frame(camera_frame)
            hand_count = self._hand_ingestion.get_last_hand_count()
            if hand_count > 0:
                print(f"DEBUG: Found {hand_count} hands", flush=True)
            else:
                now = time.monotonic()
                if now - self._last_no_hand_debug_print >= 2.0:
                    self._last_no_hand_debug_print = now
                    print("DEBUG: No hands detected", flush=True)
            normalized_hand = self._hand_ingestion.normalize_hand(detection)

            if not detection.hand_present:
                self._tracking_fail_count += 1
                if is_recording:
                    self._emit_tracking_status("hand_not_detected")
            else:
                self._tracking_fail_count = 0

            # --- PIPELINE STAGE 3: BASE PREVIEW STATE ---
            # We create the UI-facing state object early, then enrich it after
            # the gates and inference stages. This keeps the main loop readable
            # and makes it obvious which facts come from which stage.
            preview_state = PreviewState(
                camera_ready=self._camera_manager.is_open(),
                hand_present=detection.hand_present,
                hand_count=int(detection.hand_count),
                tracking_confidence=float(detection.tracking_confidence),
                gate1_passed=False,
                clutch_active=self._is_clutch_session_active(now),
                clutch_progress=0,
                required_clutch_frames=1,
                hint_text="",
                status_text="",
                inference_label=None,
            )

            # Recording uses the same normalized features pipeline as inference,
            # but remains logically separate from clutch gating. That preserves
            # the existing training workflow while still benefiting from the new
            # ingestion cleanup.
            if is_recording and normalized_hand is not None:
                self._record_sample_if_due(normalized_hand.normalized_features)

            # --- PIPELINE STAGE 4: GATES ---
            gate_decision = self._gate_pipeline.evaluate(normalized_hand)
            if gate_decision.clutch_active and not self._is_clutch_session_active(now):
                self._clutch_session_armed = True
                self._clutch_session_expires_at = now + self._clutch_session_duration_sec
                self._clutch_last_activity_at = now
                self._play_clutch_activation_sound()
            clutch_session_active = self._is_clutch_session_active(now)
            if self._clutch_session_armed and not clutch_session_active:
                self._reset_clutch_session()
                clutch_session_active = False
            preview_state.gate1_passed = gate_decision.gate1_passed
            preview_state.clutch_active = clutch_session_active
            preview_state.clutch_progress = gate_decision.clutch_progress
            preview_state.required_clutch_frames = gate_decision.required_clutch_frames
            self._clutch_active_prev = clutch_session_active
            motion_score = self._measure_motion(normalized_hand)

            # --- PIPELINE STAGE 5: STATIC INFERENCE ---
            inference_result: StaticInferenceResult | None = None
            if (
                clutch_session_active
                and gate_decision.gate1_passed
                and normalized_hand is not None
                and not is_recording
                and self._static_runner is not None
            ):
                with self._model_lock:
                    inference_result = self._static_runner.infer(normalized_hand)

            preview_state = self._build_preview_state(
                camera_ready=self._camera_manager.is_open(),
                hand_present=detection.hand_present,
                hand_count=int(detection.hand_count),
                tracking_confidence=detection.tracking_confidence,
                gate1_passed=gate_decision.gate1_passed,
                clutch_active=clutch_session_active,
                clutch_seconds_remaining=max(0.0, self._clutch_session_expires_at - now),
                clutch_progress=gate_decision.clutch_progress,
                required_clutch_frames=gate_decision.required_clutch_frames,
                raw_gesture_hint=detection.raw_gesture_hint,
                inference_result=inference_result,
                is_recording=is_recording,
            )

            # --- PIPELINE STAGE 6: OVERLAY RENDERING ---
            overlay_frame = self._preview_renderer.render(
                camera_frame.frame_bgr,
                preview_state,
                hand_frame=normalized_hand,
            )
            self._encode_preview_frame(overlay_frame)

            # --- PIPELINE STAGE 7: STABILIZER + COOLDOWN + IPC ---
            if not detection.hand_present:
                if self._active_continuous_label is not None and now - self._continuous_seen_at >= self._clutch_idle_timeout_sec:
                    self._active_continuous_label = None
                    self._continuous_smoothed_value = 0.0
                    self._continuous_prev_index_y = None
                elif not clutch_session_active and self._hand_present_prev:
                    self._reset_clutch_session()
                self._hand_present_prev = False
                time.sleep(0.02)
                continue

            self._hand_present_prev = True

            if is_recording:
                time.sleep(0.01)
                continue

            # --- Dual-Brain collision resolution ---
            # The default model always runs.  If a custom model is loaded and
            # produced a result, the PriorityRouter decides which one wins.
            default_label = "UNKNOWN"
            default_conf = 0.0
            custom_label = None
            custom_conf = None

            if inference_result is not None and not inference_result.is_unknown:
                if inference_result.label_name == "OK_Sign" and inference_result.confidence < 0.92:
                    default_label = "UNKNOWN"
                    default_conf = 0.0
                else:
                    default_label = inference_result.label_name
                    default_conf = inference_result.confidence

            # TODO: when custom_static_runner is wired, populate custom_label
            # and custom_conf from its result here.

            resolved_label, resolved_conf = self._router.resolve(
                default_label, default_conf,
                custom_label, custom_conf,
                gesture_type="static",
            )
            resolved_action = (
                self._router.get_action(resolved_label, "static")
                if resolved_label != "UNKNOWN"
                else "Unknown"
            )

            if resolved_label == "UNKNOWN":
                stable_result = self._gesture_stabilizer(
                    InferenceResult(label="UNKNOWN", confidence=0.0)
                )
            else:
                stable_result = self._gesture_stabilizer(
                    InferenceResult(
                        label=resolved_label,
                        confidence=resolved_conf,
                    )
                )

            now = time.monotonic()

            # Dynamic gestures are treated as bounded episodes: once the clutch
            # is open and motion clearly starts, the dynamic pipeline claims the
            # interaction immediately and static actions are suppressed until
            # that episode ends.
            if self._should_start_dynamic_episode(
                clutch_session_active=clutch_session_active,
                gate1_passed=gate_decision.gate1_passed,
                normalized_hand=normalized_hand,
                is_recording=is_recording,
                motion_score=motion_score,
                resolved_action=resolved_action,
            ):
                if not self._dynamic_capture_active:
                    self._dynamic_capture_active = True
                    self._dynamic_frames = []
                self._dynamic_last_motion_at = now

            if self._dynamic_capture_active and normalized_hand is not None:
                self._dynamic_frames.append(list(normalized_hand.normalized_features))
                if motion_score >= self._dynamic_motion_threshold:
                    self._dynamic_last_motion_at = now

                capture_complete = (
                    len(self._dynamic_frames) >= 30 or
                    (
                        len(self._dynamic_frames) >= self._dynamic_min_frames and
                        now - self._dynamic_last_motion_at >= self._dynamic_idle_timeout_sec
                    )
                )
                if capture_complete:
                    with self._model_lock:
                        dynamic_result = self._dynamic_runner.infer_sequence(self._dynamic_frames)
                    if not dynamic_result.is_unknown:
                        overlay_frame = self._preview_renderer.render_dynamic(overlay_frame, dynamic_result)
                        self._encode_preview_frame(overlay_frame)
                        self._last_action_time = now
                        predicted_label = dynamic_result.label_name
                        print(f"DEBUG: predicted_label={predicted_label}", flush=True)
                        payload = self._build_gesture_payload(
                            predicted_label,
                            dynamic_result.confidence,
                            normalized_hand,
                        )
                        payload["action"] = self._router.get_action(predicted_label, "dynamic")
                        payload["value"] = 0.0
                        self._send(payload)
                        self._last_action_label = predicted_label
                    self._gesture_stabilizer.reset()
                    self._dynamic_capture_active = False
                    self._dynamic_frames = []
                    time.sleep(0.02)
                    continue

            if resolved_label != "UNKNOWN":
                if resolved_action.startswith("Mode:"):
                    continuous_payload = self._build_continuous_payload(
                        resolved_label,
                        resolved_action,
                        normalized_hand,
                    )
                    if continuous_payload is not None:
                        print(f"DEBUG: predicted_label={resolved_label}", flush=True)
                        self._send(continuous_payload)
                        self._last_action_label = resolved_label
                        self._active_continuous_label = resolved_label
                        self._continuous_seen_at = now
                        self._clutch_last_activity_at = now
                    time.sleep(0.02)
                    continue

            if (
                self._active_continuous_label is not None and
                now - self._continuous_seen_at >= self._clutch_idle_timeout_sec
            ):
                self._active_continuous_label = None
                self._continuous_smoothed_value = 0.0
                self._continuous_prev_index_y = None
                time.sleep(0.02)
                continue

            if stable_result.label != "UNKNOWN":
                if now - self._last_action_time >= self._action_cooldown_sec:
                    self._last_action_time = now
                    predicted_label = stable_result.label
                    print(f"DEBUG: predicted_label={predicted_label}", flush=True)
                    payload = {
                        "type": "gesture",
                        "label": predicted_label,
                        "class": predicted_label,
                        "action": self._router.get_action(predicted_label, "static"),
                        "mode": self._interaction_mode,
                        "confidence": stable_result.confidence,
                        "value": 0.0,
                    }
                    if normalized_hand is not None and len(normalized_hand.landmarks_xyz) >= 21:
                        payload["index_tip"] = {
                            "x": float(normalized_hand.landmarks_xyz[8][0]),
                            "y": float(normalized_hand.landmarks_xyz[8][1]),
                        }
                        payload["thumb_tip"] = {
                            "x": float(normalized_hand.landmarks_xyz[4][0]),
                            "y": float(normalized_hand.landmarks_xyz[4][1]),
                        }
                    self._send(payload)
                    self._last_action_label = predicted_label
                    self._gesture_stabilizer.reset()

            time.sleep(0.02)

    def _play_clutch_activation_sound(self) -> None:
        """
        Play a slightly louder two-note UX "twink" when the clutch activates.

        The whole point is awareness: the user may be looking away from the
        live monitoring tab, so activation needs an audible cue. This helper is
        best-effort and intentionally non-fatal; audio feedback should never be
        able to crash gesture control.
        """

        if winsound is None:
            return

        try:
            # Two short tones feel more like a "twink" than a flat beep.
            # Running them on a tiny background thread keeps the frame loop
            # responsive while still making the activation feedback obvious.
            def _beep_sequence() -> None:
                try:
                    winsound.Beep(1480, 70)
                    winsound.Beep(1760, 95)
                except Exception:
                    pass

            threading.Thread(target=_beep_sequence, daemon=True).start()
        except Exception:
            pass

    def _start_background_runtime(self) -> None:
        """
        Start the camera preview source and the main Phase 1 pipeline thread.

        We do this once for the whole service lifetime instead of once per TCP
        client connection. That keeps the preview endpoint usable on cold boot
        and avoids spawning duplicate inference loops on reconnects.
        """

        if self._pipeline_thread is not None and self._pipeline_thread.is_alive():
            return

        # Best-effort camera boot. If the camera is unavailable at startup, the
        # pipeline will continue retrying via `_ensure_camera_ready()`.
        self._camera_manager.start()

        self._pipeline_thread = threading.Thread(
            target=self.run_pipeline,
            name="MlServicePipeline",
            daemon=True,
        )
        self._pipeline_thread.start()
        trace_startup("pipeline thread started")

    # ---------------------------------------------------------------------
    # Voice pipeline
    # ---------------------------------------------------------------------
    def _voice_loop(self) -> None:
        if not (KaldiRecognizer and VoskModel and sd):
            return

        model_dir = resolve_vosk_model_dir()
        if model_dir is None:
            return

        while self._running:
            if self._interaction_mode != "VOICE":
                self._close_voice_stream()
                time.sleep(0.15)
                continue

            recognizer = KaldiRecognizer(VoskModel(str(model_dir)), 16000)

            def callback(
                indata: bytes,
                frames: int,
                time_info: Any,
                status: Any,
            ) -> None:
                del frames, time_info, status
                if self._interaction_mode != "VOICE":
                    return
                if recognizer.AcceptWaveform(bytes(indata)):
                    payload = json.loads(recognizer.Result())
                    text = str(payload.get("text", "")).strip()
                    if (
                        text
                        and (time.monotonic() - self._last_voice_emit)
                        >= self._voice_phrase_cooldown_sec
                    ):
                        self._last_voice_emit = time.monotonic()
                        self._send({"type": "voice", "text": text, "confidence": 0.9})

            try:
                self._mic_state = "opening"
                self._set_status(
                    state=self._status.get("state", "ready"),
                    message="starting_voice",
                )
                with sd.RawInputStream(
                    samplerate=16000,
                    blocksize=8000,
                    dtype="int16",
                    channels=1,
                    device=self._voice_input_index if self._voice_input_index >= 0 else None,
                    callback=callback,
                ):
                    self._mic_state = "ready"
                    self._set_status(
                        state=self._status.get("state", "ready"),
                        message="mic_ready",
                    )
                    while self._running and self._interaction_mode == "VOICE":
                        time.sleep(0.1)
            except Exception as exc:  # pragma: no cover - device/runtime path
                self._mic_state = "error"
                self._set_status(state="error", message="mic_open_failed", error=str(exc))
                time.sleep(0.5)
            finally:
                self._close_voice_stream()

    # ---------------------------------------------------------------------
    # Training orchestration
    # ---------------------------------------------------------------------
    def _train_async(self) -> None:
        self._set_status(state="training", message="training_started")
        trace_startup("training stage=start")
        try:
            def cb(progress: float) -> None:
                trace_startup(f"training stage=progress progress={progress}")
                self._send({"type": "training_progress", "progress": progress})

            trace_startup("training stage=retrain_static_model")
            if self._pending_train_type == "dynamic":
                result = _retrain_custom_dynamic_model()
            else:
                result = _retrain_custom_static_model(progress_cb=cb)
            trace_startup(f"training stage=retrain_complete result={result}")
            with self._model_lock:
                trace_startup("training stage=reload_runtime_model")
                self._load_runtime_model()
                self._router.reload()
            trace_startup("training stage=send_trained")
            self._send(
                {
                    "type": "training",
                    "status": "trained",
                    "accuracy": result.get("accuracy", 0.0),
                    "warnings": result.get("warnings", []),
                    "labels": result.get("labels", self._available_labels()),
                }
            )
            self._set_status(state="ready", message="training_finished")
        except Exception as exc:  # pragma: no cover - defensive path
            tb = traceback.format_exc()
            trace_startup(f"training stage=failed error={exc}\n{tb}")
            self._send(
                {
                    "type": "training",
                    "status": "failed",
                    "error": str(exc),
                    "traceback": tb,
                }
            )
            self._set_status(
                state="error",
                message="training_failed",
                error=str(exc),
                traceback=tb,
            )

    # ---------------------------------------------------------------------
    # Command handling
    # ---------------------------------------------------------------------
    def handle_command(self, payload: Dict[str, Any]) -> None:
        command = str(payload.get("command", "")).strip().upper()

        if command == "START_RECORDING":
            label_name = str(payload.get("label", "UNNAMED"))
            action_name = str(payload.get("action", "Click"))
            gesture_type = str(payload.get("gesture_type", "static")).strip().lower()
            try:
                if gesture_type == "dynamic":
                    label_idx = _add_custom_dynamic_gesture(label_name, action_name)
                else:
                    gesture_type = "static"
                    label_idx = _add_custom_static_gesture(label_name, action_name)
                self._recording_buffer.clear()
                self._recording_label_name = label_name
                self._recording_samples = 0
                self._recording_target_samples = 300 if gesture_type == "dynamic" else 320
                self._recording_capture_interval = 0.05
                self._last_capture_time = time.monotonic()
                self._recording_label_idx = label_idx
                self._recording_gesture_type = gesture_type
                self._set_status(
                    state="recording",
                    message=f"recording:{label_name}",
                    active_label=label_name,
                    sample_count=0,
                    target_samples=self._recording_target_samples,
                )
            except Exception as exc:
                self._set_status(state="error", message=f"recording_failed:{str(exc)}")
            return

        if command == "STOP_RECORDING":
            self._stop_recording(reason="recording_stopped_manual")
            return

        if command == "TRAIN_MODEL":
            if self._training_thread and self._training_thread.is_alive():
                self._send({"type": "training", "status": "busy"})
                return
            self._training_thread = threading.Thread(target=self._train_async, daemon=True)
            self._training_thread.start()
            return

        if command == "SET_SETTINGS":
            settings = payload.get("settings")
            if isinstance(settings, dict):
                self._set_device_settings(settings)
            else:
                self._set_device_settings(payload)
            return

        if command == "DELETE_GESTURE":
            label = str(payload.get("label", "")).strip()
            try:
                _delete_custom_static_gesture(label)
                with self._model_lock:
                    self._load_runtime_model()
                    self._router.reload()
                self._set_status(state="ready", message=f"deleted:{label}")
            except Exception as exc:
                self._set_status(state="error", message=f"delete_failed:{str(exc)}")
            return

        if command == "VOICE_TEXT":
            text = str(payload.get("text", "")).strip()
            lowered = text.lower()
            if lowered == "switch to voice mode":
                self._set_mode("VOICE")
            elif lowered == "switch to hand mode":
                self._set_mode("HAND")
            if self._interaction_mode == "VOICE":
                self._send({"type": "voice", "text": text, "confidence": 0.9})
            return

        if command == "SET_MODE":
            mode = str(payload.get("mode", "HAND")).upper()
            self._set_mode("VOICE" if mode == "VOICE" else "HAND")
            return

        if command == "LIST_LABELS":
            self._send({"type": "labels", "labels": self._available_labels()})
            return

        if command == "SHUTDOWN":
            self._close_camera()
            self._close_voice_stream()
            self._hand_ingestion.close()
            self._running = False
            return

    # ---------------------------------------------------------------------
    # Main server lifecycle
    # ---------------------------------------------------------------------
    def serve(self) -> None:
        trace_startup("serve start")

        # Start the background camera/inference runtime before the preview app
        # begins serving requests. This ensures `/video_feed` can produce frames
        # immediately after Flask boots instead of waiting for a TCP client
        # connection to trigger the ML loop.
        self._start_background_runtime()

        if Flask is not None:
            self._preview_thread = threading.Thread(
                target=self._start_http_preview,
                daemon=True,
            )
            self._preview_thread.start()
            trace_startup("preview thread started")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            trace_startup("binding command socket")
            server.bind((HOST, PORT))
            server.listen(1)
            trace_startup("command socket listening")

            while self._running:
                trace_startup("waiting for client")
                try:
                    self._client, _ = server.accept()
                except OSError:
                    break
                trace_startup("client accepted")

                self._send_fail_count = 0

                runtime = describe_runtime()
                self._set_status(
                    state="ready",
                    message="service_ready",
                    python=runtime["python"],
                    cv2=runtime["cv2"],
                    mediapipe=runtime["mediapipe"],
                    vosk=runtime["vosk"],
                    error=(
                        f"cv2_error={runtime.get('cv2_error', '')} "
                        f"mediapipe_error={runtime.get('mediapipe_error', '')} "
                        f"vosk_error={runtime.get('vosk_error', '')}"
                    ),
                )
                self._voice_thread = threading.Thread(target=self._voice_loop, daemon=True)
                self._voice_thread.start()

                with self._client:
                    buffer = ""
                    while self._running:
                        try:
                            chunk = self._client.recv(4096)
                        except ConnectionResetError:
                            break
                        if not chunk:
                            break
                        buffer += chunk.decode("utf-8")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            if not line.strip():
                                continue
                            self.handle_command(json.loads(line))

                trace_startup("client disconnected, cleaning up")
                if self._recording_label_idx is not None:
                    self._stop_recording(reason="recording_stopped_disconnect")
                self._close_voice_stream()
                self._reset_clutch_session()
                self._client = None

        self._hand_ingestion.close()


if __name__ == "__main__":
    try:
        report = diagnose_environment()
        with open(STARTUP_TRACE, "a", encoding="utf-8") as handle:
            handle.write(
                f"\nEnvironment Diagnostic Report:\n{json.dumps(report, indent=2)}\n"
            )

        MlService().serve()
    except Exception:  # pragma: no cover - startup/runtime crash logging
        (ROOT / "service_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise

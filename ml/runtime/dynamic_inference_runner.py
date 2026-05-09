from __future__ import annotations

import os
from collections import deque
from pathlib import Path
import warnings
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from ml.runtime.types import DynamicInferenceResult, NormalizedHandFrame


class SequenceBuffer:
    """
    Rolling sequence buffer for dynamic gesture inference.

    Why this lives in its own class:
    dynamic inference has a different shape from static inference. Static uses
    one frame at a time; dynamic needs a stable fixed-length window. Keeping
    that buffering behavior in one small object makes the future dispatcher
    logic much easier to reason about.
    """

    def __init__(self, maxlen: int = 30, feature_size: int = 126) -> None:
        self._maxlen = int(maxlen)
        self._feature_size = int(feature_size)
        self._frames: deque[list[float]] = deque(maxlen=self._maxlen)

    def append_frame(self, hand_frame: NormalizedHandFrame) -> None:
        """
        Append one normalized frame to the rolling window.

        The buffer stores plain feature lists instead of full frame objects so
        it stays lightweight and focused on the exact input needed by the LSTM.
        """

        self.append_features(hand_frame.normalized_features)

    def append_features(self, features: list[float]) -> None:
        if len(features) != self._feature_size:
            raise ValueError(
                f"Expected {self._feature_size} dynamic features, got {len(features)}."
            )
        self._frames.append([float(value) for value in features])

    def clear(self) -> None:
        """Drop the current sequence window."""

        self._frames.clear()

    def is_full(self) -> bool:
        """Return True once the buffer contains exactly `maxlen` frames."""

        return len(self._frames) == self._maxlen

    def size(self) -> int:
        """Return the current number of frames in the rolling window."""

        return len(self._frames)

    def maxlen(self) -> int:
        """Return the configured window length."""

        return self._maxlen

    def to_list(self) -> list[list[float]]:
        """Return a copy of the buffered sequence data."""

        return [list(frame) for frame in self._frames]


class DynamicGestureModel(nn.Module):
    """
    A small LSTM classifier for sequence-based gesture recognition.

    This is intentionally defined here for now because Phase 2 is focused on
    building an isolated dynamic pipeline without wiring it into the rest of the
    runtime yet. Once training lands, this model can be split into its own
    module if that improves clarity.
    """

    def __init__(
        self,
        input_size: int = 126,
        hidden_size: int = 64,
        num_layers: int = 2,
        num_classes: int = 2,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2,
        )
        self.fc1 = nn.Linear(hidden_size, 32)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(32, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _outputs, (hidden, _cell) = self.lstm(x)
        final_hidden = hidden[-1]
        return self.fc2(self.relu(self.fc1(final_hidden)))


class DynamicInferenceRunner:
    """
    Runtime owner for the dynamic LSTM gesture model.

    It mirrors the role of `StaticInferenceRunner`, but for fixed-length
    sequences instead of single frames.
    """

    def __init__(
        self,
        model_path: str | None = None,
        label_map: dict[int, str] | None = None,
        sequence_length: int = 30,
        feature_size: int = 126,
        confidence_threshold: float = 0.75,
        hidden_size: int = 64,
        num_layers: int = 2,
    ) -> None:
        default_model_path = (
            Path(__file__).resolve().parent.parent / "models" / "dynamic" / "custom_model.pth"
        )
        self._model_path = str(model_path or default_model_path)
        self._label_map: dict[int, str] = dict(label_map or {})
        self._sequence_length = int(sequence_length)
        self._feature_size = int(feature_size)
        self._confidence_threshold = float(confidence_threshold)
        self._hidden_size = int(hidden_size)
        self._num_layers = int(num_layers)
        self._model: DynamicGestureModel | None = None
        self._last_error = ""

        self.reload(model_path=self._model_path, label_map=self._label_map)

    def reload(self, model_path: str, label_map: dict[int, str]) -> None:
        """
        Hot-swap the dynamic model weights and label map.

        This gives the future training pipeline a clean way to refresh the live
        runtime without needing to recreate the whole service process.
        """

        self._model_path = str(model_path)
        self._label_map = dict(label_map)
        self._last_error = ""

        num_classes = self._infer_num_classes(self._model_path, self._label_map)
        if num_classes <= 0:
            self._model = None
            self._last_error = (
                f"Could not determine a valid class count for dynamic model: {self._model_path}"
            )
            return

        try:
            model = DynamicGestureModel(
                input_size=self._feature_size,
                hidden_size=self._hidden_size,
                num_layers=self._num_layers,
                num_classes=num_classes,
            )
            state = torch.load(self._model_path, map_location="cpu")
            model.load_state_dict(state)
            model.eval()
            self._model = model
        except FileNotFoundError:
            self._model = None
            self._last_error = f"Dynamic model file not found: {self._model_path}"
            warnings.warn(self._last_error, RuntimeWarning, stacklevel=2)
        except Exception as exc:
            self._model = None
            self._last_error = f"Failed to load dynamic model '{self._model_path}': {exc}"

    def infer(self, buffer: SequenceBuffer) -> DynamicInferenceResult:
        """
        Run dynamic inference only when the sequence buffer is full.

        A strict full-window requirement keeps this component deterministic.
        The future dispatcher can decide when to wait, flush, or reset, but the
        model runner itself should be unambiguous about what it accepts.
        """

        if self._model is None:
            return DynamicInferenceResult(
                label_idx=-1,
                label_name="UNKNOWN",
                confidence=0.0,
                is_unknown=True,
            )

        if not buffer.is_full():
            return DynamicInferenceResult(
                label_idx=-1,
                label_name="UNKNOWN",
                confidence=0.0,
                is_unknown=True,
            )

        try:
            sequence = buffer.to_list()
            x = torch.tensor(sequence, dtype=torch.float32).unsqueeze(0)
            if tuple(x.shape) != (1, self._sequence_length, self._feature_size):
                self._last_error = (
                    "Dynamic sequence tensor has unexpected shape: "
                    f"{tuple(x.shape)}; expected "
                    f"(1, {self._sequence_length}, {self._feature_size})."
                )
                return DynamicInferenceResult(
                    label_idx=-1,
                    label_name="UNKNOWN",
                    confidence=0.0,
                    is_unknown=True,
                )

            with torch.no_grad():
                logits = self._model(x)
                probs = F.softmax(logits, dim=1)
                confidence_tensor, pred_tensor = torch.max(probs, dim=1)

            confidence = float(confidence_tensor.item())
            label_idx = int(pred_tensor.item())
            label_name = self._label_map.get(label_idx, "UNKNOWN")
            is_unknown = confidence < self._confidence_threshold or label_name == "UNKNOWN"

            result = DynamicInferenceResult(
                label_idx=-1 if is_unknown else label_idx,
                label_name="UNKNOWN" if is_unknown else label_name,
                confidence=confidence,
                is_unknown=is_unknown,
            )

            # Clear the sequence only after a successful recognized gesture.
            # This avoids immediately re-emitting the same motion from the same
            # buffered 30-frame window.
            if not result.is_unknown:
                buffer.clear()

            return result
        except Exception as exc:
            self._last_error = f"Dynamic inference failed: {exc}"
            return DynamicInferenceResult(
                label_idx=-1,
                label_name="UNKNOWN",
                confidence=0.0,
                is_unknown=True,
            )

    def get_last_error(self) -> str:
        """Return the most recent dynamic model error, if any."""

        return self._last_error

    def get_model_path(self) -> str:
        """Return the current dynamic model path."""

        return self._model_path

    def get_label_map(self) -> dict[int, str]:
        """Return a copy of the active dynamic label map."""

        return dict(self._label_map)

    def _infer_num_classes(self, model_path: str, label_map: dict[int, str]) -> int:
        """
        Infer the number of output classes from the saved state dict when
        possible, falling back to the label map if needed.
        """

        try:
            state: dict[str, Any] = torch.load(model_path, map_location="cpu")
            output_weight = state.get("fc2.weight")
            if output_weight is not None and hasattr(output_weight, "shape"):
                shape = getattr(output_weight, "shape")
                if len(shape) >= 1:
                    return int(shape[0])
        except FileNotFoundError:
            return max((int(index) for index in label_map.keys()), default=-1) + 1
        except Exception:
            pass

        if not label_map:
            return 0
        return max(int(index) for index in label_map.keys()) + 1

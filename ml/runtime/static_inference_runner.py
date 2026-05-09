from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import warnings

import torch
import torch.nn as nn
import torch.nn.functional as F

from ml.runtime.types import NormalizedHandFrame, StaticInferenceResult


class StaticGestureModel(nn.Module):
    """
    Feed-forward classifier for one normalized two-hand frame.

    Keeping the architecture here makes runtime and training share the same
    definition without depending on the old root bridge module.
    """

    def __init__(self, input_size: int = 126, num_classes: int = 5) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class StaticInferenceRunner:
    """
    Runtime owner for the static PyTorch gesture model.

    This class exists so the live inference path has one clear place
    responsible for:
    - loading model weights
    - holding the active label map
    - running forward passes
    - applying the runtime confidence threshold

    We keep this separate from service orchestration so the rest of the system
    can treat static inference as a clean black box: pass in normalized
    features, receive a typed result back.
    """

    def __init__(
        self,
        model_path: str | None = None,
        label_map: dict[int, str] | None = None,
        input_size: int = 63,
        confidence_threshold: float = 0.6,
    ) -> None:
        self._input_size = int(input_size)
        self._confidence_threshold = float(confidence_threshold)
        default_model_path = (
            Path(__file__).resolve().parent.parent / "models" / "static" / "custom_model.pth"
        )
        self._model_path = str(model_path or default_model_path)
        self._label_map: dict[int, str] = dict(label_map or {})
        self._model: StaticGestureModel | None = None
        self._last_error = ""

        self.reload(model_path=self._model_path, label_map=self._label_map)

    def reload(self, model_path: str, label_map: dict[int, str]) -> None:
        """
        Reload model weights and replace the active label map.

        This supports runtime retraining flows where the Python service keeps
        running and swaps in fresh weights after training completes.
        """

        self._model_path = str(model_path)
        self._label_map = dict(label_map)
        self._last_error = ""

        num_classes = self._infer_num_classes(self._model_path, self._label_map)
        if num_classes <= 0:
            self._model = None
            self._last_error = (
                f"Could not determine a valid class count for model: {self._model_path}"
            )
            return

        try:
            model = StaticGestureModel(input_size=self._input_size, num_classes=num_classes)
            state = torch.load(self._model_path, map_location="cpu")
            if isinstance(state, dict) and "net.6.weight" not in state and "model.6.weight" in state:
                state = {
                    (key.replace("model.", "net.", 1) if key.startswith("model.") else key): value
                    for key, value in state.items()
                }
            model.load_state_dict(state)
            model.eval()
            self._model = model
        except FileNotFoundError:
            self._model = None
            self._last_error = f"Static model file not found: {self._model_path}"
            warnings.warn(self._last_error, RuntimeWarning, stacklevel=2)
        except Exception as exc:
            self._model = None
            self._last_error = f"Failed to load static model '{self._model_path}': {exc}"

    def infer(self, hand_frame: NormalizedHandFrame) -> StaticInferenceResult:
        """
        Run static inference for one normalized hand frame.

        The model is fed the exact 63-float feature vector produced by the
        existing normalization path. That keeps Phase 1 compatible with the
        current training pipeline instead of quietly changing the model contract.
        """

        if self._model is None:
            return StaticInferenceResult(
                label_idx=-1,
                label_name="UNKNOWN",
                confidence=0.0,
                is_unknown=True,
            )

        try:
            features = hand_frame.normalized_features
            if len(features) != self._input_size:
                self._last_error = (
                    f"Expected {self._input_size} normalized features, got {len(features)}."
                )
                return StaticInferenceResult(
                    label_idx=-1,
                    label_name="UNKNOWN",
                    confidence=0.0,
                    is_unknown=True,
                )

            x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                logits = self._model(x)
                probs = F.softmax(logits, dim=1)
                confidence_tensor, pred_tensor = torch.max(probs, dim=1)

            confidence = float(confidence_tensor.item())
            label_idx = int(pred_tensor.item())
            label_name = self._label_map.get(label_idx, "UNKNOWN")
            is_unknown = confidence < self._confidence_threshold or label_name == "UNKNOWN"

            return StaticInferenceResult(
                label_idx=-1 if is_unknown else label_idx,
                label_name="UNKNOWN" if is_unknown else label_name,
                confidence=confidence,
                is_unknown=is_unknown,
            )
        except Exception as exc:
            self._last_error = f"Static inference failed: {exc}"
            return StaticInferenceResult(
                label_idx=-1,
                label_name="UNKNOWN",
                confidence=0.0,
                is_unknown=True,
            )

    def get_last_error(self) -> str:
        """Return the last human-readable model load or inference error."""

        return self._last_error

    def get_model_path(self) -> str:
        """Return the currently configured model path."""

        return self._model_path

    def get_label_map(self) -> dict[int, str]:
        """Return a copy of the active runtime label map."""

        return dict(self._label_map)

    def _infer_num_classes(self, model_path: str, label_map: dict[int, str]) -> int:
        """
        Infer the output size expected by the stored model weights.

        Why this helper exists:
        the number of classes is not always equal to the visible label count.
        Single-class training may inject an extra synthetic class, so we should
        prefer the saved weight shape when possible.
        """

        try:
            state: dict[str, Any] = torch.load(model_path, map_location="cpu")
            output_weight = state.get("net.6.weight")
            if output_weight is None:
                output_weight = state.get("model.6.weight")
            if output_weight is not None and hasattr(output_weight, "shape"):
                shape = getattr(output_weight, "shape")
                if len(shape) >= 1:
                    return int(shape[0])
        except FileNotFoundError:
            return max((int(index) for index in label_map.keys()), default=-1) + 1
        except Exception:
            # If introspection fails, we fall back to the label map instead of
            # crashing reload. This is a pragmatic runtime choice because the
            # model may still be loadable with the known label count.
            pass

        if not label_map:
            return 0
        return max(int(index) for index in label_map.keys()) + 1

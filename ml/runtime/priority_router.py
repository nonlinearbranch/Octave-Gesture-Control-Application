"""
Priority Router — Dual-Model Collision Resolver

Resolves conflicts between the default model and the custom model at inference
time.  Custom gestures always win when they produce a confident result.  When
the custom model yields UNKNOWN, the default result is checked against the
hijacked-actions blacklist before being forwarded.

Config files
------------
* ``ml/config/default_mapping.json`` — read-only factory gestures.
* ``ml/config/override_state.json``  — runtime blacklist maintained by the
  training / deletion lifecycle.
"""

from __future__ import annotations
from pathlib import Path
import json

from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DEFAULT_MAPPING_PATH = CONFIG_DIR / "default_mapping.json"
USER_MAPPING_PATH = CONFIG_DIR / "user_mapping.json"
OVERRIDE_STATE_PATH = CONFIG_DIR / "override_state.json"



# Confidence floor below which any result is treated as UNKNOWN.
_DEFAULT_CONFIDENCE_THRESHOLD = 0.60


class PriorityRouter:
    """Stateless collision resolver for the dual-brain inference pipeline."""

    def __init__(
        self,
        confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._confidence_threshold = confidence_threshold

        # In-memory caches populated from disk.
        self._default_mapping: dict[str, dict[str, Any]] = {}
        self._user_mapping: dict[str, dict[str, Any]] = {}
        self._hijacked_actions: dict[str, str] = {}
        self._disabled_defaults: list[str] = []

        self.reload()

    # -----------------------------------------------------------------
    # Config I/O
    # -----------------------------------------------------------------
    def reload(self) -> None:
        """Re-read both config files from disk.  Safe to call at any time."""

        # --- default_mapping.json ---
        if DEFAULT_MAPPING_PATH.exists():
            try:
                with DEFAULT_MAPPING_PATH.open("r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                self._default_mapping = raw if isinstance(raw, dict) else {}
            except (json.JSONDecodeError, OSError):
                self._default_mapping = {}
        else:
            self._default_mapping = {}

        # --- user_mapping.json ---
        if USER_MAPPING_PATH.exists():
            try:
                with USER_MAPPING_PATH.open("r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                self._user_mapping = raw if isinstance(raw, dict) else {}
            except (json.JSONDecodeError, OSError):
                self._user_mapping = {}
        else:
            self._user_mapping = {}

        # --- override_state.json ---
        if OVERRIDE_STATE_PATH.exists():
            try:
                with OVERRIDE_STATE_PATH.open("r", encoding="utf-8") as fh:
                    state = json.load(fh)
                self._hijacked_actions = state.get("hijacked_actions", {})
                self._disabled_defaults = state.get("disabled_defaults", [])
            except (json.JSONDecodeError, OSError):
                self._hijacked_actions = {}
                self._disabled_defaults = []
        else:
            self._hijacked_actions = {}
            self._disabled_defaults = []

    # -----------------------------------------------------------------
    # Resolution
    # -----------------------------------------------------------------
    def resolve(
        self,
        default_label: str,
        default_confidence: float,
        custom_label: Optional[str],
        custom_confidence: Optional[float],
        gesture_type: str = "static",
    ) -> tuple[str, float]:
        """Return ``(final_label, final_confidence)`` after collision logic.

        Parameters
        ----------
        default_label:
            Label string from the default model (or ``"UNKNOWN"``).
        default_confidence:
            Confidence score from the default model.
        custom_label:
            Label string from the custom model, or *None* if no custom model
            is loaded.
        custom_confidence:
            Confidence score from the custom model, or *None*.
        gesture_type:
            ``"static"`` or ``"dynamic"`` — selects the section inside
            ``default_mapping.json``.

        Returns
        -------
        tuple[str, float]
            ``(resolved_label, resolved_confidence)``.  Returns
            ``("UNKNOWN", 0.0)`` when neither model produces a usable result
            or when the result is blacklisted.
        """

        # --- Scenario 1: Custom model produced a confident hit --------
        custom_valid = (
            custom_label is not None
            and custom_label != "UNKNOWN"
            and custom_confidence is not None
            and custom_confidence >= self._confidence_threshold
        )

        if custom_valid:
            return (custom_label, custom_confidence)  # type: ignore[return-value]

        # --- Scenario 2: Fall back to default model -------------------
        default_valid = (
            default_label != "UNKNOWN"
            and default_confidence >= self._confidence_threshold
        )

        if not default_valid:
            return ("UNKNOWN", 0.0)

        # Check explicit disable list.
        if default_label in self._disabled_defaults:
            return ("UNKNOWN", 0.0)

        # Check action-hijack blacklist.  Lookup the action string that
        # the default gesture maps to, then see if a custom gesture has
        # claimed that action.
        default_action = self._lookup_default_action(
            default_label, gesture_type
        )
        if default_action and default_action in self._hijacked_actions:
            return ("UNKNOWN", 0.0)

        return (default_label, default_confidence)

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _lookup_default_action(
        self, label_name: str, gesture_type: str
    ) -> str | None:
        """Find the action string for *label_name* inside default_mapping."""
        section = self._default_mapping.get(gesture_type, {})
        for _key, entry in section.items():
            if isinstance(entry, dict) and entry.get("name") == label_name:
                return entry.get("action")
        return None

    def get_action(self, label_name: str, gesture_type: str) -> str:
        """Get the mapped action for a gesture label, checking user overrides first."""
        section = self._user_mapping.get(gesture_type, {})
        for _key, entry in section.items():
            if isinstance(entry, dict) and entry.get("name") == label_name:
                action = entry.get("action")
                if action:
                    return action

        action = self._lookup_default_action(label_name, gesture_type)
        return action if action else "Unknown"

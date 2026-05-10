from __future__ import annotations

from ml.runtime.types import ClutchState, GateDecision, NormalizedHandFrame


class Gate1ConfidenceGate:
    """
    Hard confidence filter for the ingestion funnel.

    This gate is intentionally simple: if tracking quality is too low, later
    stages should not spend work on the frame and should not try to "guess
    through" uncertainty.
    """

    def __init__(self, min_confidence: float = 0.7) -> None:
        self._min_confidence = float(min_confidence)

    @property
    def min_confidence(self) -> float:
        return self._min_confidence

    def evaluate(self, hand_frame: NormalizedHandFrame | None) -> bool:
        """
        Return True only when a usable hand frame exists and meets the minimum
        confidence threshold.
        """

        if hand_frame is None:
            return False
        if not hand_frame.hand_present:
            return False
        return float(hand_frame.tracking_confidence) >= self._min_confidence


class Gate2OpenPalmClutchGate:
    """
    Two-hand open-palm clutch for static inference.

    Behavior:
    - activates immediately on a strict OPEN_PALM_PAIR frame
    - never activates from a single-hand pose
    - resets immediately if the hand disappears or Gate 1 fails
    """

    def __init__(self, required_hold_frames: int = 6) -> None:
        self._required_hold_frames = int(required_hold_frames)
        self._state = ClutchState(
            active=False,
            candidate_label=None,
            hold_frames=0,
            required_frames=self._required_hold_frames,
            last_seen_frame_id=None,
        )

    @property
    def required_hold_frames(self) -> int:
        return self._required_hold_frames

    def reset(self) -> None:
        """Reset clutch state to a fully inactive baseline."""

        self._state = ClutchState(
            active=False,
            candidate_label=None,
            hold_frames=0,
            required_frames=self._required_hold_frames,
            last_seen_frame_id=None,
        )

    def update(
        self,
        hand_frame: NormalizedHandFrame | None,
        gate1_passed: bool,
    ) -> ClutchState:
        """
        Advance the clutch state machine using the current frame.

        Behavior:
        - activation is immediate as soon as both hands look fully open
        - partial single-hand poses never promote to clutch active
        - after activation, the clutch behaves like a trigger and remains
          active until a hard reset condition occurs elsewhere
        """

        # If the clutch is already active, keep it active permanently until
        # an explicit reset occurs elsewhere. This makes the open-palm gesture a trigger
        # rather than a hold gate.
        if self._state.active:
            if hand_frame is not None:
                self._state.last_seen_frame_id = hand_frame.frame_id
            return self._state

        # First, apply the hard reset conditions for activation.
        if hand_frame is None:
            self.reset()
            return self._state

        if not gate1_passed:
            self.reset()
            return self._state

        current_hint = hand_frame.raw_gesture_hint

        # If the current frame is not OPEN_PALM_PAIR, stay inactive.
        if current_hint != "OPEN_PALM_PAIR":
            self._state.last_seen_frame_id = hand_frame.frame_id
            return self._state

        # OPEN_PALM_PAIR detected: activate immediately (no timer).
        self._state = ClutchState(
            active=True,
            candidate_label="OPEN_PALM_PAIR",
            hold_frames=1,
            required_frames=1,
            last_seen_frame_id=hand_frame.frame_id,
        )
        return self._state


class InferenceGatePipeline:
    """
    Combine Gate 1 and Gate 2 into a single frame-level decision object.

    The rest of the runtime should not need to know the sequencing details of
    the funnel. It should be able to ask one question per frame:
    "is this frame allowed to reach static inference, and if not, why not?"
    """

    def __init__(self, min_confidence: float = 0.7, required_hold_frames: int = 6) -> None:
        self._confidence_gate = Gate1ConfidenceGate(min_confidence=min_confidence)
        self._clutch_gate = Gate2OpenPalmClutchGate(required_hold_frames=required_hold_frames)

    def reset(self) -> None:
        """Reset the stateful clutch gate."""

        self._clutch_gate.reset()

    def evaluate(self, hand_frame: NormalizedHandFrame | None) -> GateDecision:
        """
        Evaluate both gates for the given frame and return a structured result.
        """

        gate1_passed = self._confidence_gate.evaluate(hand_frame)
        clutch_state = self._clutch_gate.update(hand_frame, gate1_passed=gate1_passed)
        gate2_passed = clutch_state.active
        accepted = gate1_passed and gate2_passed

        if hand_frame is None:
            reason = "no_hand"
        elif not gate1_passed:
            reason = "low_confidence"
        elif hand_frame.raw_gesture_hint != "OPEN_PALM_PAIR":
            reason = "clutch_pose_missing"
        elif not gate2_passed:
            reason = "clutch_holding"
        else:
            reason = "accepted"

        return GateDecision(
            accepted=accepted,
            reason=reason,
            gate1_passed=gate1_passed,
            gate2_passed=gate2_passed,
            clutch_active=clutch_state.active,
            clutch_progress=clutch_state.hold_frames,
            required_clutch_frames=clutch_state.required_frames,
        )

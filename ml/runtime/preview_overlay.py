from __future__ import annotations

from typing import Any

from ml.runtime.types import DynamicInferenceResult, NormalizedHandFrame, PreviewState

cv2_error = ""
try:
    import cv2
except ImportError as exc:  # pragma: no cover - depends on local runtime
    cv2 = None  # type: ignore[assignment]
    cv2_error = str(exc)


class PreviewOverlayRenderer:
    """
    Draw lightweight UI hints on top of the live preview frame.

    The overlay should help the user understand what the system needs right
    now, but it should stay visually quiet. The goal is guidance, not a
    dashboard. That is why this renderer uses small labels, a simple clutch bar,
    and plain landmark visuals instead of heavy panels or decorative graphics.
    """

    def __init__(self) -> None:
        self._last_error = ""

    def render(
        self,
        frame_bgr: Any | None,
        preview_state: PreviewState,
        hand_frame: NormalizedHandFrame | None = None,
    ) -> Any | None:
        """
        Render a minimalist overlay on top of a copied frame.

        Returns:
            A new annotated frame on success, or the original frame value when
            drawing cannot proceed.

        We always draw on `frame.copy()` rather than the original frame because
        overlay rendering is a presentation concern. Downstream logic should not
        receive a mutated frame by surprise.
        """

        if frame_bgr is None:
            return None

        if cv2 is None:
            self._last_error = f"OpenCV overlay rendering unavailable: {cv2_error}"
            return frame_bgr

        try:
            canvas = frame_bgr.copy()
        except Exception as exc:
            self._last_error = f"Could not copy preview frame: {exc}"
            return frame_bgr

        try:
            if hand_frame is not None:
                if hand_frame.all_landmarks_xyz is not None and len(hand_frame.all_landmarks_xyz) > 0:
                    self._draw_all_hands(canvas, hand_frame)
                elif len(hand_frame.landmarks_xyz) > 0:
                    self._draw_bounding_box(canvas, hand_frame)
                    self._draw_landmarks(canvas, hand_frame)

            self._draw_status(canvas, preview_state)
            self._draw_clutch_progress(canvas, preview_state)
            self._last_error = ""
            return canvas
        except Exception as exc:
            self._last_error = f"Overlay rendering failed: {exc}"
            return frame_bgr

    def get_last_error(self) -> str:
        """Return the last overlay rendering error string, if any."""

        return self._last_error

    def render_dynamic(
        self,
        frame_bgr: Any | None,
        dynamic_result: DynamicInferenceResult,
    ) -> Any | None:
        """
        Draw the dynamic gesture result underneath the static gesture text.

        We keep this as a separate helper instead of folding it into the main
        render method because dynamic inference is being introduced incrementally.
        That keeps the Phase 2 integration small and easy to review.
        """

        if frame_bgr is None or cv2 is None:
            return frame_bgr

        try:
            # Always copy before drawing to avoid mutating the input frame.
            # Frame references can be reused, so in-place mutations cause duplication.
            canvas = frame_bgr.copy()
        except Exception as exc:
            self._last_error = f"Could not copy preview frame in render_dynamic: {exc}"
            return frame_bgr

        try:
            cv2.putText(
                canvas,
                f"Dynamic: {dynamic_result.label_name}",
                (18, 132),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.56,
                (255, 210, 120),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                canvas,
                f"Dynamic Conf: {dynamic_result.confidence:.2f}",
                (18, 156),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (220, 220, 220),
                1,
                cv2.LINE_AA,
            )
            self._last_error = ""
            return canvas
        except Exception as exc:
            self._last_error = f"Dynamic overlay rendering failed: {exc}"
            return frame_bgr

    def _draw_status(self, frame_bgr: Any, preview_state: PreviewState) -> None:
        """
        Draw the small, high-signal text labels used by the live preview.

        We intentionally keep the text near the frame edges so the user's hand
        stays visible in the center. The camera preview is the primary content;
        the overlay should support it, not crowd it.
        """

        if cv2 is None:
            return

        status_color = self._status_color(preview_state)
        muted_color = (220, 220, 220)

        cv2.putText(
            frame_bgr,
            preview_state.status_text,
            (18, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            status_color,
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame_bgr,
            preview_state.hint_text,
            (18, 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            muted_color,
            1,
            cv2.LINE_AA,
        )

        confidence_text = f"Confidence: {preview_state.tracking_confidence:.2f}"
        cv2.putText(
            frame_bgr,
            confidence_text,
            (18, 82),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.54,
            muted_color,
            1,
            cv2.LINE_AA,
        )

        if preview_state.inference_label:
            cv2.putText(
                frame_bgr,
                f"Gesture: {preview_state.inference_label}",
                (18, 108),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (170, 255, 170),
                2,
                cv2.LINE_AA,
            )

    def _draw_clutch_progress(self, frame_bgr: Any, preview_state: PreviewState) -> None:
        """
        Draw clutch status indicator.

        Since clutch now activates immediately on OPEN_PALM_PAIR detection,
        we simply show whether the clutch is active or waiting.
        """

        if cv2 is None:
            return

        h, w = frame_bgr.shape[:2]
        x = 18
        y = h - 34

        # Show simple status: either ready or waiting
        if preview_state.clutch_active:
            status_text = "Clutch: READY"
            status_color = (90, 200, 120)
        else:
            status_text = "Waiting: Show open palms"
            status_color = (90, 160, 255)

        cv2.putText(
            frame_bgr,
            status_text,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            status_color,
            1,
            cv2.LINE_AA,
        )

    def _draw_bounding_box(self, frame_bgr: Any, hand_frame: NormalizedHandFrame) -> None:
        """Draw a simple pixel-space bounding box around the detected hand."""

        if cv2 is None:
            return

        bbox = self._compute_pixel_bbox(frame_bgr, hand_frame.landmarks_xyz)
        if bbox is None:
            return

        x1, y1, x2, y2 = bbox
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (120, 200, 255), 2)

    def _draw_landmarks(self, frame_bgr: Any, hand_frame: NormalizedHandFrame) -> None:
        """
        Draw the 21 landmark points and a minimal connection scaffold.

        We do not try to reproduce the full MediaPipe styling here. The preview
        only needs enough structure for the user to understand that the hand is
        being tracked cleanly.
        """

        if cv2 is None:
            return

        h, w = frame_bgr.shape[:2]
        pixel_points: list[tuple[int, int]] = []
        for x_norm, y_norm, _ in hand_frame.landmarks_xyz:
            px = int(max(0, min(w - 1, x_norm * w)))
            py = int(max(0, min(h - 1, y_norm * h)))
            pixel_points.append((px, py))

        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17),
        ]

        for start_idx, end_idx in connections:
            start = pixel_points[start_idx]
            end = pixel_points[end_idx]
            cv2.line(frame_bgr, start, end, (110, 180, 240), 1, cv2.LINE_AA)

        for idx, point in enumerate(pixel_points):
            radius = 4 if idx == 0 else 3
            color = (120, 255, 180) if idx in {4, 8, 12, 16, 20} else (255, 255, 255)
            cv2.circle(frame_bgr, point, radius, color, -1, cv2.LINE_AA)

    def _draw_all_hands(self, frame_bgr: Any, hand_frame: NormalizedHandFrame) -> None:
        """
        Draw bounding boxes and landmarks for all detected hands.
        Used during clutch to show both hands.
        """

        if cv2 is None or hand_frame.all_landmarks_xyz is None:
            return

        h, w = frame_bgr.shape[:2]
        for hand_landmarks in hand_frame.all_landmarks_xyz:
            # Draw bounding box
            bbox = self._compute_pixel_bbox(frame_bgr, hand_landmarks)
            if bbox is not None:
                x1, y1, x2, y2 = bbox
                cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (120, 200, 255), 2)

            # Draw landmarks
            pixel_points: list[tuple[int, int]] = []
            for x_norm, y_norm, _ in hand_landmarks:
                px = int(max(0, min(w - 1, x_norm * w)))
                py = int(max(0, min(h - 1, y_norm * h)))
                pixel_points.append((px, py))

            connections = [
                (0, 1), (1, 2), (2, 3), (3, 4),
                (0, 5), (5, 6), (6, 7), (7, 8),
                (0, 9), (9, 10), (10, 11), (11, 12),
                (0, 13), (13, 14), (14, 15), (15, 16),
                (0, 17), (17, 18), (18, 19), (19, 20),
                (5, 9), (9, 13), (13, 17),
            ]

            for start_idx, end_idx in connections:
                start = pixel_points[start_idx]
                end = pixel_points[end_idx]
                cv2.line(frame_bgr, start, end, (110, 180, 240), 1, cv2.LINE_AA)

            for idx, point in enumerate(pixel_points):
                radius = 4 if idx == 0 else 3
                color = (120, 255, 180) if idx in {4, 8, 12, 16, 20} else (255, 255, 255)
                cv2.circle(frame_bgr, point, radius, color, -1, cv2.LINE_AA)

    def _compute_pixel_bbox(
        self,
        frame_bgr: Any,
        landmarks_xyz: list[list[float]],
    ) -> tuple[int, int, int, int] | None:
        """Convert normalized landmark extents into a padded pixel-space box."""

        if not landmarks_xyz:
            return None

        h, w = frame_bgr.shape[:2]
        xs = [point[0] for point in landmarks_xyz]
        ys = [point[1] for point in landmarks_xyz]

        min_x = max(0, min(xs))
        max_x = min(1, max(xs))
        min_y = max(0, min(ys))
        max_y = min(1, max(ys))

        x1 = int(min_x * w)
        x2 = int(max_x * w)
        y1 = int(min_y * h)
        y2 = int(max_y * h)

        pad_x = max(8, int((x2 - x1) * 0.08))
        pad_y = max(8, int((y2 - y1) * 0.08))

        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w - 1, x2 + pad_x)
        y2 = min(h - 1, y2 + pad_y)
        return x1, y1, x2, y2

    def _status_color(self, preview_state: PreviewState) -> tuple[int, int, int]:
        """Pick a simple color based on the current preview state."""

        if preview_state.clutch_active:
            return (110, 230, 140)
        if not preview_state.hand_present:
            return (90, 160, 255)
        if not preview_state.gate1_passed:
            return (90, 170, 255)
        return (255, 220, 120)

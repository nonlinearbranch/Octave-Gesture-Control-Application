from __future__ import annotations

import threading
import time
from typing import Any

from ml.runtime.types import CameraFrame

cv2_error = ""
try:
    import cv2
except ImportError as exc:  # pragma: no cover - depends on local runtime
    cv2 = None  # type: ignore[assignment]
    cv2_error = str(exc)


class CameraManager:
    """
    Own the camera lifecycle and nothing else.

    Why this class exists:
    `service.py` currently mixes camera setup, inference, preview generation,
    recording, and command handling in one place. That makes failures hard to
    reason about because a camera problem can look like an ML problem.

    This class draws a hard boundary around device access. Its job is:
    - open the camera safely
    - read frames
    - close the camera cleanly
    - optionally keep a lightweight background capture loop running

    It does *not* know anything about MediaPipe, landmarks, gestures, or
    models. That separation is the whole point of Phase 1.
    """

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
    ) -> None:
        # Diagnostic note: keep this as a plain variable so multi-camera users
        # can switch to camera_index=1 for OBS Virtual Camera or a second webcam
        # without touching the capture internals below.
        self._camera_index = int(camera_index)
        self._width = int(width)
        self._height = int(height)

        self._capture: Any | None = None
        self._capture_lock = threading.Lock()

        self._latest_frame: CameraFrame | None = None
        self._latest_frame_lock = threading.Lock()

        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._frame_counter = 0
        self._last_error = ""

    def open(self) -> bool:
        """
        Open the camera device if it is not already open.

        Returns:
            True when the camera is ready for reads, otherwise False.

        Why we retry multiple backends:
        On Windows, OpenCV can behave differently depending on whether DirectShow
        (`CAP_DSHOW`) or Media Foundation (`CAP_MSMF`) is used. Some webcams
        open under one backend and fail under another. Trying a small set of
        backends up front gives us a much better chance of a clean startup.
        """

        with self._capture_lock:
            if self._is_capture_open_locked():
                self._last_error = ""
                return True

            if cv2 is None:
                self._capture = None
                self._last_error = (
                    "OpenCV is not available. Camera cannot be opened. "
                    f"Import error: {cv2_error}"
                )
                return False

            self._release_capture_locked()

            backend_candidates: list[int | None] = []
            if hasattr(cv2, "CAP_DSHOW"):
                backend_candidates.append(int(cv2.CAP_DSHOW))
            if hasattr(cv2, "CAP_MSMF"):
                backend_candidates.append(int(cv2.CAP_MSMF))
            backend_candidates.append(None)

            last_error = (
                f"Failed to open camera index {self._camera_index}. "
                "No backend attempt has succeeded yet."
            )

            for backend in backend_candidates:
                try:
                    capture = self._create_capture(backend)
                except Exception as exc:
                    last_error = self._format_backend_error(
                        backend=backend,
                        message=f"VideoCapture constructor raised: {exc}",
                    )
                    continue

                if capture is None:
                    last_error = self._format_backend_error(
                        backend=backend,
                        message="VideoCapture returned None",
                    )
                    continue

                try:
                    if not capture.isOpened():
                        last_error = self._format_backend_error(
                            backend=backend,
                            message="Device did not open",
                        )
                        capture.release()
                        continue

                    self._configure_capture(capture)

                    # Read a warm-up frame before declaring success. A camera can
                    # report "opened" and still fail to deliver frames. We want
                    # `open()` to be honest because many later failures become
                    # much easier to debug if startup is strict.
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        last_error = self._format_backend_error(
                            backend=backend,
                            message="Opened device but could not read initial frame",
                        )
                        capture.release()
                        continue

                    self._capture = capture
                    self._last_error = ""
                    self._frame_counter = 0
                    self._store_frame_locked(frame)
                    return True
                except Exception as exc:
                    last_error = self._format_backend_error(
                        backend=backend,
                        message=f"Initialization failed after open: {exc}",
                    )
                    try:
                        capture.release()
                    except Exception:
                        pass

            self._capture = None
            self._last_error = last_error
            return False

    def close(self) -> None:
        """
        Stop background capture and release the camera safely.

        We stop the thread before releasing the device so there is no race where
        the capture loop tries to read from a handle that has already been
        destroyed.
        """

        self.stop()
        with self._capture_lock:
            self._release_capture_locked()
        with self._latest_frame_lock:
            self._latest_frame = None

    def is_open(self) -> bool:
        """Return True when the underlying camera handle is open."""

        with self._capture_lock:
            return self._is_capture_open_locked()

    def read_frame(self) -> CameraFrame | None:
        """
        Read a single frame directly from the camera.

        Returns:
            A `CameraFrame` on success, or `None` if the read fails.

        This method is the simplest synchronous path and is useful in tests,
        low-rate capture loops, or situations where a background thread is not
        needed yet.
        """

        if not self.is_open() and not self.open():
            return None

        with self._capture_lock:
            if not self._is_capture_open_locked():
                self._last_error = (
                    f"Camera index {self._camera_index} is not open after open attempt."
                )
                return None

            if self._capture is None:
                self._last_error = "Camera handle is missing after open attempt."
                return None

            try:
                ok, frame = self._capture.read()
            except Exception as exc:
                self._last_error = f"Camera read raised an exception: {exc}"
                return None

            if not ok or frame is None:
                self._last_error = (
                    f"Camera read failed for index {self._camera_index}. "
                    "OpenCV returned no frame."
                )
                return None

            self._last_error = ""
            return self._store_frame_locked(frame)

    def start(self) -> bool:
        """
        Start a lightweight background capture loop.

        Returns:
            True if the loop is running, otherwise False.

        The background loop lets later modules consume the latest frame without
        blocking on camera I/O every time. We keep this logic here because
        continuous capture is still part of camera ownership.
        """

        if self._running:
            return True

        if not self.open():
            return False

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="CameraManagerCapture",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """
        Stop the background capture loop if it is running.

        We do not release the camera handle here. `stop()` only stops the loop.
        `close()` is the stronger operation that also tears down the device.
        """

        if not self._running:
            return

        self._stop_event.set()
        thread = self._thread
        self._thread = None

        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

        self._running = False

    def is_running(self) -> bool:
        """Return True when the background capture thread is active."""

        return self._running

    def get_latest_frame(self) -> CameraFrame | None:
        """
        Return the newest captured frame, if one exists.

        We return the stored object as-is because downstream code should treat
        frames as read-only snapshots. If a later module needs defensive copies,
        it should make them explicitly at that boundary.
        """

        with self._latest_frame_lock:
            return self._latest_frame

    def set_camera_index(self, camera_index: int) -> None:
        """
        Switch to a different camera index.

        We fully close the current device before changing indices because many
        webcam drivers do not recover well if the old handle remains alive while
        a new index is opened.
        """

        was_running = self._running
        self.close()
        self._camera_index = int(camera_index)
        self._last_error = ""
        if was_running:
            self.start()

    def get_last_error(self) -> str:
        """Return the most recent human-readable camera error message."""

        return self._last_error

    def get_camera_index(self) -> int:
        """Return the currently configured camera index."""

        return self._camera_index

    def get_dimensions(self) -> tuple[int, int]:
        """Return the requested capture width and height."""

        return self._width, self._height

    def _capture_loop(self) -> None:
        """
        Continuously read frames while the camera manager is running.

        The loop is intentionally conservative:
        - short sleep on failure so we do not spin at 100% CPU
        - automatic self-stop if the device disappears for too long

        This gives the rest of the system a stable "latest frame" source
        without baking gesture-specific behavior into the camera layer.
        """

        consecutive_failures = 0
        max_failures = 50

        while not self._stop_event.is_set():
            frame = self.read_frame()
            if frame is not None:
                consecutive_failures = 0
                time.sleep(0.001)
                continue

            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                self._last_error = (
                    f"Camera index {self._camera_index} stopped delivering frames. "
                    "Background capture loop is stopping after repeated failures."
                )
                break

            time.sleep(0.02)

        self._running = False

    def _create_capture(self, backend: int | None) -> Any | None:
        """Create a `cv2.VideoCapture` for the configured camera index."""

        if cv2 is None:
            return None
        if backend is None:
            return cv2.VideoCapture(self._camera_index)
        return cv2.VideoCapture(self._camera_index, backend)

    def _configure_capture(self, capture: Any) -> None:
        """
        Apply conservative capture settings.

        These settings are not guarantees. Camera drivers may ignore them. We
        still set them because they improve responsiveness when supported,
        especially `CAP_PROP_BUFFERSIZE` which can reduce stale-frame lag.
        """

        if cv2 is None:
            return

        if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
            try:
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

        if hasattr(cv2, "CAP_PROP_FRAME_WIDTH"):
            try:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            except Exception:
                pass

        if hasattr(cv2, "CAP_PROP_FRAME_HEIGHT"):
            try:
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            except Exception:
                pass

    def _store_frame_locked(self, frame_bgr: Any) -> CameraFrame:
        """
        Normalize a raw OpenCV frame into the shared `CameraFrame` contract.

        The frame is mirrored horizontally because the current UI and recording
        workflow expect selfie-style feedback. Doing that once here keeps later
        modules from each making their own inconsistent decision.

        We make a defensive copy of the frame before any processing because
        some OpenCV backends reuse internal buffers across consecutive reads.
        Without the copy, the stored frame_bgr reference could silently point
        at stale or partially-overwritten memory by the next capture cycle.
        """

        if cv2 is not None:
            try:
                # Defensive copy: some camera backends reuse the internal
                # frame buffer on the next read(), which silently corrupts
                # any reference we hold.  Copying once up front is cheap
                # and guarantees downstream code sees a stable snapshot.
                frame_bgr = frame_bgr.copy()
                frame_bgr = cv2.flip(frame_bgr, 1)
            except Exception:
                # Mirroring improves UX, but capture should still succeed even if
                # the flip operation fails for an unusual frame object.
                pass

        self._frame_counter += 1
        frame = CameraFrame(
            frame_bgr=frame_bgr,
            frame_rgb=None,
            timestamp=time.monotonic(),
            frame_id=self._frame_counter,
            camera_index=self._camera_index,
        )

        with self._latest_frame_lock:
            self._latest_frame = frame

        return frame

    def _release_capture_locked(self) -> None:
        """Release the current OpenCV capture handle, ignoring secondary errors."""

        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
        self._capture = None

    def _is_capture_open_locked(self) -> bool:
        """Check whether the current capture handle is alive and open."""

        if self._capture is None:
            return False
        try:
            return bool(self._capture.isOpened())
        except Exception:
            return False

    def _format_backend_error(self, backend: int | None, message: str) -> str:
        """
        Build a readable backend-specific error message.

        These messages are meant to be shown in logs or status output. Being
        explicit about the backend tried makes webcam debugging much less
        frustrating on real machines.
        """

        backend_name = "default" if backend is None else str(backend)
        return (
            f"Camera open failed for index {self._camera_index} using backend "
            f"{backend_name}: {message}"
        )

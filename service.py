import importlib
import csv
import importlib
import json
import os
import shutil
import sys
import threading
import time
import traceback
import traceback
import uuid
import logging
import io

from flask import Flask, Response, request, jsonify
from gevent.pywsgi import WSGIServer

from utils.helpers import (
    SETTINGS_PATH,
    append_engine_event,
    get_setting,
    load_gesture_mapping,
    load_settings,
    save_gesture_mapping,
    save_json,
    write_runtime_state
)

RESTART_SENSITIVE_SETTINGS = {
    "camera_index",
    "camera_width",
    "camera_height",
    "max_hands",
    "hand_model_complexity",
    "hand_min_detection_confidence",
    "hand_min_tracking_confidence",
    "voice_enabled",
    "voice_model_dir",
    "voice_sample_rate"
}


class JsonEmitter:
    def __init__(self):
        self._lock = threading.Lock()

    def emit(self, msg_type, data=None, request_id=None, ok=True):
        payload = {
            "type": msg_type,
            "time": time.time(),
            "ok": bool(ok),
            "data": data or {}
        }
        if request_id is not None:
            payload["id"] = request_id
        line = json.dumps(payload, ensure_ascii=True)
        with self._lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()


def _merge_dict(base, updates):
    out = dict(base or {})
    for key, value in (updates or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_dict(out[key], value)
        else:
            out[key] = value
    return out


# --- FLASK STREAMING SERVER ---

class StreamingServer:
    def __init__(self):
        self.app = Flask(__name__)
        self.frame_data = None
        self.lock = threading.Lock()
        self.server = None
        self.thread = None

        # Disable Flask logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        @self.app.route('/video_feed')
        def video_feed():
            return Response(self.generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

        @self.app.route('/training_feed')
        def training_feed():
            return Response(self.generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    def update_frame(self, jpeg_bytes):
        with self.lock:
            self.frame_data = jpeg_bytes

    def generate(self):
        while True:
            with self.lock:
                if self.frame_data is None:
                    time.sleep(0.05)
                    continue
                data = self.frame_data
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + data + b'\r\n')
            time.sleep(0.04) # Limit FPS slightly for streaming

    def run(self, host='127.0.0.1', port=5000):
        try:
            self.server = WSGIServer((host, port), self.app)
            self.server.serve_forever()
        except Exception:
            pass

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.stop()
            self.server = None


# --- TRAINING COORDINATOR (Existing Code) ---


class TrainingCoordinator:
    def __init__(self, emitter):
        self.emitter = emitter
        self._lock = threading.Lock()
        self._job = None
        self.stream_callback = None

    def current(self):
        with self._lock:
            return self._job

    def _clear_if(self, session_id):
        with self._lock:
            if self._job and self._job.get("session_id") == session_id:
                self._job = None

    def _gesture_name_from_payload(self, payload, fallback):
        candidates = [
            payload.get("gestureName"),
            payload.get("title"),
            payload.get("gestureId"),
            fallback
        ]
        for value in candidates:
            name = str(value or "").strip()
            if name:
                return name[:80]
        return fallback

    def _default_action_from_payload(self, payload, gesture_type):
        action = payload.get("action")
        if isinstance(action, (str, dict)):
            return action
        if gesture_type == "voice":
            voice_action = payload.get("voiceAction")
            if isinstance(voice_action, (str, dict)):
                return voice_action
            return "Click"
        return "Click"

    def start(self, payload):
        payload = payload or {}
        gesture_id = str(payload.get("gestureId") or "").strip() or f"gesture-{int(time.time())}"
        gesture_type = "voice" if str(payload.get("type")).strip().lower() == "voice" else "hand"
        session_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"

        # Cancel older job first.
        self.cancel()

        cancel_event = threading.Event()
        job = {
            "session_id": session_id,
            "gesture_id": gesture_id,
            "type": gesture_type,
            "payload": payload,
            "cancel_event": cancel_event,
            "done": False
        }
        with self._lock:
            self._job = job

        thread = threading.Thread(target=self._run, args=(job,), daemon=True)
        job["thread"] = thread
        thread.start()

        return {"sessionId": session_id, "gestureId": gesture_id, "type": gesture_type}

    def _emit_progress(
        self,
        job,
        progress,
        done=False,
        cancelled=False,
        failed=False,
        error=None,
        result=None
    ):
        self.emitter.emit(
            "training.progress",
            {
                "sessionId": job["session_id"],
                "gestureId": job["gesture_id"],
                "type": job["type"],
                "progress": int(max(0, min(100, progress))),
                "done": bool(done),
                "cancelled": bool(cancelled),
                "failed": bool(failed),
                "error": str(error) if error else "",
                "result": result or {}
            }
        )

    def _append_samples(self, rows):
        if not rows:
            return
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_root = os.environ.get("OCTAVE_DATA_DIR", "").strip() or base_dir
        if not os.path.isabs(data_root):
            data_root = os.path.abspath(os.path.join(base_dir, data_root))
        csv_path = os.path.join(data_root, "ml_engine", "data", "static_gestures.csv")
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def _run_voice_training(self, job):
        from ml_engine.gesture_manager import set_voice_action

        payload = job.get("payload") or {}
        phrase = str(payload.get("phrase") or "").strip().lower()
        action = self._default_action_from_payload(payload, "voice")

        self._emit_progress(job, 0, done=False)
        for progress in [8, 16, 24, 34, 44, 55, 66, 78, 88, 96]:
            if job["cancel_event"].is_set():
                self._emit_progress(job, 0, done=False, cancelled=True)
                return
            self._emit_progress(job, progress, done=False)
            time.sleep(0.22)

        if phrase and phrase != "your custom phrase":
            set_voice_action(phrase, action)

        self._emit_progress(
            job,
            100,
            done=True,
            result={"phrase": phrase, "action": action}
        )

    def _run_hand_training(self, job):
        self._emit_progress(job, 1, done=False)
        append_engine_event(
            "training_stage",
            {"sessionId": job["session_id"], "gestureId": job["gesture_id"], "stage": "imports_start"}
        )
        import cv2
        import mediapipe as mp

        from ml_engine.feature_extraction import extract_features
        from ml_engine.gesture_manager import add_gesture, retrain_static_model, set_static_action
        append_engine_event(
            "training_stage",
            {"sessionId": job["session_id"], "gestureId": job["gesture_id"], "stage": "imports_done"}
        )

        payload = job.get("payload") or {}
        gesture_name = self._gesture_name_from_payload(payload, job["gesture_id"])
        action = self._default_action_from_payload(payload, "hand")
        is_locked = bool(payload.get("locked"))

        target_samples_raw = payload.get("targetSamples")
        if target_samples_raw is None:
            target_samples_raw = get_setting("dataset_target_samples", 180)
        target_samples = max(50, min(240, int(target_samples_raw)))
        capture_interval = float(
            payload.get("captureIntervalSec", get_setting("dataset_capture_interval_sec", 0.09))
        )

        append_engine_event(
            "training_stage",
            {"sessionId": job["session_id"], "gestureId": job["gesture_id"], "stage": "labeling"}
        )
        label = add_gesture(gesture_name)
        if not is_locked:
            set_static_action(gesture_name, action)

        self._emit_progress(job, 2, done=False)
        append_engine_event(
            "training_stage",
            {"sessionId": job["session_id"], "gestureId": job["gesture_id"], "stage": "camera_prepare"}
        )

        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(
            max_num_hands=1,
            model_complexity=int(get_setting("hand_model_complexity", 0)),
            min_detection_confidence=float(get_setting("hand_min_detection_confidence", 0.6)),
            min_tracking_confidence=float(get_setting("hand_min_tracking_confidence", 0.55))
        )

        camera_index = int(get_setting("camera_index", 0))
        cap = None
        for attempt in range(5):
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                break
            time.sleep(0.4)
        
        if not cap or not cap.isOpened():
            hands.close()
            raise RuntimeError(f"Unable to open camera index {camera_index} (busy?)")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(get_setting("camera_width", 960)))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(get_setting("camera_height", 540)))

        rows = []
        samples = 0
        last_capture_t = 0.0
        capture_start_t = time.time()
        max_capture_wait = float(payload.get("maxCaptureWaitSec", 90))
        append_engine_event(
            "training_stage",
            {"sessionId": job["session_id"], "gestureId": job["gesture_id"], "stage": "capture_loop"}
        )

        try:
            while samples < target_samples:
                if job["cancel_event"].is_set():
                    self._emit_progress(job, 0, done=False, cancelled=True)
                    return

                if time.time() - capture_start_t > max_capture_wait:
                    raise RuntimeError(
                        "Timed out while capturing samples. Keep your hand in frame and retry."
                    )

                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.01)
                    time.sleep(0.01)
                    continue

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(rgb)
                if not result.multi_hand_landmarks:
                    # Stream even if no hands found
                    if self.stream_callback:
                        ret, jpeg = cv2.imencode('.jpg', frame)
                        if ret:
                            self.stream_callback(jpeg.tobytes())
                    continue

                # Draw landmarks for stream
                if self.stream_callback:
                    annotated = frame.copy()
                    for hand_landmarks in result.multi_hand_landmarks:
                        mp.solutions.drawing_utils.draw_landmarks(
                            annotated,
                            hand_landmarks,
                            mp.solutions.hands.HAND_CONNECTIONS
                        )
                    # Add simple overlay
                    cv2.putText(annotated, f"Samples: {samples}/{target_samples}", (20, 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    ret, jpeg = cv2.imencode('.jpg', annotated)
                    if ret:
                        self.stream_callback(jpeg.tobytes())

                now_t = time.time()
                if now_t - last_capture_t < capture_interval:
                    continue
                hand = result.multi_hand_landmarks[0]
                feat = extract_features(hand)
                rows.append(list(feat) + [int(label)])
                samples += 1
                last_capture_t = now_t
                progress = 5 + int((samples / target_samples) * 72)
                self._emit_progress(job, progress, done=False)
        finally:
            cap.release()
            hands.close()

        if job["cancel_event"].is_set():
            self._emit_progress(job, 0, done=False, cancelled=True)
            return

        self._append_samples(rows)
        self._emit_progress(job, 80, done=False)
        append_engine_event(
            "training_stage",
            {"sessionId": job["session_id"], "gestureId": job["gesture_id"], "stage": "retrain"}
        )

        epochs_raw = payload.get("epochs", get_setting("static_train_epochs", 55))
        epochs = max(10, min(140, int(epochs_raw)))

        def on_epoch(epoch_idx, total_epochs, _loss):
            if job["cancel_event"].is_set():
                return False
            progress = 82 + int((epoch_idx / max(1, total_epochs)) * 16)
            self._emit_progress(job, progress, done=False)
            return True

        retrain_out = retrain_static_model(progress_callback=on_epoch, epochs=epochs)

        if job["cancel_event"].is_set():
            self._emit_progress(job, 0, done=False, cancelled=True)
            return

        self._emit_progress(
            job,
            100,
            done=True,
            result={
                "label": label,
                "gestureName": gesture_name,
                "samples": samples,
                "retrain": retrain_out or {}
            }
        )

    def _run(self, job):
        try:
            append_engine_event(
                "training_started",
                {"sessionId": job["session_id"], "gestureId": job["gesture_id"], "type": job["type"]}
            )
            if job["type"] == "voice":
                self._run_voice_training(job)
            else:
                self._run_hand_training(job)
            job["done"] = True
            append_engine_event(
                "training_completed",
                {"sessionId": job["session_id"], "gestureId": job["gesture_id"], "type": job["type"]}
            )
        except Exception as exc:
            append_engine_event(
                "training_failed",
                {"sessionId": job["session_id"], "gestureId": job["gesture_id"], "error": str(exc)}
            )
            self._emit_progress(job, 0, done=False, failed=True, error=str(exc))
        finally:
            self._clear_if(job["session_id"])

    def cancel(self):
        with self._lock:
            job = self._job
        if not job:
            return False
        job["cancel_event"].set()
        thread = job.get("thread")
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self._clear_if(job["session_id"])
        return True

    def complete(self):
        with self._lock:
            job = self._job
        if not job:
            return False
        self._emit_progress(job, 100, done=True)
        job["done"] = True
        job["cancel_event"].set()
        thread = job.get("thread")
        if thread and thread.is_alive():
            thread.join(timeout=0.8)
        self._clear_if(job["session_id"])
        return True


class RuntimeEngine:
    def __init__(self, emitter):
        self.emitter = emitter
        self._thread = None
        self._stop_event = threading.Event()
        self._running = False
        self._state_lock = threading.Lock()
        self._last_state = {
            "running": False,
            "dynamic_family": None,
            "dynamic_intent": None,
            "confidence": 0.0,
            "static_gesture": None,
            "voice_phrase": None,
            "mode": "CURSOR",
            "fps": 0.0
        }
        self._last_error = None

    def is_running(self):
        return self._running

    def last_error(self):
        return self._last_error

    def get_state(self):
        with self._state_lock:
            return dict(self._last_state)

    def health(self):
        modules = [
            "cv2",
            "mediapipe",
            "numpy",
            "torch",
            "pandas",
            "mss",
            "pyautogui",
            "vosk",
            "sounddevice"
        ]
        checks = {}
        for name in modules:
            try:
                importlib.import_module(name)
                checks[name] = {"ok": True}
            except Exception as exc:
                checks[name] = {"ok": False, "error": str(exc)}
        return {
            "python": sys.version,
            "executable": sys.executable,
            "modules": checks
        }

    def start(self):
        if self._running:
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._running = True
        self._last_error = None
        self._thread.start()
        self.emitter.emit("engine.status", {"running": True, "phase": "starting"})
        return True

    def stop(self):
        if not self._running:
            return True
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.8)
        self._running = False
        with self._state_lock:
            self._last_state["running"] = False
        self.emitter.emit("engine.status", {"running": False, "phase": "stopped"})
        return True

    def _set_error(self, stage, exc):
        self._last_error = f"{stage}: {exc}"
        append_engine_event("engine_error", {"stage": stage, "error": str(exc)})
        self.emitter.emit(
            "engine.error",
            {
                "stage": stage,
                "error": str(exc)
            },
            ok=False
        )

    def _loop(self):
        cap = None
        voice_listener = None
        hands = None
        try:
            import cv2
            import mediapipe as mp
        except Exception as exc:
            self._set_error("imports", exc)
            self._running = False
            return

        try:
            cv2.setUseOptimized(True)
        except Exception:
            pass

        try:
            from dynamic_engine.drs_gesture import detect_drs
            from dynamic_engine.family_detector import DynamicFamilyDetector
            from intent_engine.context_engine.intent_adapter import cycle_override, get_active_intent
            from intent_engine.intent_resolver import execute_custom_action, resolve_intent
            from intent_engine.mode_manager import get_mode
            from intent_engine.stability_filter import stable_gesture
            from ml_engine.feature_extraction import extract_features
            from ml_engine.static_runtime import init_static_model, run_static_inference
            from screen_engine.screen_capture import capture_resized
            from screen_engine.semantic_extractor import extract_semantic_features
            from voice_engine.vosk_listener import VoskVoiceListener
        except Exception as exc:
            self._set_error("module_load", exc)
            self._running = False
            return

        family_detector = DynamicFamilyDetector()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_root = os.environ.get("OCTAVE_DATA_DIR", "").strip() or base_dir
        if not os.path.isabs(data_root):
            data_root = os.path.abspath(os.path.join(base_dir, data_root))

        data_dir = os.path.join(data_root, "ml_engine", "data")
        template_data_dir = os.path.join(base_dir, "ml_engine", "data")

        label_map_path = os.path.join(data_dir, "label_map.json")
        model_path = os.path.join(data_dir, "models", "static_model.pth")

        template_label_map_path = os.path.join(template_data_dir, "label_map.json")
        if not os.path.exists(label_map_path) and os.path.exists(template_label_map_path):
            os.makedirs(os.path.dirname(label_map_path), exist_ok=True)
            shutil.copyfile(template_label_map_path, label_map_path)

        voice_model_dir = str(get_setting("voice_model_dir", "vosk-model-small-en-us-0.15"))
        data_voice_model_path = os.path.join(data_dir, voice_model_dir)
        template_voice_model_path = os.path.join(template_data_dir, voice_model_dir)
        vosk_model_path = (
            data_voice_model_path
            if os.path.exists(data_voice_model_path)
            else template_voice_model_path
        )

        def _load_label_map():
            try:
                with open(label_map_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                return {str(k): str(v) for k, v in data.items()}
            except Exception:
                return {}

        label_map = _load_label_map()
        if label_map and os.path.exists(model_path):
            init_static_model(model_path, 63, len(label_map))

        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(
            max_num_hands=int(get_setting("max_hands", 2)),
            model_complexity=int(get_setting("hand_model_complexity", 0)),
            min_detection_confidence=float(get_setting("hand_min_detection_confidence", 0.6)),
            min_tracking_confidence=float(get_setting("hand_min_tracking_confidence", 0.55))
        )

        camera_index_raw = get_setting("camera_index", 0)
        try:
            camera_index = int(camera_index_raw)
        except Exception:
            camera_index = 0
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            self._set_error("camera_open", f"Unable to open camera index {camera_index}")
            self._running = False
            return

        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(get_setting("camera_width", 960)))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(get_setting("camera_height", 540)))

        sem_interval = float(get_setting("semantic_interval_sec", 0.4))
        state_interval = float(get_setting("runtime_state_interval_sec", 0.2))
        reload_interval = float(get_setting("model_reload_interval_sec", 2.0))

        last_state_write = 0.0
        last_semantic_t = 0.0
        last_reload_t = 0.0
        last_semantic = {}
        last_family = None
        last_intent = None
        last_static = None
        last_conf = 0.0
        last_voice_phrase = None
        last_label_mtime = os.path.getmtime(label_map_path) if os.path.exists(label_map_path) else 0.0
        last_model_mtime = os.path.getmtime(model_path) if os.path.exists(model_path) else 0.0
        prev_t = time.time()
        fps = 0.0

        try:
            voice_listener = VoskVoiceListener(vosk_model_path)
            voice_listener.start()
        except Exception as exc:
            self._set_error("voice_start", exc)
            voice_listener = None

        append_engine_event("engine_started", {"voice_model_path": vosk_model_path})
        self.emitter.emit("engine.status", {"running": True, "phase": "active"})

        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.02)
                    continue

                now_t = time.time()
                dt = max(1e-6, now_t - prev_t)
                prev_t = now_t
                fps = 0.88 * fps + 0.12 * (1.0 / dt)

                if now_t - last_reload_t >= reload_interval:
                    current_label_mtime = (
                        os.path.getmtime(label_map_path) if os.path.exists(label_map_path) else 0.0
                    )
                    current_model_mtime = (
                        os.path.getmtime(model_path) if os.path.exists(model_path) else 0.0
                    )
                    if current_label_mtime != last_label_mtime:
                        label_map = _load_label_map()
                        last_label_mtime = current_label_mtime
                    if (
                        current_model_mtime != last_model_mtime
                        and label_map
                        and os.path.exists(model_path)
                    ):
                        init_static_model(model_path, 63, len(label_map))
                        last_model_mtime = current_model_mtime
                    last_reload_t = now_t

                if now_t - last_semantic_t >= sem_interval:
                    try:
                        screen_small = capture_resized()
                        last_semantic = extract_semantic_features(screen_small)
                    except Exception:
                        last_semantic = {}
                    last_semantic_t = now_t

                voice_event = voice_listener.poll_event() if voice_listener else None
                if voice_event:
                    executed = execute_custom_action(voice_event.get("action"))
                    last_voice_phrase = voice_event.get("phrase")
                    self.emitter.emit(
                        "engine.voice",
                        {
                            "phrase": voice_event.get("phrase"),
                            "executed": bool(executed)
                        }
                    )

                gesture_name = None
                family = None
                intent = None
                confidence = 0.0

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(rgb)

                if result.multi_hand_landmarks:
                    hands_list = result.multi_hand_landmarks

                    if len(hands_list) >= 2:
                        try:
                            if detect_drs(hands_list[0], hands_list[1]):
                                resolve_intent(None, gesture_name="DRS T-Frame")
                                gesture_name = "DRS T-Frame"
                        except Exception:
                            pass

                    hand = hands_list[0]
                    try:
                        features = extract_features(hand)
                        gesture_id = run_static_inference(features, hand)
                    except Exception:
                        gesture_id = -1

                    if gesture_id != -1:
                        raw = label_map.get(str(gesture_id), "UNKNOWN")
                        gesture_name = stable_gesture(raw)

                    family = family_detector.detect(hand)
                    if family:
                        intent, confidence = get_active_intent(family, last_semantic or {})

                    if gesture_name == "Three Fingers" and family:
                        cycle_override(family, intent)
                        intent, confidence = get_active_intent(family, last_semantic or {})

                    resolve_intent(hand, gesture_name=gesture_name, family=family, intent=intent)

                if family:
                    last_family = family
                if intent:
                    last_intent = intent
                    last_conf = confidence
                if gesture_name:
                    last_static = gesture_name

                # ENCODE AND UPDATE STREAM
                try:
                    # Draw landmarks on a copy for streaming
                    annotated_frame = frame.copy()
                            
                    # Simple landmark drawing if we have results
                    if result.multi_hand_landmarks:
                        for hand_landmarks in result.multi_hand_landmarks:
                            mp.solutions.drawing_utils.draw_landmarks(
                                annotated_frame,
                                hand_landmarks,
                                mp_hands.HAND_CONNECTIONS
                            )
                    
                    # Add overlays
                    cv2.putText(annotated_frame, f"Mode: {get_mode()}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    if last_family:
                         cv2.putText(annotated_frame, f"Family: {last_family}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                    if last_intent:
                        cv2.putText(annotated_frame, f"Intent: {last_intent} ({last_conf:.2f})", (20, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                    ret, jpeg = cv2.imencode('.jpg', annotated_frame)
                    if ret and hasattr(self, 'stream_callback') and self.stream_callback:
                        self.stream_callback(jpeg.tobytes())
                except Exception:
                    pass

                if now_t - last_state_write >= state_interval:
                    runtime = {
                        "running": True,
                        "dynamic_family": last_family,
                        "dynamic_intent": last_intent,
                        "confidence": round(float(last_conf), 4),
                        "static_gesture": last_static,
                        "voice_phrase": last_voice_phrase,
                        "mode": get_mode(),
                        "fps": round(float(fps), 2),
                        "semantic_features": last_semantic or {}
                    }
                    write_runtime_state(runtime)
                    with self._state_lock:
                        self._last_state = dict(runtime)
                    self.emitter.emit("engine.runtime", runtime)
                    last_state_write = now_t
        except Exception as exc:
            self._set_error("runtime_loop", exc)
            self.emitter.emit(
                "engine.error",
                {"traceback": traceback.format_exc()},
                ok=False
            )
        finally:
            if cap is not None:
                cap.release()
            if voice_listener:
                try:
                    voice_listener.stop()
                except Exception:
                    pass
            if hands is not None:
                try:
                    hands.close()
                except Exception:
                    pass
            self._running = False
            with self._state_lock:
                self._last_state["running"] = False
            append_engine_event("engine_stopped", {})
            self.emitter.emit("engine.status", {"running": False, "phase": "stopped"})



class EngineService:
    def __init__(self):
        self.emitter = JsonEmitter()
        self.runtime = RuntimeEngine(self.emitter)
        self.training = TrainingCoordinator(self.emitter)
        
        # Start Streaming Server
        self.stream_server = StreamingServer()
        self.stream_server.start()
        
        # Connect Runtime to Stream Server
        self.runtime.stream_callback = self.stream_server.update_frame
        self.training.stream_callback = self.stream_server.update_frame

        
        # Monkey patch runtime to inspect frames
        self._original_runtime_loop = self.runtime._loop
        self.runtime._loop = self._patched_loop

    def _patched_loop(self):
        # This wrapper injects frame extraction logic into the runtime loop
        # We'll need to modify RuntimeEngine to support a callback or external access
        # For now, let's redefine RuntimeEngine._loop in place or subclass it. 
        # Actually, simpler approach: modify RuntimeEngine class directly above.
        # But since I'm editing the file, I'll modify RuntimeEngine directly in the next chunk.
        self._original_runtime_loop()

    def _ack(self, request_id, result=None):
        self.emitter.emit("response", result or {}, request_id=request_id, ok=True)

    def _nack(self, request_id, error):
        self.emitter.emit("response", {"error": str(error)}, request_id=request_id, ok=False)

    def _save_settings(self, updates):
        current = load_settings(force=True)
        merged = _merge_dict(current, updates or {})
        save_json(SETTINGS_PATH, merged)
        return load_settings(force=True)

    def _save_mapping(self, updates):
        current = load_gesture_mapping(force=True)
        payload = updates or {}
        merged = _merge_dict(
            current,
            {k: v for k, v in payload.items() if k not in {"disabled_static", "voice_actions"}}
        )

        if "disabled_static" in payload:
            raw_disabled = payload.get("disabled_static") or []
            if isinstance(raw_disabled, list):
                disabled = []
                seen = set()
                for item in raw_disabled:
                    name = str(item).strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    disabled.append(name)
                merged["disabled_static"] = disabled

        if "voice_actions" in payload and isinstance(payload.get("voice_actions"), dict):
            merged["voice_actions"] = payload.get("voice_actions")

        save_gesture_mapping(merged)
        return load_gesture_mapping(force=True)

    def handle(self, message):
        request_id = message.get("id")
        cmd = str(message.get("cmd") or "").strip()
        payload = message.get("payload") or {}

        try:
            if cmd in {"health", "engine.health"}:
                self._ack(
                    request_id,
                    {
                        "runtimeRunning": self.runtime.is_running(),
                        "lastError": self.runtime.last_error(),
                        "health": self.runtime.health()
                    }
                )
                return

            if cmd == "engine.start":
                self.runtime.start()
                self._ack(
                    request_id,
                    {"running": self.runtime.is_running(), "lastError": self.runtime.last_error()}
                )
                return

            if cmd == "engine.stop":
                self.runtime.stop()
                self._ack(request_id, {"running": self.runtime.is_running()})
                return

            if cmd == "engine.get_state":
                self._ack(request_id, {"state": self.runtime.get_state()})
                return

            if cmd == "engine.update_settings":
                saved = self._save_settings(payload)
                restart_required = (
                    self.runtime.is_running()
                    and isinstance(payload, dict)
                    and any(key in payload for key in RESTART_SENSITIVE_SETTINGS)
                )
                restarted = False
                if restart_required:
                    self.runtime.stop()
                    self.runtime.start()
                    restarted = True
                self._ack(
                    request_id,
                    {
                        "saved": True,
                        "settings": saved,
                        "running": self.runtime.is_running(),
                        "restarted": restarted,
                        "lastError": self.runtime.last_error()
                    }
                )
                return

            if cmd == "engine.update_mapping":
                saved = self._save_mapping(payload)
                self._ack(request_id, {"saved": True, "mapping": saved})
                return

            if cmd == "training.start":
                # Stop runtime to free camera resource for training
                if self.runtime.is_running():
                    self.runtime.stop()
                    
                out = self.training.start(payload)
                self._ack(request_id, out)
                return

            if cmd == "training.cancel":
                ok = self.training.cancel()
                # Restart runtime for live monitoring
                self.runtime.start()
                self._ack(request_id, {"cancelled": bool(ok)})
                return

            if cmd == "training.complete":
                ok = self.training.complete()
                # Restart runtime for live monitoring
                self.runtime.start()
                self._ack(request_id, {"completed": bool(ok)})
                return

            if cmd == "ping":
                self._ack(request_id, {"pong": True})
                return

            self._nack(request_id, f"Unknown command: {cmd}")
        except Exception as exc:
            append_engine_event("service_error", {"cmd": cmd, "error": str(exc)})
            self._nack(request_id, exc)

    def run_forever(self):
        self.emitter.emit(
            "engine.ready",
            {
                "pid": os.getpid(),
                "cwd": os.getcwd(),
                "python": sys.executable
            }
        )

        while True:
            raw = sys.stdin.readline()
            if raw == "":
                # parent process closed pipe
                self.runtime.stop()
                self.training.cancel()
                break
            line = raw.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception as exc:
                self.emitter.emit("response", {"error": f"Invalid JSON: {exc}"}, ok=False)
                continue
            self.handle(msg)


if __name__ == "__main__":
    EngineService().run_forever()

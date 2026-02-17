import os
import json
import time
import queue
import threading

from utils.helpers import load_gesture_mapping, get_setting, append_engine_event


class VoskVoiceListener:
    def __init__(self, model_path):
        self.model_path = model_path
        self.enabled = bool(get_setting("voice_enabled", True))
        self.sample_rate = int(get_setting("voice_sample_rate", 16000))
        self.cooldown = float(get_setting("voice_phrase_cooldown_sec", 1.0))
        self.q = queue.Queue()
        self.thread = None
        self.running = False
        self.event = None
        self.last_phrase_time = {}
        self._mapping = {}
        self._mapping_mtime = 0.0
        self._lock = threading.Lock()

    def _load_mapping(self, force=False):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "gesture_mapping.json")
        mtime = os.path.getmtime(path) if os.path.exists(path) else 0.0
        if not force and mtime == self._mapping_mtime and self._mapping:
            return self._mapping
        mapping = load_gesture_mapping(force=True)
        self._mapping = mapping.get("voice_actions", {}) or {}
        self._mapping_mtime = mtime
        return self._mapping

    def _grammar_json(self):
        mapping = self._load_mapping()
        phrases = sorted({p.strip().lower() for p in mapping.keys() if str(p).strip()})
        if not phrases:
            return None
        return json.dumps(phrases)

    def _accept_phrase(self, phrase):
        phrase = str(phrase).strip().lower()
        if not phrase:
            return
        mapping = self._load_mapping()
        action = mapping.get(phrase)
        if not action:
            return
        now = time.time()
        if now - self.last_phrase_time.get(phrase, 0) < self.cooldown:
            return
        self.last_phrase_time[phrase] = now
        with self._lock:
            self.event = {
                "phrase": phrase,
                "action": action,
                "time": now
            }
        append_engine_event("voice_phrase", {"phrase": phrase})

    def _run(self):
        try:
            from vosk import Model, KaldiRecognizer
            import sounddevice as sd
        except Exception:
            self.running = False
            return

        if not self.enabled:
            self.running = False
            return

        if not os.path.isdir(self.model_path):
            self.running = False
            return

        try:
            grammar = self._grammar_json()
            model = Model(self.model_path)
            if grammar:
                rec = KaldiRecognizer(model, self.sample_rate, grammar)
            else:
                rec = KaldiRecognizer(model, self.sample_rate)
        except Exception:
            self.running = False
            return

        def callback(indata, frames, t, status):
            if status:
                return
            self.q.put(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=callback
            ):
                while self.running:
                    data = self.q.get()
                    if rec.AcceptWaveform(data):
                        out = json.loads(rec.Result())
                        self._accept_phrase(out.get("text", ""))
                    else:
                        _ = rec.PartialResult()
        except Exception:
            self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def poll_event(self):
        self._load_mapping()
        with self._lock:
            ev = self.event
            self.event = None
        return ev

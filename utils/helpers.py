import os
import json
import time


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(BASE_DIR, "config", "settings.json")
GESTURE_MAPPING_PATH = os.path.join(BASE_DIR, "config", "gesture_mapping.json")
RUNTIME_STATE_PATH = os.path.join(BASE_DIR, "config", "runtime_state.json")
ENGINE_COMMANDS_PATH = os.path.join(BASE_DIR, "config", "engine_commands.jsonl")
ENGINE_EVENTS_PATH = os.path.join(BASE_DIR, "config", "engine_events.jsonl")


DEFAULT_SETTINGS = {
    "semantic_interval_sec": 0.4,
    "runtime_state_interval_sec": 0.2,
    "command_poll_interval_sec": 0.25,
    "model_reload_interval_sec": 2.0,
    "max_hands": 2,
    "camera_index": 0,
    "camera_width": 960,
    "camera_height": 540,
    "draw_landmarks": True,
    "hand_model_complexity": 0,
    "hand_min_detection_confidence": 0.6,
    "hand_min_tracking_confidence": 0.55,
    "voice_enabled": True,
    "voice_model_dir": "vosk-model-small-en-us-0.15",
    "voice_sample_rate": 16000,
    "voice_phrase_cooldown_sec": 1.0,
    "static_confidence_threshold": 0.7,
    "intent_safety_threshold": 0.55,
    "override_duration_sec": 5.0,
    "mode_switch_cooldown_sec": 1.5,
    "drs_hold_time_sec": 0.5,
    "system_action_cooldown_sec": 2.0,
    "dataset_target_samples": 320,
    "dataset_capture_interval_sec": 0.09,
    "mss_monitor_index": 1,
    "brightness_display_index": 0,
    "dynamic_modes": [
        "CURSOR",
        "VOLUME",
        "BRIGHTNESS",
        "SCROLL",
        "ZOOM",
        "NAVIGATION",
        "ROTATION"
    ],
    "gesture_cooldowns": {
        "Fist": 1.5,
        "Thumb": 1.5,
        "V Sign": 1.5,
        "OK Sign": 1.0,
        "Three Fingers": 1.5,
        "DRS T-Frame": 2.0
    },
    "system_commands": {
        "play_pause": "nircmd sendkeypress space",
        "mute_toggle": "nircmd mutesysvolume 2"
    }
}

_cache = None
_cache_time = 0
_mapping_cache = None
_mapping_mtime = 0.0


def _merge(defaults, incoming):
    out = dict(defaults)
    if not isinstance(incoming, dict):
        return out
    for k, v in incoming.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings(force=False):
    global _cache, _cache_time
    now = time.time()
    if not force and _cache is not None and now - _cache_time < 1.0:
        return _cache
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}
    _cache = _merge(DEFAULT_SETTINGS, data)
    _cache_time = now
    return _cache


def get_setting(key, fallback=None):
    settings = load_settings()
    if key in settings:
        return settings[key]
    return fallback


def write_runtime_state(state):
    payload = dict(state or {})
    payload["timestamp"] = time.time()
    try:
        os.makedirs(os.path.dirname(RUNTIME_STATE_PATH), exist_ok=True)
        with open(RUNTIME_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass


def load_json(path, fallback=None):
    if fallback is None:
        fallback = {}
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def save_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def default_gesture_mapping():
    return {
        "dynamic_families": {
            "MAGNITUDE": ["Volume", "Brightness", "Zoom", "ScrollSpeed", "PlaybackSpeed"],
            "CURSOR": ["FreeMove", "HoverFocus", "PrecisionPoint", "TextFieldFocus"],
            "GRAB": ["WindowDrag", "ObjectMove", "Resize", "SelectionBox"],
            "NAVIGATION": ["TabSwitch", "DesktopSwitch", "SlideNavigate", "TimelineJump"],
            "ROTATION": ["KnobAdjust", "ObjectRotate"],
            "SCROLL": ["VerticalScroll"]
        },
        "static_actions": {
            "Fist": "PlayPause",
            "Thumb": "MuteToggle",
            "V Sign": "AltRight",
            "OK Sign": "Click",
            "Three Fingers": "ModeSwitch",
            "DRS T-Frame": "OpenVSCode"
        },
        "voice_actions": {}
    }


def load_gesture_mapping(force=False):
    global _mapping_cache, _mapping_mtime
    if not os.path.exists(GESTURE_MAPPING_PATH):
        payload = default_gesture_mapping()
        save_json(GESTURE_MAPPING_PATH, payload)
        _mapping_cache = payload
        _mapping_mtime = os.path.getmtime(GESTURE_MAPPING_PATH)
        return payload
    mtime = os.path.getmtime(GESTURE_MAPPING_PATH)
    if not force and _mapping_cache is not None and mtime == _mapping_mtime:
        return _mapping_cache
    payload = load_json(GESTURE_MAPPING_PATH, default_gesture_mapping())
    payload = _merge(default_gesture_mapping(), payload)
    _mapping_cache = payload
    _mapping_mtime = mtime
    return payload


def save_gesture_mapping(payload):
    global _mapping_cache, _mapping_mtime
    data = _merge(default_gesture_mapping(), payload or {})
    save_json(GESTURE_MAPPING_PATH, data)
    _mapping_cache = data
    _mapping_mtime = os.path.getmtime(GESTURE_MAPPING_PATH)


def append_jsonl(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def append_engine_event(event_type, data=None):
    payload = {
        "type": event_type,
        "time": time.time(),
        "data": data or {}
    }
    append_jsonl(ENGINE_EVENTS_PATH, payload)

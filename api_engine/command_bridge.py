import os
import json
import time

from utils.helpers import ENGINE_COMMANDS_PATH, append_engine_event
from ml_engine.gesture_manager import (
    add_gesture,
    rename_gesture,
    delete_gesture,
    collect_samples_for_label,
    retrain_static_model,
    set_static_action,
    delete_static_action,
    set_voice_action,
    delete_voice_action
)


class CommandBridge:
    def __init__(self):
        self.last_mtime = 0.0

    def _read_commands(self):
        path = ENGINE_COMMANDS_PATH
        if not os.path.exists(path):
            return []
        mtime = os.path.getmtime(path)
        if mtime == self.last_mtime:
            return []
        self.last_mtime = mtime
        commands = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        commands.append(json.loads(line))
                    except Exception:
                        append_engine_event("command_error", {"line": line, "error": "invalid_json"})
            open(path, "w", encoding="utf-8").close()
        except Exception as e:
            append_engine_event("command_error", {"error": str(e)})
        return commands

    def _handle(self, cmd):
        kind = str(cmd.get("cmd", "")).strip()

        if kind == "add_gesture":
            name = cmd.get("name", "")
            label = add_gesture(name)
            if cmd.get("collect", False):
                collect_samples_for_label(label)
            if cmd.get("retrain", False):
                retrain_static_model()
            return {"ok": True, "label": label}

        if kind == "rename_gesture":
            label = rename_gesture(cmd.get("gesture"), cmd.get("new_name"))
            return {"ok": True, "label": label}

        if kind == "delete_gesture":
            label = delete_gesture(cmd.get("gesture"))
            if cmd.get("retrain", True):
                retrain_static_model()
            return {"ok": True, "label": label}

        if kind == "collect_samples":
            label = int(cmd.get("label"))
            samples = collect_samples_for_label(
                label,
                target_samples=cmd.get("target_samples"),
                capture_interval=cmd.get("capture_interval_sec")
            )
            return {"ok": True, "samples": samples}

        if kind == "retrain":
            out = retrain_static_model()
            return {"ok": True, "result": out}

        if kind == "set_static_action":
            set_static_action(cmd.get("gesture"), cmd.get("action"))
            return {"ok": True}

        if kind == "delete_static_action":
            delete_static_action(cmd.get("gesture"))
            return {"ok": True}

        if kind == "set_voice_action":
            set_voice_action(cmd.get("phrase"), cmd.get("action"))
            return {"ok": True}

        if kind == "delete_voice_action":
            delete_voice_action(cmd.get("phrase"))
            return {"ok": True}

        return {"ok": False, "error": "unknown_command"}

    def poll_once(self):
        commands = self._read_commands()
        if not commands:
            return
        for cmd in commands:
            started = time.time()
            try:
                result = self._handle(cmd)
                append_engine_event("command_result", {
                    "cmd": cmd,
                    "result": result,
                    "latency_ms": int((time.time() - started) * 1000)
                })
            except Exception as e:
                append_engine_event("command_error", {
                    "cmd": cmd,
                    "error": str(e)
                })

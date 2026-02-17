from ml_engine.gesture_manager import (
    list_gestures,
    add_gesture,
    rename_gesture,
    delete_gesture,
    collect_samples_for_label,
    retrain_static_model,
    normalize_labels,
    set_static_action,
    delete_static_action,
    set_voice_action,
    delete_voice_action
)


def show():
    rows = list_gestures()
    if not rows:
        print("No gestures")
        return
    print("\nCurrent Gestures")
    for label, name in rows:
        print(f"{label}: {name}")


def cmd_add():
    name = input("New gesture name: ").strip()
    if not name:
        return
    label = add_gesture(name)
    print("Label:", label)
    rec = input("Collect samples now? (y/n): ").strip().lower() == "y"
    if rec:
        collect_samples_for_label(label)
        if input("Retrain now? (y/n): ").strip().lower() == "y":
            retrain_static_model()


def cmd_edit():
    key = input("Gesture label or name to edit: ").strip()
    if not key:
        return
    new_name = input("New name: ").strip()
    if not new_name:
        return
    label = rename_gesture(key, new_name)
    print("Updated label:", label)
    rec = input("Recollect samples for this gesture? (y/n): ").strip().lower() == "y"
    if rec:
        collect_samples_for_label(label)
        if input("Retrain now? (y/n): ").strip().lower() == "y":
            retrain_static_model()


def cmd_delete():
    key = input("Gesture label or name to delete: ").strip()
    if not key:
        return
    delete_gesture(key)
    normalize_labels()
    print("Deleted")
    if input("Retrain now? (y/n): ").strip().lower() == "y":
        retrain_static_model()


def cmd_recollect():
    key = input("Gesture label to recollect: ").strip()
    if not key.isdigit():
        return
    collect_samples_for_label(int(key))
    if input("Retrain now? (y/n): ").strip().lower() == "y":
        retrain_static_model()


def cmd_retrain():
    out = retrain_static_model()
    print("Model:", out["model_path"])
    print("Classes:", out["num_classes"])
    print("Rows:", out["rows"])


def cmd_set_static_action():
    key = input("Gesture label or name: ").strip()
    if not key:
        return
    mode = input("Action type (launch_app/hotkey/key/command/url/open_path/builtin): ").strip().lower()
    if mode == "builtin":
        name = input("Builtin (PlayPause/MuteToggle/AltRight/Click/ModeSwitch/OpenVSCode): ").strip()
        set_static_action(key, name)
    elif mode == "launch_app":
        target = input("App target (e.g. ms word): ").strip()
        set_static_action(key, {"type": "launch_app", "target": target})
    elif mode == "hotkey":
        raw = input("Keys comma-separated (e.g. ctrl,shift,n): ").strip()
        keys = [x.strip() for x in raw.split(",") if x.strip()]
        set_static_action(key, {"type": "hotkey", "keys": keys})
    elif mode == "key":
        k = input("Key: ").strip()
        set_static_action(key, {"type": "key", "key": k})
    elif mode == "command":
        c = input("Shell command: ").strip()
        set_static_action(key, {"type": "command", "command": c})
    elif mode == "url":
        u = input("URL: ").strip()
        set_static_action(key, {"type": "url", "url": u})
    elif mode == "open_path":
        p = input("Path: ").strip()
        set_static_action(key, {"type": "open_path", "path": p})
    print("Static action updated")


def cmd_delete_static_action():
    key = input("Gesture label or name: ").strip()
    if not key:
        return
    delete_static_action(key)
    print("Static action removed")


def cmd_set_voice_action():
    phrase = input("Voice phrase: ").strip().lower()
    if not phrase:
        return
    mode = input("Action type (launch_app/hotkey/key/command/url/open_path/builtin): ").strip().lower()
    if mode == "builtin":
        name = input("Builtin (PlayPause/MuteToggle/AltRight/Click/ModeSwitch/OpenVSCode): ").strip()
        set_voice_action(phrase, name)
    elif mode == "launch_app":
        target = input("App target (e.g. ms word): ").strip()
        set_voice_action(phrase, {"type": "launch_app", "target": target})
    elif mode == "hotkey":
        raw = input("Keys comma-separated: ").strip()
        keys = [x.strip() for x in raw.split(",") if x.strip()]
        set_voice_action(phrase, {"type": "hotkey", "keys": keys})
    elif mode == "key":
        k = input("Key: ").strip()
        set_voice_action(phrase, {"type": "key", "key": k})
    elif mode == "command":
        c = input("Shell command: ").strip()
        set_voice_action(phrase, {"type": "command", "command": c})
    elif mode == "url":
        u = input("URL: ").strip()
        set_voice_action(phrase, {"type": "url", "url": u})
    elif mode == "open_path":
        p = input("Path: ").strip()
        set_voice_action(phrase, {"type": "open_path", "path": p})
    print("Voice action updated")


def cmd_delete_voice_action():
    phrase = input("Voice phrase: ").strip().lower()
    if not phrase:
        return
    delete_voice_action(phrase)
    print("Voice action removed")


def main():
    while True:
        print("\n1. List")
        print("2. Add")
        print("3. Edit")
        print("4. Delete")
        print("5. Recollect")
        print("6. Retrain")
        print("7. Set Static Action")
        print("8. Delete Static Action")
        print("9. Set Voice Action")
        print("10. Delete Voice Action")
        print("11. Exit")
        ch = input("Select: ").strip()

        if ch == "1":
            show()
        elif ch == "2":
            cmd_add()
        elif ch == "3":
            cmd_edit()
        elif ch == "4":
            cmd_delete()
        elif ch == "5":
            cmd_recollect()
        elif ch == "6":
            cmd_retrain()
        elif ch == "7":
            cmd_set_static_action()
        elif ch == "8":
            cmd_delete_static_action()
        elif ch == "9":
            cmd_set_voice_action()
        elif ch == "10":
            cmd_delete_voice_action()
        elif ch == "11":
            break


if __name__ == "__main__":
    main()

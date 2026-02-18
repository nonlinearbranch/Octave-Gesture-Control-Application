from ml_engine.gesture_manager import add_gesture, collect_samples_for_label, retrain_static_model


def main():
    gesture_name = input("Enter gesture name: ").strip()
    if not gesture_name:
        print("Invalid gesture name")
        return

    label = add_gesture(gesture_name)
    print("Gesture assigned label:", label)
    print("Starting in 3 seconds...")

    import time
    time.sleep(3)

    samples = collect_samples_for_label(label)
    print("Saved", samples, "samples for", gesture_name)
    if input("Retrain model now? (y/n): ").strip().lower() == "y":
        out = retrain_static_model()
        print("Model:", out["model_path"])
        print("Classes:", out["num_classes"])
        print("Rows:", out["rows"])


if __name__ == "__main__":
    main()

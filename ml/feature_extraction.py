import numpy as np


def diagnose_environment() -> dict:
    """Validate all required ML dependencies and their versions."""
    import importlib

    deps = ["numpy", "cv2", "mediapipe", "torch", "vosk", "sounddevice", "pandas"]
    report = {}
    print("--- SPIDER Environment Diagnostics ---")
    for dep in deps:
        try:
            mod = importlib.import_module(dep)
            version = getattr(mod, "__version__", getattr(mod, "VERSION", "unknown"))
            report[dep] = {"status": "ok", "version": version}
            print(f"[OK] {dep.ljust(15)} : {version}")
        except Exception as exc:
            report[dep] = {"status": "error", "error": str(exc)}
            print(f"[FAIL] {dep.ljust(13)} : {exc}")

    print("--------------------------------------")
    return report


def extract_features(hand_landmarks):
    """
    Extract a 126-dimensional feature vector from one or two hand landmarks.

    Accepts these input formats:
      (a) MediaPipe hand_landmarks object with a .landmark attribute.
      (b) Sequence of one or two MediaPipe hand landmark objects.
      (c) List of 21 [x, y, z] triples for a single hand.
      (d) numpy array with shape (21, 3), (63,), or (n_hands, 21, 3).

    Normalization:
      1. Translation-invariant: all coords are relative to wrist (landmark 0).
      2. Scale-invariant: divide by wrist-to-middle-MCP distance (landmark 9).

    Returns a numpy array of shape (126,), dtype float32.
    """
    hands = _collect_hands(hand_landmarks)
    features_list: list[np.ndarray] = []
    for hand in hands[:2]:
        features_list.append(_extract_single_hand_features(hand))

    while len(features_list) < 2:
        features_list.append(np.zeros((63,), dtype=np.float32))

    result = np.concatenate(features_list, axis=0)
    if result.shape != (126,):
        raise ValueError(
            f"Feature extraction produced shape {result.shape}, expected (126,)."
        )
    return result


def _collect_hands(hand_landmarks):
    """Return a list of one or two single-hand landmark objects."""
    if _is_multi_hand_collection(hand_landmarks):
        collected = list(hand_landmarks)
        if len(collected) == 0:
            raise ValueError("No hand landmarks provided.")
        return collected[:2]
    return [hand_landmarks]


def _is_multi_hand_collection(candidate):
    if isinstance(candidate, np.ndarray):
        return candidate.ndim == 3 and candidate.shape[1:] == (21, 3)

    if isinstance(candidate, (list, tuple)) and len(candidate) in (1, 2):
        first = candidate[0]
        if first is None:
            return False
        return _looks_like_single_hand(first)

    return False


def _looks_like_single_hand(candidate):
    if hasattr(candidate, "landmark"):
        return True

    if isinstance(candidate, np.ndarray):
        return candidate.shape in ((21, 3), (63,))

    if isinstance(candidate, (list, tuple)):
        if len(candidate) == 21 and all(
            isinstance(point, (list, tuple, np.ndarray)) and len(point) == 3
            for point in candidate
        ):
            return True
        if len(candidate) == 63 and all(
            isinstance(value, (int, float, np.integer, np.floating)) for value in candidate
        ):
            return True
    return False


def _extract_single_hand_features(hand_landmarks):
    coords = _parse_landmarks(hand_landmarks)
    wrist = coords[0].copy()
    coords = coords - wrist

    hand_scale = np.linalg.norm(coords[9])
    if hand_scale > 1e-8:
        coords = coords / hand_scale

    features = coords.flatten().astype(np.float32)
    if features.shape != (63,):
        raise ValueError(
            f"Feature extraction produced shape {features.shape}, expected (63,)."
        )
    return features


def _parse_landmarks(hand_landmarks):
    """Convert supported landmark input into a (21, 3) float64 numpy array."""
    if hasattr(hand_landmarks, "landmark"):
        landmarks = hand_landmarks.landmark
        if len(landmarks) != 21:
            raise ValueError(
                f"MediaPipe hand_landmarks has {len(landmarks)} landmarks, expected 21."
            )
        return np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float64)

    if isinstance(hand_landmarks, np.ndarray):
        if hand_landmarks.shape == (21, 3):
            return hand_landmarks.astype(np.float64)
        if hand_landmarks.shape == (63,):
            return hand_landmarks.reshape(21, 3).astype(np.float64)
        raise ValueError(
            f"numpy array has shape {hand_landmarks.shape}, expected (21, 3) or (63,)."
        )

    if isinstance(hand_landmarks, (list, tuple)):
        if len(hand_landmarks) == 0:
            raise ValueError("Empty landmark list.")

        first = hand_landmarks[0]
        if isinstance(first, (list, tuple, np.ndarray)):
            if len(hand_landmarks) != 21:
                raise ValueError(
                    f"Landmark list has {len(hand_landmarks)} entries, expected 21."
                )
            coords = np.array(hand_landmarks, dtype=np.float64)
            if coords.shape != (21, 3):
                raise ValueError(
                    f"Landmark array has shape {coords.shape}, expected (21, 3)."
                )
            return coords

        if isinstance(first, (int, float, np.floating, np.integer)):
            if len(hand_landmarks) == 63:
                return np.array(hand_landmarks, dtype=np.float64).reshape(21, 3)
            raise ValueError(
                f"Flat landmark list has {len(hand_landmarks)} values, expected 63."
            )

        raise ValueError(
            f"Landmark list entries have unsupported type: {type(first).__name__}."
        )

    raise ValueError(
        f"Unrecognized landmark format: {type(hand_landmarks).__name__}. "
        "Expected MediaPipe hand_landmarks, list of [x,y,z], or numpy array."
    )


def _self_test():
    """Verify extract_features works with every supported input format."""
    passed = 0
    failed = 0

    def _check(name, fn):
        nonlocal passed, failed
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {name}: {exc}")
            failed += 1

    def t_list_input():
        data = [[i * 0.01, i * 0.02, i * 0.001] for i in range(21)]
        result = extract_features(data)
        assert result.shape == (126,), f"shape {result.shape}"
        assert result.dtype == np.float32, f"dtype {result.dtype}"
        assert np.allclose(result[63:], 0.0), "second hand should be zero padded"

    _check("list [[x,y,z], ...] input", t_list_input)

    def t_np_21x3():
        result = extract_features(np.random.rand(21, 3))
        assert result.shape == (126,) and result.dtype == np.float32
        assert np.allclose(result[63:], 0.0), "second hand should be zero padded"

    _check("numpy (21,3) input", t_np_21x3)

    def t_np_flat():
        result = extract_features(np.random.rand(63))
        assert result.shape == (126,) and result.dtype == np.float32
        assert np.allclose(result[63:], 0.0), "second hand should be zero padded"

    _check("numpy (63,) input", t_np_flat)

    def t_mediapipe_mock():
        class Landmark:
            def __init__(self, x, y, z):
                self.x = x
                self.y = y
                self.z = z

        class Hand:
            def __init__(self):
                self.landmark = [
                    Landmark(i * 0.01, i * 0.02, i * 0.001) for i in range(21)
                ]

        result = extract_features(Hand())
        assert result.shape == (126,) and result.dtype == np.float32
        assert np.allclose(result[63:], 0.0), "second hand should be zero padded"

    _check("MediaPipe mock object input", t_mediapipe_mock)

    def t_two_hands():
        class Landmark:
            def __init__(self, x, y, z):
                self.x = x
                self.y = y
                self.z = z

        class Hand:
            def __init__(self, offset):
                self.landmark = [
                    Landmark(offset + i * 0.01, i * 0.02, i * 0.001) for i in range(21)
                ]

        result = extract_features([Hand(0.0), Hand(1.0)])
        assert result.shape == (126,) and result.dtype == np.float32
        assert not np.allclose(result[:63], result[63:]), "two hands should produce distinct halves"

    _check("MediaPipe two-hand input", t_two_hands)

    def t_consistency():
        raw = [[i * 0.01, i * 0.02, i * 0.001] for i in range(21)]
        result_list = extract_features(raw)
        result_np2d = extract_features(np.array(raw))
        result_flat = extract_features(np.array(raw).flatten())
        assert np.allclose(result_list, result_np2d), "list vs numpy (21,3) mismatch"
        assert np.allclose(result_list, result_flat), "list vs numpy (63,) mismatch"

    _check("cross-format consistency", t_consistency)

    def t_validation():
        cases = [
            ([], "empty list"),
            ([[1, 2, 3]], "only 1 landmark"),
            (np.zeros((10, 3)), "wrong numpy shape"),
            ("not_landmarks", "string input"),
        ]
        for bad_input, desc in cases:
            try:
                extract_features(bad_input)
                raise AssertionError(f"Should have raised ValueError for: {desc}")
            except ValueError:
                pass

    _check("ValueError for invalid inputs", t_validation)

    def t_normalization():
        raw = [[i * 0.05, i * 0.03, i * 0.01] for i in range(21)]
        result = extract_features(raw)
        assert np.allclose(result[0:3], 0.0), f"wrist not zeroed: {result[0:3]}"
        mcp9 = result[27:30]
        mcp9_norm = np.linalg.norm(mcp9)
        assert abs(mcp9_norm - 1.0) < 1e-5, (
            f"MCP9 norm={mcp9_norm}, expected 1.0"
        )

    _check("normalization correctness", t_normalization)

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import sys

    print("Feature Extraction Self-Test")
    print("=" * 40)
    ok = _self_test()
    sys.exit(0 if ok else 1)


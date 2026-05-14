from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Callable

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from ml.runtime.static_inference_runner import StaticGestureModel


ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DATA_DIR = ROOT_DIR / "data" / "static"
MODEL_DIR = ROOT_DIR / "models" / "static"
CONFIG_DIR = ROOT_DIR / "config"
DEFAULT_MAPPING_PATH = CONFIG_DIR / "default_mapping.json"
FEATURE_SIZE = 126
MIN_SAMPLES = 10


def resolve_model_path(target: str) -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR / f"{target}_model.pth"


def _load_aggregated_csv(
    csv_path: Path,
    *,
    enforce_min_samples: bool = True,
) -> tuple[torch.Tensor, torch.Tensor]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Static training CSV not found: {csv_path}")

    features: list[list[float]] = []
    labels: list[int] = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row_number, row in enumerate(reader, start=1):
            if not row:
                continue
            if len(row) != FEATURE_SIZE + 1:
                raise ValueError(
                    f"Invalid row {row_number} in {csv_path}: expected "
                    f"{FEATURE_SIZE + 1} values including label, got {len(row)}"
                )
            try:
                values = [float(value) for value in row[:FEATURE_SIZE]]
                label = int(float(row[-1]))
            except ValueError as exc:
                raise ValueError(f"Invalid numeric value in {csv_path} row {row_number}") from exc
            features.append(values)
            labels.append(label)

    if enforce_min_samples and len(features) < MIN_SAMPLES:
        raise ValueError(
            f"Need at least {MIN_SAMPLES} static samples, got {len(features)}."
        )

    return torch.tensor(features, dtype=torch.float32), torch.tensor(labels, dtype=torch.long)


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _static_mapping() -> dict[int, str]:
    mapping = _load_json_file(DEFAULT_MAPPING_PATH).get("static", {})
    if not isinstance(mapping, dict):
        return {}
    return {
        int(key): str(value.get("name", "")).strip()
        for key, value in mapping.items()
        if isinstance(value, dict) and "name" in value
    }


def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in str(value) if ch.isalnum())


def _load_folder_dataset_for_labels(
    data_dir: Path,
    label_mapping: dict[int, str],
) -> tuple[torch.Tensor, torch.Tensor, list[str]]:
    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(f"Static data folder not found: {data_dir}")

    file_paths = sorted([path for path in data_dir.glob("*.csv") if path.is_file()])
    if not file_paths:
        raise FileNotFoundError(f"No static CSV files found in {data_dir}")

    normalized_labels = {
        _normalize_name(label_name): label_id
        for label_id, label_name in label_mapping.items()
    }

    features: list[list[float]] = []
    labels: list[int] = []
    seen_label_ids: set[int] = set()

    for path in file_paths:
        normalized_stem = _normalize_name(path.stem)
        if normalized_stem not in normalized_labels:
            raise ValueError(f"No static mapping entry found for dataset file: {path.name}")
        label_index = normalized_labels[normalized_stem]
        seen_label_ids.add(label_index)
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row_number, row in enumerate(reader, start=1):
                if not row:
                    continue
                if len(row) != FEATURE_SIZE:
                    raise ValueError(
                        f"Invalid row {row_number} in {path}: expected "
                        f"{FEATURE_SIZE} values, got {len(row)}"
                    )
                try:
                    values = [float(value) for value in row]
                except ValueError as exc:
                    raise ValueError(f"Invalid numeric value in {path} row {row_number}") from exc
                features.append(values)
                labels.append(label_index)

    if len(features) < MIN_SAMPLES:
        raise ValueError(
            f"Need at least {MIN_SAMPLES} static samples, got {len(features)}."
        )

    label_names = [label_mapping[label_id] for label_id in sorted(seen_label_ids)]
    return (
        torch.tensor(features, dtype=torch.float32),
        torch.tensor(labels, dtype=torch.long),
        label_names,
    )


def _load_folder_dataset(target: str) -> tuple[torch.Tensor, torch.Tensor, list[str]]:
    if target != "default":
        raise ValueError(f"Folder dataset loading requires explicit label mapping, got target={target}")
    return _load_folder_dataset_for_labels(STATIC_DATA_DIR / target, _static_mapping())


def _load_custom_dataset(csv_path: Path) -> tuple[torch.Tensor, torch.Tensor]:
    features, labels = _load_aggregated_csv(csv_path, enforce_min_samples=False)
    return features, labels


def _merge_datasets(
    datasets: list[tuple[torch.Tensor, torch.Tensor]],
) -> tuple[torch.Tensor, torch.Tensor]:
    present = [(features, labels) for features, labels in datasets if int(features.shape[0]) > 0]
    if not present:
        raise ValueError("No static training samples were loaded.")
    merged_features = torch.cat([features for features, _ in present], dim=0)
    merged_labels = torch.cat([labels for _, labels in present], dim=0)
    return merged_features, merged_labels


def _load_transfer_weights(
    model: StaticGestureModel,
    checkpoint_path: Path,
    *,
    skip_keys: set[str] | None = None,
) -> list[str]:
    if not checkpoint_path.exists():
        return [f"transfer_checkpoint_missing:{checkpoint_path.name}"]

    state = torch.load(checkpoint_path, map_location="cpu")
    if isinstance(state, dict) and "net.6.weight" not in state and "model.6.weight" in state:
        state = {
            (key.replace("model.", "net.", 1) if key.startswith("model.") else key): value
            for key, value in state.items()
        }

    model_state = model.state_dict()
    applied = 0
    skipped: list[str] = []
    for key, value in state.items():
        if skip_keys and key in skip_keys:
            skipped.append(key)
            continue
        if key in model_state and tuple(model_state[key].shape) == tuple(value.shape):
            model_state[key] = value
            applied += 1
        else:
            skipped.append(key)
    model.load_state_dict(model_state)

    warnings: list[str] = []
    if applied > 0:
        warnings.append(f"transfer_learning_loaded:{checkpoint_path.name}")
    if skipped:
        warnings.append("transfer_learning_skipped_mismatched_output_layer")
    return warnings


def _inject_noise_class_if_needed(
    features: torch.Tensor,
    labels: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, list[str]]:
    unique_labels = sorted(int(value) for value in labels.unique().tolist())
    if len(unique_labels) > 1:
        return features, labels, []

    noise_label = max(unique_labels, default=-1) + 1
    noise_count = max(MIN_SAMPLES, min(64, int(features.shape[0])))
    std = torch.std(features, dim=0, keepdim=True)
    std = torch.where(std < 1e-4, torch.full_like(std, 0.03), std)
    center = torch.mean(features, dim=0, keepdim=True)
    noise = center + torch.randn((noise_count, features.shape[1])) * std * 2.5
    noise_labels = torch.full((noise_count,), noise_label, dtype=torch.long)
    return torch.cat([features, noise], dim=0), torch.cat([labels, noise_labels], dim=0), [
        "single_class_noise_injected"
    ]


def _split_dataset(dataset: TensorDataset) -> tuple[Any, Any]:
    if len(dataset) < 2:
        raise ValueError("Need at least two samples after preprocessing.")
    val_count = max(1, int(0.2 * len(dataset)))
    train_count = len(dataset) - val_count
    if train_count <= 0:
        train_count = len(dataset) - 1
        val_count = 1
    return torch.utils.data.random_split(
        dataset,
        [train_count, val_count],
        generator=torch.Generator().manual_seed(42),
    )


def train_static_model(
    *,
    target: str = "custom",
    csv_path: str | None = None,
    model_path: str | None = None,
    epochs: int = 60,
    lr: float = 0.001,
    batch_size: int = 32,
    progress_cb: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    if target == "custom":
        if not csv_path:
            raise ValueError("Custom static training requires csv_path.")
        default_features, default_labels, default_label_names = _load_folder_dataset("default")
        custom_features, custom_labels = _load_custom_dataset(Path(csv_path))
        features, labels = _merge_datasets(
            [(default_features, default_labels), (custom_features, custom_labels)]
        )
        label_names = default_label_names
    else:
        features, labels, label_names = _load_folder_dataset(target)

    features, labels, noise_warnings = _inject_noise_class_if_needed(features, labels)
    warnings.extend(noise_warnings)
    num_classes = max(int(value) for value in labels.tolist()) + 1

    dataset = TensorDataset(features, labels)
    train_dataset, val_dataset = _split_dataset(dataset)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)

    model = StaticGestureModel(input_size=FEATURE_SIZE, num_classes=num_classes)
    if target == "custom":
        warnings.extend(
            _load_transfer_weights(
                model,
                MODEL_DIR / "default_model.pth",
                skip_keys={"net.6.weight", "net.6.bias", "model.6.weight", "model.6.bias"},
            )
        )
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    val_accuracy = 0.0
    for epoch in range(1, epochs + 1):
        model.train()
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()

        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for val_x, val_y in val_loader:
                logits = model(val_x)
                predictions = torch.argmax(logits, dim=1)
                correct += int((predictions == val_y).sum().item())
                total += int(val_y.size(0))
        val_accuracy = correct / max(1, total)

        if progress_cb is not None:
            progress_cb(epoch / float(max(1, epochs)))

    output_path = Path(model_path) if model_path else resolve_model_path(target)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_path)

    return {
        "model_path": str(output_path),
        "target": target,
        "num_classes": num_classes,
        "labels": label_names,
        "samples": int(features.shape[0]),
        "train_samples": len(train_dataset),
        "validation_samples": len(val_dataset),
        "accuracy": val_accuracy,
        "val_accuracy": val_accuracy,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the static gesture model.")
    parser.add_argument("--target", choices=["default", "custom"], required=True)
    parser.add_argument("--csv-path", default=None)
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--lr", type=float, default=0.0007)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    print(
        train_static_model(
            target=args.target,
            csv_path=args.csv_path,
            model_path=args.model_path,
            epochs=args.epochs,
            lr=args.lr,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    main()

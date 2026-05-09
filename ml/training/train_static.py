from __future__ import annotations

import argparse
import csv
import random
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
FEATURE_SIZE = 126
MIN_SAMPLES = 10


def resolve_model_path(target: str) -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR / f"{target}_model.pth"


def _load_aggregated_csv(csv_path: Path) -> tuple[torch.Tensor, torch.Tensor]:
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

    if len(features) < MIN_SAMPLES:
        raise ValueError(
            f"Need at least {MIN_SAMPLES} static samples, got {len(features)}."
        )

    return torch.tensor(features, dtype=torch.float32), torch.tensor(labels, dtype=torch.long)


def _load_folder_dataset(target: str) -> tuple[torch.Tensor, torch.Tensor, list[str]]:
    data_dir = STATIC_DATA_DIR / target
    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(f"Static data folder not found: {data_dir}")

    file_paths = sorted([path for path in data_dir.glob("*.csv") if path.is_file()])
    if not file_paths:
        raise FileNotFoundError(f"No static CSV files found in {data_dir}")

    features: list[list[float]] = []
    labels: list[int] = []
    label_names: list[str] = []

    for label_index, path in enumerate(file_paths):
        label_names.append(path.stem.replace("-", "_"))
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

    return (
        torch.tensor(features, dtype=torch.float32),
        torch.tensor(labels, dtype=torch.long),
        label_names,
    )


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
    if csv_path:
        features, labels = _load_aggregated_csv(Path(csv_path))
        label_names: list[str] = []
    else:
        features, labels, label_names = _load_folder_dataset(target)

    features, labels, warnings = _inject_noise_class_if_needed(features, labels)
    num_classes = max(int(value) for value in labels.tolist()) + 1

    dataset = TensorDataset(features, labels)
    train_dataset, val_dataset = _split_dataset(dataset)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)

    model = StaticGestureModel(input_size=FEATURE_SIZE, num_classes=num_classes)
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

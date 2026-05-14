from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset


TargetName = str
ROOT_DIR = Path(__file__).resolve().parent.parent
DYNAMIC_DATA_DIR = ROOT_DIR / "data" / "dynamic"
MODEL_DIR = ROOT_DIR / "models" / "dynamic"
CONFIG_DIR = ROOT_DIR / "config"
DEFAULT_MAPPING_PATH = CONFIG_DIR / "default_mapping.json"
USER_MAPPING_PATH = CONFIG_DIR / "user_mapping.json"
SEQUENCE_LENGTH = 30


class DynamicGestureModel(nn.Module):
    def __init__(
        self,
        input_size: int = 126,
        hidden_size: int = 64,
        num_layers: int = 2,
        num_classes: int = 2,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2,
        )
        self.fc1 = nn.Linear(hidden_size, 32)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(32, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        outputs, (hidden, _) = self.lstm(x)
        final_hidden = hidden[-1]
        return self.fc2(self.relu(self.fc1(final_hidden)))


def resolve_model_path(target: str) -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR / f"{target}_model.pth"


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in str(value) if ch.isalnum())


def _label_mapping(section_name: str, path: Path) -> dict[int, str]:
    mapping = _load_json_file(path).get(section_name, {})
    if not isinstance(mapping, dict):
        return {}
    return {
        int(key): str(value.get("name", "")).strip()
        for key, value in mapping.items()
        if isinstance(value, dict) and "name" in value
    }


def _load_dynamic_folder_dataset(
    data_dir: Path,
    label_mapping: dict[int, str],
) -> tuple[list[list[list[float]]], list[int], set[int]]:
    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(f"Dynamic data folder not found: {data_dir}")

    file_paths = sorted([p for p in data_dir.glob("*.csv") if p.is_file()])
    if not file_paths:
        raise FileNotFoundError(f"No dynamic CSV files found in {data_dir}")

    normalized_labels = {
        _normalize_name(label_name): label_id
        for label_id, label_name in label_mapping.items()
    }

    sequences: list[list[list[float]]] = []
    labels: list[int] = []
    seen_label_ids: set[int] = set()

    for csv_path in file_paths:
        normalized_stem = _normalize_name(csv_path.stem)
        if normalized_stem not in normalized_labels:
            raise ValueError(f"No dynamic mapping entry found for dataset file: {csv_path.name}")
        label_index = normalized_labels[normalized_stem]
        seen_label_ids.add(label_index)
        rows: list[list[float]] = []
        with csv_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row_number, row in enumerate(reader, start=1):
                if not row:
                    continue
                if len(row) != 126:
                    raise ValueError(
                        f"Invalid row {row_number} in {csv_path}: expected 126 values, got {len(row)}"
                    )
                try:
                    values = [float(value) for value in row]
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid numeric value in {csv_path} row {row_number}"
                    ) from exc
                rows.append(values)

        if len(rows) % SEQUENCE_LENGTH != 0:
            raise ValueError(
                f"Dynamic CSV {csv_path} must contain a multiple of {SEQUENCE_LENGTH} rows, got {len(rows)}"
            )

        for seq_index in range(len(rows) // SEQUENCE_LENGTH):
            sequence = rows[seq_index * SEQUENCE_LENGTH : (seq_index + 1) * SEQUENCE_LENGTH]
            sequences.append(sequence)
            labels.append(label_index)

    return sequences, labels, seen_label_ids


def load_dynamic_dataset(target: str) -> tuple[torch.Tensor, torch.Tensor, list[str], list[str]]:
    warnings: list[str] = []
    default_mapping = _label_mapping("dynamic", DEFAULT_MAPPING_PATH)
    sequences: list[list[list[float]]] = []
    labels: list[int] = []
    seen_label_ids: set[int] = set()

    default_sequences, default_labels, default_seen = _load_dynamic_folder_dataset(
        DYNAMIC_DATA_DIR / "default",
        default_mapping,
    )
    sequences.extend(default_sequences)
    labels.extend(default_labels)
    seen_label_ids.update(default_seen)

    if target == "custom":
        user_mapping = _label_mapping("dynamic", USER_MAPPING_PATH)
        custom_dir = DYNAMIC_DATA_DIR / "custom"
        custom_files = sorted([p for p in custom_dir.glob("*.csv") if p.is_file()]) if custom_dir.exists() else []
        if custom_files:
            custom_sequences, custom_labels, custom_seen = _load_dynamic_folder_dataset(
                custom_dir,
                user_mapping,
            )
            sequences.extend(custom_sequences)
            labels.extend(custom_labels)
            seen_label_ids.update(custom_seen)
        else:
            warnings.append("custom_dynamic_dataset_empty_using_defaults_only")
    elif target != "default":
        raise ValueError(f"Unsupported dynamic training target: {target}")

    if not sequences:
        raise ValueError("No dynamic sequences were loaded.")

    merged_mapping = dict(default_mapping)
    if target == "custom":
        merged_mapping.update(_label_mapping("dynamic", USER_MAPPING_PATH))

    label_names = [merged_mapping[label_id] for label_id in sorted(seen_label_ids)]
    return (
        torch.tensor(sequences, dtype=torch.float32),
        torch.tensor(labels, dtype=torch.long),
        label_names,
        warnings,
    )


def _load_transfer_weights(
    model: DynamicGestureModel,
    checkpoint_path: Path,
    *,
    skip_keys: set[str] | None = None,
) -> list[str]:
    if not checkpoint_path.exists():
        return [f"transfer_checkpoint_missing:{checkpoint_path.name}"]

    state = torch.load(checkpoint_path, map_location="cpu")
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


def train_dynamic_model(
    *,
    target: str,
    epochs: int = 40,
    lr: float = 0.001,
    batch_size: int = 16,
) -> dict[str, Any]:
    X, y, label_names, warnings = load_dynamic_dataset(target)
    num_classes = max(int(value) for value in y.tolist()) + 1

    print(
        f"Training dynamic model for target={target} classes={label_names} sequences={len(y)}",
        flush=True,
    )

    dataset = TensorDataset(X, y)
    val_count = max(1, int(0.2 * len(dataset)))
    train_count = len(dataset) - val_count
    train_dataset, val_dataset = torch.utils.data.random_split(
        dataset,
        [train_count, val_count],
        generator=torch.Generator().manual_seed(42),
    )

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)

    model = DynamicGestureModel(input_size=126, hidden_size=64, num_layers=2, num_classes=num_classes)
    if target == "custom":
        warnings.extend(
            _load_transfer_weights(
                model,
                MODEL_DIR / "default_model.pth",
                skip_keys={"fc2.weight", "fc2.bias"},
            )
        )
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * batch_x.size(0)

        epoch_loss /= max(1, len(train_dataset))

        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for val_x, val_y in val_loader:
                logits = model(val_x)
                _, predictions = torch.max(logits, 1)
                correct += (predictions == val_y).sum().item()
                total += val_y.size(0)

        val_accuracy = correct / max(1, total)
        print(
            f"Epoch {epoch}/{epochs} loss={epoch_loss:.4f} val_accuracy={val_accuracy:.4f}",
            flush=True,
        )

    model_path = resolve_model_path(target)
    torch.save(model.state_dict(), model_path)
    print(f"Saved dynamic model to {model_path}", flush=True)

    return {
        "model_path": str(model_path),
        "target": target,
        "num_classes": num_classes,
        "labels": label_names,
        "train_sequences": train_count,
        "validation_sequences": val_count,
        "val_accuracy": val_accuracy,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the dynamic gesture model.")
    parser.add_argument("--target", choices=["default", "custom"], required=True)
    parser.add_argument("--epochs", type=int, default=75)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    result = train_dynamic_model(
        target=args.target,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
    )
    print(result)


if __name__ == "__main__":
    main()

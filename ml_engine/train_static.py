import os
import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd

from utils.helpers import get_setting

try:
    from ml_engine.static_model import StaticGestureModel
except Exception:
    from static_model import StaticGestureModel


def _default_paths():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "ml_engine", "data", "static_gestures.csv")
    model_path = os.path.join(base_dir, "ml_engine", "data", "models", "static_model.pth")
    return csv_path, model_path


def train_static_model(csv_path=None, model_path=None, epochs=None, lr=0.001):
    default_csv, default_model = _default_paths()
    csv_path = csv_path or default_csv
    model_path = model_path or default_model
    if epochs is None:
        epochs = int(get_setting("static_train_epochs", 125))

    if not os.path.exists(csv_path):
        raise FileNotFoundError(csv_path)

    data = pd.read_csv(csv_path, header=None)
    if data.empty:
        raise ValueError("Dataset is empty")

    X = data.iloc[:, :-1].values
    y = data.iloc[:, -1].values.astype(int)

    uniq = sorted(set(y.tolist()))
    remap = {old: idx for idx, old in enumerate(uniq)}
    y = [remap[v] for v in y]

    X = torch.tensor(X, dtype=torch.float32)
    y = torch.tensor(y, dtype=torch.long)

    num_classes = len(set(y.tolist()))
    model = StaticGestureModel(input_size=X.shape[1], num_classes=num_classes)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    for epoch in range(epochs):
        outputs = model(X)
        loss = criterion(outputs, y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if epoch % 5 == 0:
            print("Epoch", epoch, "Loss:", loss.item())

    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    torch.save(model.state_dict(), model_path)
    print("Training finished")
    return {
        "model_path": model_path,
        "num_classes": num_classes,
        "rows": len(data)
    }


if __name__ == "__main__":
    train_static_model()

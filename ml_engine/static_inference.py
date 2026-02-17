import torch
from static_model import StaticGestureModel

model = None


def load_model(model_path, input_size, num_classes):
    global model
    model = StaticGestureModel(input_size, num_classes)
    model.load_state_dict(torch.load(model_path))
    model.eval()


def predict(features):
    with torch.no_grad():
        x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
        out = model(x)
        pred = torch.argmax(out, dim=1).item()
        return pred

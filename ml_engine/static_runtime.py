import torch
import torch.nn.functional as F
from ml_engine.static_model import StaticGestureModel

model = None
num_classes = None
confidence_threshold = 0.7


def init_static_model(model_path, input_size, classes):
    global model, num_classes
    num_classes = classes
    model = StaticGestureModel(input_size, classes)
    model.load_state_dict(torch.load(model_path))
    model.eval()


def run_static_inference(features):
    with torch.no_grad():
        x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
        out = model(x)

        probs = F.softmax(out, dim=1)
        conf, pred = torch.max(probs, dim=1)

        if conf.item() < confidence_threshold:
            return -1

        return pred.item()

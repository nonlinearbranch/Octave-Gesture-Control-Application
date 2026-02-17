import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
from static_model import StaticGestureModel

data = pd.read_csv("C:\\Users\\HP\\OneDrive\\RISHI GARG LAB\\GESTURE CONTROLLED SYSTEM(GF)\\ml_engine\\data\\static_gestures.csv")

X = data.iloc[:, :-1].values
y = data.iloc[:, -1].values

X = torch.tensor(X, dtype=torch.float32)
y = torch.tensor(y, dtype=torch.long)

num_classes = len(set(y.tolist()))

model = StaticGestureModel(input_size=X.shape[1], num_classes=num_classes)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

epochs = 125

for epoch in range(epochs):
    outputs = model(X)
    loss = criterion(outputs, y)

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    if epoch % 5 == 0:
        print("Epoch", epoch, "Loss:", loss.item())

torch.save(model.state_dict(), "C:\\Users\\HP\\OneDrive\\RISHI GARG LAB\\GESTURE CONTROLLED SYSTEM(GF)\\ml_engine\\data\\models\\static_model.pth")
    
print("Training finished")

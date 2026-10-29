from pathlib import Path

import torch
from ultralytics import YOLO

if __name__ == "__main__":
    data_yaml = Path(__file__).resolve().parent.parent / "datasets" / "chars" / "data.yaml"
    device = 0 if torch.cuda.is_available() else "cpu"

    model = YOLO("yolov8n.pt")
    model.train(
        data=str(data_yaml),
        imgsz=640,
        epochs=80,
        batch=8,
        device=device,
        workers=2,
        patience=20,
        verbose=True,
    )

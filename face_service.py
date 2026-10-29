"""Phát hiện và trích xuất đặc trưng khuôn mặt bằng FaceNet (tích hợp từ project PhuocNguyen)."""

from dataclasses import dataclass

import cv2
import numpy as np
import torch
from facenet_pytorch import InceptionResnetV1, MTCNN
from PIL import Image


@dataclass
class FaceData:
    box: tuple[int, int, int, int]
    confidence: float
    embedding: list[float] | None = None


class FaceService:
    def __init__(self) -> None:
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.detector = MTCNN(keep_all=True, device=self.device, min_face_size=40)
        self.encoder = (
            InceptionResnetV1(pretrained="vggface2").eval().to(self.device)
        )

    def detect_from_bgr(
        self, frame: np.ndarray, extract_embedding: bool = False
    ) -> list[FaceData]:
        """Phát hiện khuôn mặt trên khung hình BGR (tùy chọn trích xuất vector 512 chiều)."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        height, width = frame.shape[:2]

        boxes, probabilities = self.detector.detect(image)
        if boxes is None or probabilities is None:
            return []

        results: list[FaceData] = []
        sorted_indices = sorted(
            enumerate(probabilities),
            key=lambda item: float(item[1]) if item[1] is not None else -1.0,
            reverse=True,
        )
        for index, probability in sorted_indices:
            if probability is None or np.isnan(probability):
                continue
            raw_box = boxes[index]
            x1, y1, x2, y2 = [int(round(float(val))) for val in raw_box]
            x1, x2 = max(0, x1), min(width, x2)
            y1, y2 = max(0, y1), min(height, y2)
            if x1 >= x2 or y1 >= y2:
                continue

            embedding_list: list[float] | None = None
            if extract_embedding:
                face_tensor = self.detector.extract(
                    image, np.asarray([raw_box]), save_path=None
                )
                if face_tensor is not None:
                    with torch.inference_mode():
                        vector = self.encoder(face_tensor.to(self.device))[0]
                    vector = (
                        torch.nn.functional.normalize(vector, p=2, dim=0)
                        .cpu()
                        .numpy()
                    )
                    embedding_list = vector.astype(float).tolist()

            results.append(
                FaceData(
                    box=(x1, y1, x2, y2),
                    confidence=round(float(probability), 3),
                    embedding=embedding_list,
                )
            )
        return results

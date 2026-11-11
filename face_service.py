"""Phát hiện khuôn mặt (MTCNN) và trích xuất / đối chiếu đặc trưng khuôn mặt (FaceNet)."""

from dataclasses import dataclass
import os
import subprocess
import sys

import cv2
import numpy as np
import torch
from PIL import Image

try:
    from facenet_pytorch import InceptionResnetV1, MTCNN
except ImportError:
    InceptionResnetV1 = None
    MTCNN = None


# Ngưỡng Cosine Similarity để coi hai vector là cùng một người.
FACE_MATCH_THRESHOLD = 0.65
EMBEDDING_SIZE = 512


@dataclass
class FaceData:
    box: tuple[int, int, int, int]
    confidence: float

    @property
    def area(self) -> int:
        x1, y1, x2, y2 = self.box
        return max(0, x2 - x1) * max(0, y2 - y1)


def cosine_similarity(vector_a, vector_b) -> float:
    a = np.asarray(vector_a, dtype=np.float32)
    b = np.asarray(vector_b, dtype=np.float32)
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    if norm == 0.0:
        return 0.0
    return float(np.dot(a, b) / norm)


def embedding_to_bytes(embedding) -> bytes:
    return np.asarray(embedding, dtype=np.float32).tobytes()


def embedding_from_bytes(raw: bytes | None) -> list[float] | None:
    if not raw:
        return None
    vector = np.frombuffer(raw, dtype=np.float32)
    if vector.size != EMBEDDING_SIZE:
        return None
    return vector.astype(float).tolist()


class FaceService:
    def __init__(self) -> None:
        global InceptionResnetV1, MTCNN
        if MTCNN is None or InceptionResnetV1 is None:
            print("[SYS] Đang cài đặt facenet-pytorch==2.6.0 (--no-deps) trong luồng nền...")
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-q",
                    "--no-deps",
                    "--root-user-action=ignore",
                    "facenet-pytorch==2.6.0",
                ]
            )
            from facenet_pytorch import InceptionResnetV1 as _IRV1, MTCNN as _MTCNN

            InceptionResnetV1, MTCNN = _IRV1, _MTCNN

        # Trên Hugging Face Spaces (đặc biệt ZeroGPU), không gọi torch.cuda.is_available() ở main process
        if os.getenv("SPACE_ID") or os.getenv("FORCE_CPU") == "1":
            self.device = "cpu"
        else:
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        min_face = 24 if self.device == "cpu" else 40
        self.detector = MTCNN(keep_all=True, device=self.device, min_face_size=min_face)
        self.encoder: InceptionResnetV1 | None = None
        self.encoder_error: str | None = None
        try:
            # Lần chạy đầu cần Internet để tải trọng số vggface2 (~100 MB) vào cache torch.
            self.encoder = (
                InceptionResnetV1(pretrained="vggface2").eval().to(self.device)
            )
        except Exception as error:  # noqa: BLE001 - không để lỗi tải model làm sập server
            self.encoder_error = str(error)
            print(
                "[WARN] Không tải được FaceNet (InceptionResnetV1). "
                f"Hệ thống chỉ phát hiện khuôn mặt, không đối chiếu được: {error}"
            )

    @property
    def can_embed(self) -> bool:
        return self.encoder is not None

    def detect_from_bgr(self, frame: np.ndarray) -> list[FaceData]:
        """Phát hiện khuôn mặt trên khung hình BGR, sắp xếp theo độ tin cậy giảm dần."""
        height, width = frame.shape[:2]
        scale = 1.0
        if self.device == "cpu" and width > 320:
            scale = 320.0 / float(width)
            small_w = 320
            small_h = max(60, int(round(height * scale)))
            small_bgr = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_AREA)
            rgb_frame = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2RGB)
        else:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        image = Image.fromarray(rgb_frame)
        with torch.inference_mode():
            boxes, probabilities = self.detector.detect(image)
        if boxes is None or probabilities is None:
            return []

        inv_scale = 1.0 / scale
        results: list[FaceData] = []
        for raw_box, probability in zip(boxes, probabilities):
            if probability is None or np.isnan(probability):
                continue
            x1, y1, x2, y2 = [int(round(float(val) * inv_scale)) for val in raw_box]
            x1, x2 = max(0, x1), min(width, x2)
            y1, y2 = max(0, y1), min(height, y2)
            if x1 >= x2 or y1 >= y2:
                continue
            results.append(
                FaceData(box=(x1, y1, x2, y2), confidence=round(float(probability), 3))
            )

        results.sort(key=lambda face: face.confidence, reverse=True)
        return results

    def embed_face(
        self, frame: np.ndarray, box: tuple[int, int, int, int]
    ) -> list[float] | None:
        """Trích xuất vector đặc trưng 512 chiều (đã chuẩn hóa L2) cho một khuôn mặt."""
        if self.encoder is None:
            return None

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        face_tensor = self.detector.extract(
            image, np.asarray([box], dtype=np.float32), save_path=None
        )
        if face_tensor is None:
            return None
        if face_tensor.dim() == 3:
            face_tensor = face_tensor.unsqueeze(0)

        with torch.inference_mode():
            vector = self.encoder(face_tensor.to(self.device))[0]
        vector = torch.nn.functional.normalize(vector, p=2, dim=0).cpu().numpy()
        return vector.astype(float).tolist()

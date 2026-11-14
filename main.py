import base64
import json
import math
import os
import queue
import re
import sys
import threading
import time
from collections import Counter, deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from ultralytics import YOLO

from database import (
    HISTORY_LIMIT,
    PARKING_FEE_VND,
    DatabaseConfigurationError,
    DatabaseOperationError,
    fetch_overview,
    find_active_parking_session,
    flush_pending_plate_records,
    format_record_row,
    initialize_database,
    insert_plate_record,
    verify_checkout_face,
)
from face_service import (
    FACE_MATCH_THRESHOLD,
    FaceData,
    FaceService,
    cosine_similarity,
)


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
PLATE_MODEL_PATH = BASE_DIR / "weights" / "plate_best.pt"
CHAR_MODEL_PATH = BASE_DIR / "weights" / "chars_best.pt"
PENDING_FILE = BASE_DIR / "data" / "pending_records.json"

CONF_PLATE = 0.40
CONF_CHAR = 0.35

# Bỏ phiếu đồng thuận biển số độc lập trên từng Camera
VOTE_WINDOW_SECONDS = 3.0
VOTE_SAMPLE_INTERVAL_SECONDS = 0.12
VOTE_MIN_SAMPLES = 3
VOTE_MIN_SHARE = 0.70

# Cơ chế "Lưu hờ" (Two-Phase Latch): đợi khuôn mặt chuẩn nhất ở Camera đối diện (tối đa 4 giây)
# Ngưỡng độ nét (Laplacian Variance 128x128 trên vùng lõi 70% mặt):
# - Ảnh mặt mờ thực tế (media_1794468081037_1e129541.png) đo được = 12.85
# - Khuôn mặt rõ nét đạt >= 22.0 (chốt tức thì ở >= 28.0 kèm confidence >= 0.92)
FACE_MIN_CONFIDENCE = 0.85
FACE_MIN_SHARPNESS = 22.0
FACE_INSTANT_SHARPNESS = 28.0
FACE_SAMPLE_WINDOW_SECONDS = 0.18
FACE_MAX_SHARPNESS_WAIT_SECONDS = 0.50
FACE_PRE_LATCH_LOOKBACK_SECONDS = 0.85
FACE_RECENT_BUFFER_SECONDS = 1.20
LATCH_TIMEOUT_SECONDS = 4.0
MAX_BROWSER_FRAME_B64_CHARS = 2_500_000

# Không còn thấy khung biển số nào trong khoảng này => reset bộ đếm phiếu của cam đó
PLATE_LOST_RESET_SECONDS = 1.5
# Cùng một biển số + cùng một luồng (IN/OUT) không ghi trùng trong khoảng này
PLATE_COOLDOWN_SECONDS = 20.0
# Khóa ngắn hạn chiều ngược lại ngay sau khi xe vừa hoàn tất VÀO hoặc RA
# (tránh việc xe chạy qua mặt camera kia khi di chuyển qua cổng bị bắt nhầm chiều ngược lại)
CROSS_DIRECTION_COOLDOWN_SECONDS = 12.0
FACE_IDLE_EVERY_N_FRAMES = 2

DB_RETRY_SECONDS = 15.0
CAMERA_STOP_TIMEOUT_SECONDS = 5.0

CAMERA_BACKENDS = (
    ("Media Foundation", cv2.CAP_MSMF),
    ("DirectShow", cv2.CAP_DSHOW),
    ("Tự động", cv2.CAP_ANY),
)


# ============================================================================
# Chuẩn hóa biển số Việt Nam
# ============================================================================
PLATE_SERIES_RE = re.compile(r"^\d{2}[A-Z]{1,2}\d?$")
PLATE_NUMBER_RE = re.compile(r"^\d{4,5}$")
TO_DIGIT = {"D": "0", "B": "8", "S": "5", "Z": "2", "G": "6"}
TO_LETTER = {"0": "D", "8": "B", "5": "S", "2": "Z", "6": "G", "4": "A"}


def _clean_plate_key(text: str | None) -> str:
    return "".join(ch for ch in str(text or "").upper() if ch.isalnum())


def _try_parse_series_number(raw_chars: list[str], split_at: int) -> tuple[str, str] | None:
    if split_at < 3 or len(raw_chars) - split_at not in (4, 5):
        return None
    chars = list(raw_chars)
    for i in (0, 1):
        chars[i] = TO_DIGIT.get(chars[i], chars[i])
    chars[2] = TO_LETTER.get(chars[2], chars[2])
    # Toàn bộ 4 hoặc 5 ký tự của phần số phía sau đều ép về chữ số
    for i in range(split_at, len(chars)):
        chars[i] = TO_DIGIT.get(chars[i], chars[i])
    series = "".join(chars[:split_at])
    number = "".join(chars[split_at:])
    if PLATE_SERIES_RE.match(series) and PLATE_NUMBER_RE.match(number):
        return f"{series}{number}", f"{series}-{number}"
    return None


def normalize_plate(raw_text: str) -> tuple[str, str] | None:
    """Trả về (khóa bỏ phiếu, chuỗi hiển thị) hoặc None nếu không giống biển số VN."""
    if not raw_text:
        return None
    upper = raw_text.upper()
    chars = [ch for ch in upper if ch.isalnum()]
    if not 7 <= len(chars) <= 10:
        return None

    if upper.count("-") == 1:
        split_at = sum(ch.isalnum() for ch in upper.split("-")[0])
        parsed = _try_parse_series_number(chars, split_at)
        if parsed:
            return parsed

    for num_len in (5, 4):
        parsed = _try_parse_series_number(chars, len(chars) - num_len)
        if parsed:
            return parsed
    return None


# ============================================================================
# Nhận diện trên một khung hình
# ============================================================================
def _box_iou(box_a, box_b) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0, min(ay2, by2) - max(ay1, by1))
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union_area = area_a + area_b - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


def _deduplicate_chars(raw_chars, iou_threshold: float = 0.55):
    kept = []
    for candidate in sorted(raw_chars, key=lambda item: item[3], reverse=True):
        if any(_box_iou(candidate[4], existing[4]) > iou_threshold for existing in kept):
            continue
        kept.append(candidate)
    return kept


def _assemble_plate_text(chars) -> str:
    if len(chars) == 1:
        return chars[0][2]

    y_values = [char[1] for char in chars]
    char_heights = [max(1, char[4][3] - char[4][1]) for char in chars]
    avg_char_height = sum(char_heights) / len(char_heights)

    if max(y_values) - min(y_values) < avg_char_height * 0.6:
        return "".join(char[2] for char in sorted(chars, key=lambda char: char[0]))

    threshold = (min(y_values) + max(y_values)) / 2.0
    line_top = sorted((c for c in chars if c[1] < threshold), key=lambda c: c[0])
    line_bottom = sorted((c for c in chars if c[1] >= threshold), key=lambda c: c[0])
    text_top = "".join(char[2] for char in line_top)
    text_bottom = "".join(char[2] for char in line_bottom)
    if text_top and text_bottom:
        return f"{text_top}-{text_bottom}"
    return text_top + text_bottom


# Trên Hugging Face Spaces (ZeroGPU) không được chạm vào CUDA ở tiến trình chính -> ép YOLO chạy CPU
YOLO_DEVICE = "cpu" if (os.getenv("SPACE_ID") or os.getenv("FORCE_CPU") == "1") else None


def _yolo_kwargs() -> dict:
    return {"device": YOLO_DEVICE} if YOLO_DEVICE else {}


def _region_sharpness(
    frame, box: tuple[int, int, int, int], inner_ratio: float = 1.0
) -> float:
    """Đo độ sắc nét quang học (Laplacian Variance chuẩn hóa 128x128) để lọc bỏ ảnh bị rung/nhòe.
    Với khuôn mặt, dùng inner_ratio=0.70 để chỉ đo vùng lõi mặt, tránh nhiễu bởi rèm cửa/nền phía sau.
    """
    if frame is None:
        return 0.0
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = map(int, box)
    if 0.2 <= inner_ratio < 1.0:
        bw, bh = x2 - x1, y2 - y1
        mx = int(round(bw * (1.0 - inner_ratio) * 0.5))
        my = int(round(bh * (1.0 - inner_ratio) * 0.5))
        x1, x2 = x1 + mx, x2 - mx
        y1, y2 = y1 + my, y2 - my
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return 0.0
    roi = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _crop_to_data_url(
    frame,
    box: tuple[int, int, int, int],
    max_w: int = 360,
    max_h: int = 180,
    pad_ratio: float = 0.06,
) -> str | None:
    """Cắt vùng ảnh (biển số hoặc khuôn mặt), giữ độ nét cao và mã hóa JPEG Data URL."""
    if frame is None:
        return None
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = map(int, box)
    bw, bh = max(1, x2 - x1), max(1, y2 - y1)
    px, py = int(round(bw * pad_ratio)), int(round(bh * pad_ratio))
    cx1, cy1 = max(0, x1 - px), max(0, y1 - py)
    cx2, cy2 = min(w, x2 + px), min(h, y2 + py)
    if cx1 >= cx2 or cy1 >= cy2:
        return None
    crop = frame[cy1:cy2, cx1:cx2]
    ch, cw = crop.shape[:2]
    scale = min(max_w / cw, max_h / ch, 1.0)
    if scale < 1.0:
        crop = cv2.resize(
            crop,
            (max(1, round(cw * scale)), max(1, round(ch * scale))),
            interpolation=cv2.INTER_AREA,
        )
    ok, buf = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        return None
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _save_snapshot_to_disk(kind: str, plate_number: str, data_url: str | None) -> None:
    """Lưu thêm bản sao file ảnh (.jpg) vào data/snapshots/ để phục vụ kiểm tra trực tiếp."""
    if not data_url or "," not in data_url:
        return
    try:
        snap_dir = BASE_DIR / "data" / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        safe_plate = "".join(ch for ch in str(plate_number) if ch.isalnum() or ch in "-_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_bytes = base64.b64decode(data_url.split(",", 1)[1])
        (snap_dir / f"{ts}_{safe_plate}_{kind}.jpg").write_bytes(raw_bytes)
    except Exception:
        pass


def detect_plates(frame, plate_model: YOLO, char_model: YOLO, annotated=None):
    results = plate_model.predict(
        frame, conf=CONF_PLATE, iou=0.5, imgsz=640, verbose=False, **_yolo_kwargs()
    )[0]
    names = char_model.names
    height, width = frame.shape[:2]
    plate_present = False
    readings: dict[str, str] = {}
    plate_boxes: list[dict] = []
    plate_crops: dict[str, tuple[float, str]] = {}

    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x1 >= x2 or y1 >= y2:
            continue

        plate_present = True
        crop = frame[y1:y2, x1:x2]
        char_res = char_model.predict(
            crop, conf=CONF_CHAR, iou=0.5, imgsz=640, verbose=False, **_yolo_kwargs()
        )[0]

        raw_chars = []
        for char_box in char_res.boxes:
            cx1, cy1, cx2, cy2 = map(int, char_box.xyxy[0])
            raw_chars.append(
                (
                    (cx1 + cx2) / 2.0,
                    (cy1 + cy2) / 2.0,
                    names[int(char_box.cls[0])],
                    float(char_box.conf[0]),
                    (cx1, cy1, cx2, cy2),
                )
            )

        chars = _deduplicate_chars(raw_chars)
        raw_text = _assemble_plate_text(chars) if chars else ""

        normalized = normalize_plate(raw_text)
        label = normalized[1] if normalized else (raw_text or "?")
        if normalized:
            readings[normalized[0]] = normalized[1]
            plate_sharpness = _region_sharpness(frame, (x1, y1, x2, y2))
            crop_url = _crop_to_data_url(
                frame, (x1, y1, x2, y2), max_w=360, max_h=180, pad_ratio=0.06
            )
            if crop_url:
                prev = plate_crops.get(normalized[0])
                if prev is None or plate_sharpness >= prev[0]:
                    plate_crops[normalized[0]] = (plate_sharpness, crop_url)

        plate_boxes.append(
            {
                "x1": round(x1 / width, 4),
                "y1": round(y1 / height, 4),
                "x2": round(x2 / width, 4),
                "y2": round(y2 / height, 4),
                "label": label,
                "valid": bool(normalized),
            }
        )

        if annotated is not None:
            color = (0, 200, 0) if normalized else (0, 165, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
            for _, _, _, _, (cx1, cy1, cx2, cy2) in chars:
                cv2.rectangle(
                    annotated, (x1 + cx1, y1 + cy1), (x1 + cx2, y1 + cy2), (255, 0, 0), 1
                )
            cv2.putText(
                annotated,
                label,
                (x1, min(height - 5, y2 + 30)),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 255),
                2,
            )

    return plate_present, readings, plate_boxes, plate_crops


def draw_faces(annotated, faces: list[FaceData]) -> None:
    for idx, face in enumerate(faces, start=1):
        fx1, fy1, fx2, fy2 = face.box
        cv2.rectangle(annotated, (fx1, fy1), (fx2, fy2), (255, 0, 255), 2)
        cv2.putText(
            annotated,
            f"Face {idx} ({face.confidence:.0%})",
            (fx1, max(20, fy1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 0, 255),
            2,
        )


def resize_camera_preview(frame, max_width: int = 1120, max_height: int = 840):
    height, width = frame.shape[:2]
    scale = min(max_width / width, max_height / height, 1.0)
    if scale < 1.0:
        frame = cv2.resize(
            frame,
            (round(width * scale), round(height * scale)),
            interpolation=cv2.INTER_AREA,
        )
    return frame


def get_vote_result(observations):
    if not observations:
        return None
    votes = Counter(key for _, key, _ in observations)
    key, vote_count = votes.most_common(1)[0]
    display = Counter(d for _, k, d in observations if k == key).most_common(1)[0][0]
    return key, display, vote_count, vote_count / len(observations), len(observations)


def is_vote_confirmed(vote_result) -> bool:
    if vote_result is None:
        return False
    _, _, _, vote_share, sample_count = vote_result
    return sample_count >= VOTE_MIN_SAMPLES and vote_share >= VOTE_MIN_SHARE


def _face_score(face: FaceData, frame) -> tuple[float, float]:
    """Trả về (tổng điểm chất lượng, độ sắc nét Laplacian vùng lõi 70%) của khuôn mặt."""
    sharpness = _region_sharpness(frame, face.box, inner_ratio=0.70)
    score = (face.confidence ** 2) * math.pow(max(1.0, face.area), 0.25) * max(1.0, sharpness)
    return score, sharpness


# ============================================================================
# Camera
# ============================================================================
def open_camera(device_index: int):
    errors = []
    for backend_name, backend in CAMERA_BACKENDS:
        capture = None
        try:
            capture = cv2.VideoCapture(device_index, backend)
            if not capture.isOpened():
                errors.append(f"{backend_name}: không mở được")
                capture.release()
                continue

            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, frame = capture.read()
            if ok and frame is not None:
                return capture, frame, backend_name, errors

            errors.append(f"{backend_name}: mở được nhưng không đọc được hình")
            capture.release()
        except cv2.error as error:
            errors.append(f"{backend_name}: {error}")
            if capture is not None:
                capture.release()

    return None, None, None, errors


class FrameGrabber:
    MAX_CONSECUTIVE_FAILURES = 25

    def __init__(self, cam_id: int, device_index: int, capture, first_frame, backend_name: str) -> None:
        self.cam_id = cam_id
        self.device_index = device_index
        self.backend_name = backend_name
        self._capture = capture
        self._cond = threading.Condition()
        self._frame = first_frame
        self._seq = 1
        self._stopped = False
        self.failed = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        failures = 0
        try:
            while not self._stopped:
                ok, frame = self._capture.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= self.MAX_CONSECUTIVE_FAILURES:
                        with self._cond:
                            self.failed = True
                            self._cond.notify_all()
                        break
                    time.sleep(0.05)
                    continue
                failures = 0
                with self._cond:
                    self._frame = frame
                    self._seq += 1
                    self._cond.notify_all()
        finally:
            self._capture.release()

    def get_latest(self, last_seq: int):
        with self._cond:
            if self._seq == last_seq:
                return None, last_seq
            return self._frame, self._seq

    def stop(self) -> None:
        with self._cond:
            if self._stopped:
                return
            self._stopped = True
            self._cond.notify_all()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)


# ============================================================================
# Trạng thái riêng của từng Camera (Cam 1 & Cam 2)
# ============================================================================
class CameraUnitState:
    """Lưu trạng thái hình ảnh, bỏ phiếu biển số và bộ đệm khuôn mặt của 1 Camera."""

    def __init__(self, cam_id: int, default_port: int) -> None:
        self.cam_id = cam_id
        self.device_index = default_port
        self.backend_name: str | None = None
        # Trạng thái bật/tắt độc lập của từng camera
        self.active = False
        self.mode: str | None = None  # "local" (OpenCV) | "browser" (WebRTC) | None
        self.grabber: FrameGrabber | None = None
        self.latest_jpeg: bytes | None = None
        self.latest_boxes: dict = {"plates": [], "faces": []}
        self.jpeg_seq = 0
        self.current_plates: list[str] = []
        self.plate_in_view = False
        self.current_faces: list[float] = []
        self.ambiguous_frame = False
        self.reset_tracking()

    def clear_display(self) -> None:
        self.latest_jpeg = None
        self.latest_boxes = {"plates": [], "faces": []}
        self.current_plates = []
        self.plate_in_view = False
        self.current_faces = []
        self.ambiguous_frame = False

    def reset_tracking(self) -> None:
        self.observations: deque = deque()
        self.plate_crops: dict[str, tuple[float, str]] = {}
        self.last_sample_time = 0.0
        self.last_plate_seen: float | None = None
        # Lưu các khuôn mặt chuẩn gần nhất (now, score, confidence, frame, box, sharpness)
        self.recent_faces: deque = deque()


# ============================================================================
# Trạng thái hệ thống 2 Camera đối xứng (Cam 1 ↔ Cam 2 chéo luồng)
# ============================================================================
class SystemState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.control_lock = threading.Lock()
        self.db_write_lock = threading.Lock()

        self.plate_model: YOLO | None = None
        self.char_model: YOLO | None = None
        self.face_service: FaceService | None = None

        self.database_ready = False
        self.database_error: str | None = None
        self.pending_records: list[dict] = []
        self.records_version = 0
        self.overview_cache: dict[tuple, dict] = {}
        self.write_queue: queue.Queue = queue.Queue()
        self.writer_stop = threading.Event()
        self.writer_thread: threading.Thread | None = None

        # Hai camera đối xứng (bật/tắt riêng từng camera, tách biệt cổng khi bật cả 2):
        # - Cam nào chốt Biển số trước thì Cam đối diện (3 - plate_cam) bắt buộc xác thực Khuôn mặt
        # - Chiều VÀO (IN) / RA (OUT) tự động xác định theo trạng thái xe đang trong bãi (IN_PARKING)
        self.running = False  # True khi có ít nhất 1 camera đang bật
        self.browser_mode = False  # True khi có ít nhất 1 camera chạy qua WebRTC trình duyệt
        self.infer_lock = threading.Lock()
        self.session_id = 0
        self.cams: dict[int, CameraUnitState] = {
            1: CameraUnitState(cam_id=1, default_port=0),
            2: CameraUnitState(cam_id=2, default_port=1),
        }

        self.worker_thread: threading.Thread | None = None
        self.frame_count = 0
        self.camera_error: str | None = None
        self.last_confirmed: dict | None = None
        self.confirm_seq = 0

        # Thông báo kết quả cổng & cảnh báo an ninh khi lệch mặt lúc ra
        self.feedback_seq = 0
        self.gate_feedback: dict | None = None
        self.security_alert: dict | None = None

        self._reset_session_state_locked()

    def load_ai_models(self) -> None:
        if not PLATE_MODEL_PATH.is_file():
            raise RuntimeError(f"Không tìm thấy model biển số: {PLATE_MODEL_PATH}")
        if not CHAR_MODEL_PATH.is_file():
            raise RuntimeError(f"Không tìm thấy model ký tự: {CHAR_MODEL_PATH}")
        self.plate_model = YOLO(str(PLATE_MODEL_PATH))
        self.char_model = YOLO(str(CHAR_MODEL_PATH))
        self.face_service = FaceService()

    def _set_feedback_locked(self, fb_type: str, message: str) -> None:
        self.feedback_seq += 1
        self.gate_feedback = {
            "seq": self.feedback_seq,
            "type": fb_type,
            "message": message,
            "expires_at": time.monotonic() + 2.0,
        }

    def _reset_session_state_locked(self) -> None:
        for cam in self.cams.values():
            cam.reset_tracking()
        # recent_confirms lưu thời điểm hết hạn khóa: token -> expire_monotonic_time
        self.recent_confirms: dict[str, float] = {}
        # Trạng thái Lưu hờ (Two-Phase Latch)
        self.latched: dict | None = None
        self.face_window_start: float | None = None
        self.best_face: tuple[float, float, object, tuple, float] | None = None

    def _lock_plate_cooldown_locked(self, plate_key: str, direction: str, now: float) -> None:
        same_dir_token = f"{plate_key}:{direction}"
        opposite_dir = "OUT" if direction == "IN" else "IN"
        opp_dir_token = f"{plate_key}:{opposite_dir}"
        self.recent_confirms[same_dir_token] = now + PLATE_COOLDOWN_SECONDS
        # Khóa ngắn hạn chiều ngược lại để xe chạy qua mặt camera kia không bị bắt nhầm
        self.recent_confirms[opp_dir_token] = max(
            self.recent_confirms.get(opp_dir_token, 0.0),
            now + CROSS_DIRECTION_COOLDOWN_SECONDS,
        )

    # ---------------------------------------------------------- hàng chờ (file)
    def load_pending_from_disk(self) -> None:
        if not PENDING_FILE.is_file():
            return
        try:
            items = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
            for item in items:
                item["recognized_at"] = datetime.fromisoformat(item["recognized_at"])
            with self.db_write_lock:
                self.pending_records = items
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"[WARN] Không đọc được {PENDING_FILE}: {error}")

    def _persist_pending(self) -> None:
        try:
            if not self.pending_records:
                PENDING_FILE.unlink(missing_ok=True)
                return
            PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = [
                {
                    **{k: v for k, v in rec.items() if k != "_seq"},
                    "recognized_at": rec["recognized_at"].isoformat(),
                }
                for rec in self.pending_records
            ]
            tmp = PENDING_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(PENDING_FILE)
        except OSError as error:
            print(f"[WARN] Không ghi được {PENDING_FILE}: {error}")

    def get_pending_snapshot(self) -> list[dict]:
        with self.db_write_lock:
            return list(self.pending_records)

    def get_pending_count(self) -> int:
        with self.db_write_lock:
            return len(self.pending_records)

    # -------------------------------------------------------------- database
    def _set_db_status(self, ready: bool, error: str | None) -> None:
        with self.lock:
            self.database_ready = ready
            self.database_error = error

    def _bump_version(self) -> None:
        with self.lock:
            self.records_version += 1
            self.overview_cache.clear()

    def get_cached_overview(self, q: str, status: str, limit: int) -> dict | None:
        with self.lock:
            ver = self.records_version
            key = (ver, q.strip(), status.strip(), limit)
            cached = self.overview_cache.get(key)
        if cached is not None:
            return cached
        overview = fetch_overview(q, status, limit)
        with self.lock:
            if self.records_version == ver:
                self.overview_cache[key] = overview
        return overview

    def connect_database(self) -> int:
        try:
            initialize_database()
        except (DatabaseConfigurationError, DatabaseOperationError) as error:
            self._set_db_status(False, str(error))
            raise
        self._set_db_status(True, None)
        return self.flush_pending()

    def flush_pending(self) -> int:
        with self.db_write_lock:
            if not self.pending_records:
                return 0
            before = len(self.pending_records)
            try:
                flush_pending_plate_records(self.pending_records)
                self._set_db_status(True, None)
            except (DatabaseConfigurationError, DatabaseOperationError) as error:
                self._set_db_status(False, str(error))
                raise
            finally:
                flushed = before - len(self.pending_records)
                self._persist_pending()
                if flushed:
                    self._bump_version()
            return flushed

    def _store_record(self, record: dict) -> None:
        inserted_to_db = False
        with self.db_write_lock:
            with self.lock:
                ready = self.database_ready
            if ready:
                try:
                    _, match_score = insert_plate_record(record)
                    with self.lock:
                        if (
                            self.last_confirmed
                            and self.last_confirmed.get("seq") == record.get("_seq")
                        ):
                            preview = format_record_row(
                                "Mới",
                                {**record, "face_match_score": match_score},
                            )
                            self.last_confirmed["match_status"] = preview["Đối chiếu"]
                    self._bump_version()
                    inserted_to_db = True
                except (DatabaseConfigurationError, DatabaseOperationError) as error:
                    self._set_db_status(False, str(error))

            if not inserted_to_db:
                if str(record.get("direction", "IN")).upper() == "OUT":
                    rec_key = _clean_plate_key(record.get("plate_number"))
                    for pending_rec in self.pending_records:
                        if (
                            _clean_plate_key(pending_rec.get("plate_number")) == rec_key
                            and pending_rec.get("direction") == "IN"
                            and pending_rec.get("parking_status") == "IN_PARKING"
                        ):
                            pending_rec["parking_status"] = "COMPLETED"

                self.pending_records.append(record)
                self._persist_pending()
                self._bump_version()

        if inserted_to_db:
            try:
                self.get_cached_overview("", "all", HISTORY_LIMIT)
            except Exception:
                pass

    def _db_writer_loop(self) -> None:
        last_retry = time.monotonic()
        while not self.writer_stop.is_set():
            try:
                record = self.write_queue.get(timeout=1.0)
            except queue.Empty:
                record = None

            if record is not None:
                self._store_record(dict(record))
                continue

            with self.lock:
                ready = self.database_ready
            now = time.monotonic()
            if not ready and now - last_retry >= DB_RETRY_SECONDS:
                last_retry = now
                try:
                    flushed = self.connect_database()
                    print(f"[DB] Đã kết nối lại MySQL, đồng bộ {flushed} bản ghi chờ.")
                except (DatabaseConfigurationError, DatabaseOperationError):
                    pass

    def start_db_writer(self) -> None:
        self.writer_thread = threading.Thread(target=self._db_writer_loop, daemon=True)
        self.writer_thread.start()

    def stop_db_writer(self) -> None:
        self.writer_stop.set()
        if self.writer_thread is not None:
            self.writer_thread.join(timeout=3.0)

    # ------------------------------------------------- Latch & Security Alert APIs
    def cancel_latch(self) -> None:
        with self.lock:
            self._clear_latch_locked()
            for cam in self.cams.values():
                cam.observations.clear()

    def resolve_security_alert(self, approve: bool) -> dict:
        record_to_save = None
        now = time.monotonic()
        with self.lock:
            alert = self.security_alert
            if alert is None:
                return {"status": "none"}
            self.security_alert = None
            plate_key = alert.get("plate_key", "")
            direction = alert["record"].get("direction", "OUT")

            if approve:
                record_to_save = alert["record"]
                if plate_key:
                    self._lock_plate_cooldown_locked(plate_key, direction, now)
                self._set_feedback_locked(
                    "warn",
                    f"XE {record_to_save['plate_number']} RA BÃI ĐƯỢC DUYỆT",
                )
            else:
                # Khi TỪ CHỐI: xóa cooldown của biển số này để chủ xe thật có thể quét lại ngay
                if plate_key:
                    self.recent_confirms.pop(f"{plate_key}:OUT", None)
                for cam in self.cams.values():
                    cam.observations.clear()
                self._set_feedback_locked(
                    "error",
                    f"XE {alert['record']['plate_number']} RA BÃI BỊ TỪ CHỐI",
                )

        if record_to_save is not None:
            preview = format_record_row("Mới", record_to_save)
            with self.lock:
                self.last_confirmed = {
                    "seq": record_to_save["_seq"],
                    "plate_number": record_to_save["plate_number"],
                    "direction": preview["Luồng"],
                    "recognized_at": preview["Thời gian nhận diện"],
                    "consensus": preview["Đồng thuận biển số"],
                    "face_status": preview["Khuôn mặt"],
                    "match_status": preview["Đối chiếu"],
                }
            self.write_queue.put(record_to_save)
            return {"status": "approved"}
        return {"status": "rejected"}

    # ------------------------------------------------- Camera độc lập (bật/tắt riêng)
    def _refresh_running_locked(self) -> None:
        self.running = any(c.active for c in self.cams.values())
        self.browser_mode = any(
            c.active and c.mode == "browser" for c in self.cams.values()
        )

    def _clear_latch_locked(self) -> None:
        self.latched = None
        self.face_window_start = None
        self.best_face = None

    def start_camera(
        self, cam_id: int, device_index: int, prefer_browser: bool = False
    ) -> str:
        """Bật riêng 1 camera (Cam 1 hoặc Cam 2) tại cổng `device_index`."""
        if cam_id not in self.cams:
            raise ValueError("Camera ID phải là 1 hoặc 2.")

        with self.control_lock:
            with self.lock:
                cam = self.cams[cam_id]
                other = self.cams[3 - cam_id]
                if cam.active:
                    return cam.mode or "local"
                if other.active and other.device_index == device_index:
                    msg = (
                        f"Cổng {device_index} đang được dùng bởi Cam {other.cam_id}. "
                        "Khi bật 2 Camera, mỗi Camera phải dùng 1 cổng thiết bị riêng (hoặc chỉ bật 1 Camera)."
                    )
                    self.camera_error = msg
                    raise ValueError(msg)

            use_browser = prefer_browser or os.getenv("SPACE_ID") is not None
            grabber = None
            backend = "WebRTC (trình duyệt)"

            if not use_browser:
                cap, frame, backend, errors = open_camera(device_index)
                if cap is None:
                    if os.getenv("ALLOW_BROWSER_CAMERA", "1") == "1":
                        use_browser = True
                        backend = "WebRTC (trình duyệt)"
                    else:
                        msg = (
                            f"Không mở được Cam {cam_id} tại cổng {device_index} "
                            f"({'; '.join(errors)}). Hãy bấm 'Dò cổng' để xem các cổng đang hoạt động."
                        )
                        with self.lock:
                            self.camera_error = msg
                        raise ValueError(msg)
                else:
                    grabber = FrameGrabber(cam_id, device_index, cap, frame, backend)

            with self.lock:
                was_running = self.running
                if not was_running:
                    self.session_id += 1
                    self.frame_count = 0
                    self.security_alert = None
                    self._reset_session_state_locked()
                else:
                    # Đổi cấu hình camera giữa chừng -> hủy lượt lưu hờ đang dở
                    self._clear_latch_locked()
                    for c in self.cams.values():
                        c.observations.clear()

                cam.device_index = device_index
                cam.backend_name = backend
                cam.mode = "browser" if use_browser else "local"
                cam.grabber = grabber
                cam.active = True
                cam.clear_display()
                cam.reset_tracking()
                self.camera_error = None
                self._refresh_running_locked()

                if grabber is not None and self.worker_thread is None:
                    self.worker_thread = threading.Thread(
                        target=self._camera_worker_loop, daemon=True
                    )
                    self.worker_thread.start()
            return cam.mode

    def stop_camera(self, cam_id: int) -> None:
        """Tắt riêng 1 camera; camera còn lại (nếu đang bật) vẫn tiếp tục hoạt động."""
        if cam_id not in self.cams:
            return
        with self.control_lock:
            with self.lock:
                grabber = self._deactivate_cam_locked(cam_id)
            if grabber is not None:
                grabber.stop()

    def _deactivate_cam_locked(self, cam_id: int, error: str | None = None):
        """Tắt camera trong khi đang giữ `self.lock`. Trả về grabber cần dừng (nếu không còn ai dùng)."""
        cam = self.cams[cam_id]
        other = self.cams[3 - cam_id]
        if not cam.active:
            return None
        grabber = cam.grabber
        cam.active = False
        cam.mode = None
        cam.grabber = None
        cam.backend_name = None
        cam.clear_display()
        cam.reset_tracking()
        self._clear_latch_locked()
        if error:
            self.camera_error = error
        self._refresh_running_locked()
        if not self.running:
            self.session_id += 1
            self.security_alert = None
            self._reset_session_state_locked()
        return grabber

    def stop_cameras(self) -> None:
        for cam_id in (1, 2):
            self.stop_camera(cam_id)
        with self.lock:
            worker = self.worker_thread
        if worker is not None and worker.is_alive():
            worker.join(timeout=CAMERA_STOP_TIMEOUT_SECONDS)

    @staticmethod
    def _decode_b64_frame(data_str: str | None):
        if not data_str or len(data_str) > MAX_BROWSER_FRAME_B64_CHARS:
            return None
        try:
            raw_b64 = data_str.split(",", 1)[1] if "," in data_str else data_str
            buf = np.frombuffer(base64.b64decode(raw_b64), dtype=np.uint8)
            if buf.size == 0:
                return None
            return cv2.imdecode(buf, cv2.IMREAD_COLOR)
        except Exception:
            return None

    def ingest_browser_frames(
        self, cam1_b64: str | None, cam2_b64: str | None
    ) -> dict:
        with self.lock:
            b1 = self.cams[1].active and self.cams[1].mode == "browser"
            b2 = self.cams[2].active and self.cams[2].mode == "browser"
            if not (b1 or b2):
                return {"active": False}
            session_id = self.session_id

        frame1 = self._decode_b64_frame(cam1_b64) if b1 else None
        if b1 and b2 and cam1_b64 and cam2_b64 and cam2_b64 == cam1_b64:
            # Chặn gửi trùng cùng 1 khung hình cho cả 2 camera ở chế độ 2 luồng
            frame2 = None
        else:
            frame2 = self._decode_b64_frame(cam2_b64) if b2 else None
        if frame1 is None and frame2 is None:
            return {"active": True, "processed": False}

        if not self.infer_lock.acquire(blocking=False):
            with self.lock:
                b1_boxes = self.cams[1].latest_boxes if b1 else None
                b2_boxes = self.cams[2].latest_boxes if b2 else None
            return {
                "active": True,
                "processed": False,
                "cam1_boxes": b1_boxes,
                "cam2_boxes": b2_boxes,
            }
        try:
            self._process_dual_frames(session_id, frame1, frame2, encode_jpeg=False)
            with self.lock:
                b1_boxes = self.cams[1].latest_boxes if b1 else None
                b2_boxes = self.cams[2].latest_boxes if b2 else None
        except Exception as error:  # noqa: BLE001 - không để lỗi AI làm đứng hình
            print(f"[WARN] Lỗi xử lý AI khung hình trình duyệt: {error}")
            return {"active": True, "processed": False, "error": str(error)}
        finally:
            self.infer_lock.release()

        return {
            "active": True,
            "processed": True,
            "cam1_boxes": b1_boxes,
            "cam2_boxes": b2_boxes,
        }

    def _camera_worker_loop(self) -> None:
        """Luồng xử lý AI cho các camera cục bộ (OpenCV). Tự thoát khi không còn camera cục bộ nào bật."""
        last_seq: dict[int, int] = {}
        try:
            while True:
                to_stop = []
                with self.lock:
                    g1 = self.cams[1].grabber if self.cams[1].active else None
                    g2 = self.cams[2].grabber if self.cams[2].active else None
                    if g1 is None and g2 is None:
                        self.worker_thread = None
                        return
                    # Camera bị mất tín hiệu -> chỉ tắt riêng camera đó
                    for cam_id, g in ((1, g1), (2, g2)):
                        if g is not None and g.failed:
                            stopped = self._deactivate_cam_locked(
                                cam_id,
                                f"Cam {cam_id} (cổng {g.device_index}) bị ngắt tín hiệu hình ảnh.",
                            )
                            if stopped is not None:
                                to_stop.append(stopped)
                    if to_stop:
                        g1 = self.cams[1].grabber if self.cams[1].active else None
                        g2 = self.cams[2].grabber if self.cams[2].active else None
                    session_id = self.session_id

                for g in to_stop:
                    g.stop()

                frame1 = frame2 = None
                if g1 is not None:
                    frame1, last_seq[id(g1)] = g1.get_latest(last_seq.get(id(g1), 0))
                if g2 is not None:
                    frame2, last_seq[id(g2)] = g2.get_latest(last_seq.get(id(g2), 0))

                if frame1 is None and frame2 is None:
                    time.sleep(0.015)
                    continue

                try:
                    with self.infer_lock:
                        self._process_dual_frames(session_id, frame1, frame2)
                except Exception as error:  # noqa: BLE001
                    print(f"[WARN] Lỗi xử lý AI trên camera cục bộ: {error}")
                    with self.lock:
                        self.camera_error = f"Lỗi xử lý AI: {error}"
                    time.sleep(0.2)
        finally:
            with self.lock:
                if self.worker_thread is threading.current_thread():
                    self.worker_thread = None

    def _analyze_single_cam_frame(
        self,
        frame,
        run_face_idle: bool,
        is_required_face_cam: bool,
        encode_jpeg: bool = True,
        skip_plate_ocr: bool = False,
    ):
        annotated = frame.copy() if encode_jpeg else None
        if (
            not skip_plate_ocr
            and self.plate_model is not None
            and self.char_model is not None
        ):
            plate_present, readings, plate_boxes, plate_crops = detect_plates(
                frame, self.plate_model, self.char_model, annotated
            )
        else:
            plate_present, readings, plate_boxes, plate_crops = False, {}, [], {}

        faces: list[FaceData] = []
        if self.face_service is not None and (
            plate_present or is_required_face_cam or run_face_idle
        ):
            faces = self.face_service.detect_from_bgr(frame)
            if annotated is not None:
                draw_faces(annotated, faces)

        jpeg_bytes = None
        if annotated is not None:
            ok_enc, buffer = cv2.imencode(
                ".jpg",
                resize_camera_preview(annotated),
                [int(cv2.IMWRITE_JPEG_QUALITY), 82],
            )
            jpeg_bytes = buffer.tobytes() if ok_enc else None

        height, width = frame.shape[:2]
        face_boxes = [
            {
                "x1": round(f.box[0] / width, 4),
                "y1": round(f.box[1] / height, 4),
                "x2": round(f.box[2] / width, 4),
                "y2": round(f.box[3] / height, 4),
                "label": f"Mặt {idx} ({f.confidence:.0%})",
            }
            for idx, f in enumerate(faces, start=1)
        ]
        overlay_boxes = {"plates": plate_boxes, "faces": face_boxes}

        return plate_present, readings, plate_crops, faces, jpeg_bytes, overlay_boxes

    def _process_dual_frames(
        self, session_id: int, frame1, frame2, encode_jpeg: bool = True
    ) -> None:
        with self.lock:
            if self.session_id != session_id:
                return
            current_frame_idx = self.frame_count
            required_face_cam = (
                self.latched["required_face_cam"] if self.latched is not None else None
            )
            latched_plate_cam = (
                self.latched["plate_cam"] if self.latched is not None else None
            )
            active1 = self.cams[1].active
            active2 = self.cams[2].active

        dual_cam_mode = bool(active1 and active2)
        run_face_idle = current_frame_idx % FACE_IDLE_EVERY_N_FRAMES == 0

        # Khi đang Lưu hờ ở chế độ 2 Cam:
        # - Cam lấy mặt (required_face_cam) bỏ qua YOLO biển số để dồn 100% tốc độ cho MTCNN bắt nét mặt tức thì.
        # - Cam biển số (latched_plate_cam) chỉ quét YOLO cách nhịp (mỗi 2 frame) để kiểm tra chống tráo xe.
        skip_plate_1 = bool(
            dual_cam_mode
            and required_face_cam is not None
            and (
                required_face_cam == 1
                or (latched_plate_cam == 1 and current_frame_idx % 2 == 1)
            )
        )
        skip_plate_2 = bool(
            dual_cam_mode
            and required_face_cam is not None
            and (
                required_face_cam == 2
                or (latched_plate_cam == 2 and current_frame_idx % 2 == 1)
            )
        )

        res1 = (
            self._analyze_single_cam_frame(
                frame1,
                run_face_idle and required_face_cam is None,
                required_face_cam == 1 or not dual_cam_mode,
                encode_jpeg=encode_jpeg,
                skip_plate_ocr=skip_plate_1,
            )
            if (active1 and frame1 is not None)
            else None
        )
        res2 = (
            self._analyze_single_cam_frame(
                frame2,
                run_face_idle and required_face_cam is None,
                required_face_cam == 2 or not dual_cam_mode,
                encode_jpeg=encode_jpeg,
                skip_plate_ocr=skip_plate_2,
            )
            if (active2 and frame2 is not None)
            else None
        )

        now = time.monotonic()
        commit_pair = None

        with self.lock:
            if self.session_id != session_id:
                return

            # Dọn các khóa chống trùng đã hết hạn
            self.recent_confirms = {
                token: exp for token, exp in self.recent_confirms.items() if exp > now
            }

            for cam_id, res, raw_frame in ((1, res1, frame1), (2, res2, frame2)):
                if res is None:
                    continue
                plate_present, readings, plate_crops, faces, jpeg_bytes, overlay_boxes = res
                cam = self.cams[cam_id]
                if plate_crops:
                    for p_key, (p_sharp, p_url) in plate_crops.items():
                        prev = cam.plate_crops.get(p_key)
                        if prev is None or p_sharp >= prev[0]:
                            cam.plate_crops[p_key] = (p_sharp, p_url)

                # Cập nhật lịch sử bỏ phiếu biển số của riêng Cam này
                while (
                    cam.observations
                    and now - cam.observations[0][0] > VOTE_WINDOW_SECONDS
                ):
                    cam.observations.popleft()

                if plate_present:
                    cam.last_plate_seen = now
                elif (
                    cam.last_plate_seen is not None
                    and now - cam.last_plate_seen >= PLATE_LOST_RESET_SECONDS
                ):
                    cam.observations.clear()
                    cam.last_plate_seen = None

                if (
                    len(readings) == 1
                    and now - cam.last_sample_time >= VOTE_SAMPLE_INTERVAL_SECONDS
                ):
                    key, display = next(iter(readings.items()))
                    cam.observations.append((now, key, display))
                    cam.last_sample_time = now

                # Cập nhật bộ đệm khuôn mặt chuẩn gần nhất trên Cam này
                while (
                    cam.recent_faces
                    and now - cam.recent_faces[0][0] > FACE_RECENT_BUFFER_SECONDS
                ):
                    cam.recent_faces.popleft()

                valid_faces = [
                    f for f in faces if f.confidence >= FACE_MIN_CONFIDENCE
                ]
                if valid_faces and raw_frame is not None:
                    scored_faces = [
                        (*_face_score(f, raw_frame), f) for f in valid_faces
                    ]
                    best_score, best_sharpness, best_in_frame = max(
                        scored_faces, key=lambda item: item[0]
                    )
                    cam.recent_faces.append(
                        (
                            now,
                            best_score,
                            best_in_frame.confidence,
                            raw_frame,
                            best_in_frame.box,
                            best_sharpness,
                        )
                    )

                # Chỉ cập nhật hình ảnh / thông tin hiển thị cho camera đang bật
                if not cam.active:
                    continue
                cam.ambiguous_frame = len(readings) > 1
                cam.plate_in_view = plate_present
                cam.current_plates = list(readings.values())
                cam.current_faces = [f.confidence for f in faces]
                cam.latest_boxes = overlay_boxes
                if jpeg_bytes is not None:
                    cam.latest_jpeg = jpeg_bytes
                    cam.jpeg_seq += 1

            confirmed_candidates: dict[int, str] = {}
            if self.security_alert is None and self.latched is None:
                for cid in (1, 2):
                    v_check = get_vote_result(self.cams[cid].observations)
                    if is_vote_confirmed(v_check):
                        cand_key, cand_display, _, _, _ = v_check
                        # Bỏ qua ngay nếu cả 2 chiều IN & OUT đều đang trong thời gian khóa Cooldown (tránh query DB lặp)
                        if (
                            f"{cand_key}:IN" in self.recent_confirms
                            and f"{cand_key}:OUT" in self.recent_confirms
                        ):
                            self.cams[cid].observations.clear()
                            continue
                        confirmed_candidates[cid] = cand_display

        # Truy vấn DB kiểm tra phiên gửi xe bên NGOÀI self.lock (lấy luôn embedding lượt VÀO để không phải query lần 2)
        active_session_map: dict[str, tuple[dict | None, bool]] = {}
        for cand_plate in set(confirmed_candidates.values()):
            active_session_map[cand_plate] = self._get_active_parking_session(cand_plate)

        with self.lock:
            if self.session_id != session_id:
                return
            dual_cam_mode = bool(self.cams[1].active and self.cams[2].active)

            # ------------------------------------------------------------------
            # Xử lý máy trạng thái 2 Pha đối xứng (Lưu hờ Biển số -> Chốt Khuôn mặt):
            #   - Khi bật cả 2 Camera (dual_cam_mode = True):
            #       + Cam 1 chốt Biển số => BẮT BUỘC Cam 2 phải thấy Khuôn mặt
            #       + Cam 2 chốt Biển số => BẮT BUỘC Cam 1 phải thấy Khuôn mặt
            #   - Khi chỉ bật 1 Camera dự phòng (dual_cam_mode = False):
            #       + Cam đang bật vừa chốt Biển số vừa lấy Khuôn mặt
            #   - Chiều VÀO (IN) / RA (OUT) tự động xác định theo trạng thái xe trong bãi:
            #       + Chưa có trong bãi => VÀO BÃI (IN)
            #       + Đang gửi trong bãi (IN_PARKING) => RA BÃI (OUT, đối chiếu FaceNet >= 65%)
            # ------------------------------------------------------------------
            if self.security_alert is None:
                if self.latched is None:
                    active_cam_ids = [cid for cid in (2, 1) if self.cams[cid].active]
                    for plate_cam_id in active_cam_ids:
                        cam = self.cams[plate_cam_id]
                        vote = get_vote_result(cam.observations)
                        if not is_vote_confirmed(vote):
                            continue

                        key, display, vote_count, vote_share, sample_count = vote
                        active_session, db_ok = active_session_map.get(
                            display, (None, True)
                        )
                        if not db_ok:
                            # Không tự ý gán chiều IN khi lỗi kết nối MySQL (tránh thu phí 2 lần cho xe đang gửi)
                            cam.observations.clear()
                            self._set_feedback_locked(
                                "error",
                                f"LỖI KẾT NỐI CSDL — TẠM HOÃN XÁC THỰC XE {display}",
                            )
                            continue

                        direction = "OUT" if active_session is not None else "IN"
                        target_face_cam_id = (
                            (3 - plate_cam_id) if dual_cam_mode else plate_cam_id
                        )

                        cooldown_token = f"{key}:{direction}"
                        if cooldown_token in self.recent_confirms:
                            cam.observations.clear()
                            continue

                        best_plate_crop = cam.plate_crops.get(key)
                        self.latched = {
                            "direction": direction,
                            "plate_key": key,
                            "plate_number": display,
                            "plate_image": best_plate_crop[1] if best_plate_crop else None,
                            "vote_count": vote_count,
                            "sample_count": sample_count,
                            "consensus_rate": round(vote_share, 4),
                            "plate_cam": plate_cam_id,
                            "required_face_cam": target_face_cam_id,
                            "latched_at": now,
                            "active_session": active_session,
                        }
                        self.face_window_start = None
                        self.best_face = None
                        cam.observations.clear()
                        cam.plate_crops.clear()

                        # Giữ lại các khuôn mặt vừa xuất hiện trên Cam đối diện trong lúc đang bỏ phiếu biển số
                        opp_cam = self.cams[target_face_cam_id]
                        while (
                            opp_cam.recent_faces
                            and now - opp_cam.recent_faces[0][0] > FACE_PRE_LATCH_LOOKBACK_SECONDS
                        ):
                            opp_cam.recent_faces.popleft()
                        if opp_cam.recent_faces:
                            best_recent = max(opp_cam.recent_faces, key=lambda item: item[1])
                            self.face_window_start = opp_cam.recent_faces[0][0]
                            self.best_face = (
                                best_recent[1],
                                best_recent[2],
                                best_recent[3],
                                best_recent[4],
                                best_recent[5],
                            )
                        break

                if self.latched is not None:
                    elapsed_latch = now - self.latched["latched_at"]
                    plate_cam_obj = self.cams[self.latched["plate_cam"]]
                    # Chống đánh tráo xe trong lúc đang Lưu hờ: nếu xuất hiện biển số hợp lệ khác thì hủy ngay
                    swapped_plate = any(
                        _clean_plate_key(p) != self.latched["plate_key"]
                        for p in plate_cam_obj.current_plates
                    )
                    if swapped_plate:
                        dir_text = "VÀO BÃI" if self.latched["direction"] == "IN" else "RA BÃI"
                        self._set_feedback_locked(
                            "warn",
                            f"XE {self.latched['plate_number']} {dir_text} HỦY LƯU HỜ (ĐÃ ĐỔI XE MỚI)",
                        )
                        self._clear_latch_locked()
                    elif elapsed_latch > LATCH_TIMEOUT_SECONDS:
                        dir_text = "VÀO BÃI" if self.latched["direction"] == "IN" else "RA BÃI"
                        self._set_feedback_locked(
                            "warn",
                            f"XE {self.latched['plate_number']} {dir_text} HỦY LƯU HỜ (THIẾU KHUÔN MẶT)",
                        )
                        self._clear_latch_locked()
                    else:
                        req_cam_id = self.latched["required_face_cam"]
                        req_cam = self.cams[req_cam_id]
                        latched_at = self.latched["latched_at"]
                        if req_cam.recent_faces:
                            if self.face_window_start is None:
                                self.face_window_start = now
                            for f_ts, f_score, f_conf, f_frame, f_box, f_sharp in req_cam.recent_faces:
                                if f_ts < latched_at - FACE_PRE_LATCH_LOOKBACK_SECONDS:
                                    continue
                                if self.best_face is None or f_score > self.best_face[0]:
                                    self.best_face = (f_score, f_conf, f_frame, f_box, f_sharp)

                        face_wait_elapsed = (
                            now - self.face_window_start
                            if self.face_window_start is not None
                            else 0.0
                        )
                        is_instant_sharp = (
                            self.best_face is not None
                            and self.best_face[1] >= 0.92
                            and self.best_face[4] >= FACE_INSTANT_SHARPNESS
                        )
                        is_sharp_enough = (
                            self.best_face is not None
                            and (
                                is_instant_sharp
                                or (
                                    face_wait_elapsed >= FACE_SAMPLE_WINDOW_SECONDS
                                    and self.best_face[4] >= FACE_MIN_SHARPNESS
                                )
                                or face_wait_elapsed >= FACE_MAX_SHARPNESS_WAIT_SECONDS
                            )
                        )
                        if (
                            self.best_face is not None
                            and self.face_window_start is not None
                            and is_sharp_enough
                        ):
                            latched_info = self.latched
                            best_face = self.best_face
                            self.confirm_seq += 1

                            commit_pair = (
                                {
                                    "_seq": self.confirm_seq,
                                    "_session_id": session_id,
                                    "_plate_key": latched_info["plate_key"],
                                    "_active_session": latched_info.get("active_session"),
                                    "plate_number": latched_info["plate_number"],
                                    "plate_image": latched_info.get("plate_image"),
                                    "direction": latched_info["direction"],
                                    "parking_status": (
                                        "IN_PARKING"
                                        if latched_info["direction"] == "IN"
                                        else "EXITED"
                                    ),
                                    "fee_amount": (
                                        PARKING_FEE_VND
                                        if latched_info["direction"] == "IN"
                                        else 0
                                    ),
                                    "recognized_at": datetime.now().replace(
                                        microsecond=0
                                    ),
                                    "vote_count": latched_info["vote_count"],
                                    "sample_count": latched_info["sample_count"],
                                    "consensus_rate": latched_info["consensus_rate"],
                                    "face_detected": True,
                                    "face_confidence": best_face[1],
                                    "camera_index": self.cams[
                                        latched_info["plate_cam"]
                                    ].device_index,
                                },
                                best_face,
                            )
                            self._clear_latch_locked()
                            req_cam.recent_faces.clear()

            self.frame_count += 1

        if commit_pair is not None:
            self._commit_latched_pair(*commit_pair)

    def _get_active_parking_session(
        self, plate_number: str
    ) -> tuple[dict | None, bool]:
        """Trả về (active_session, db_ok). Nếu lỗi kết nối DB mà không có bản ghi pending thì db_ok = False."""
        pending_sess = self._find_pending_active_session(plate_number)
        if pending_sess is not None:
            return pending_sess, True
        with self.lock:
            db_ready = self.database_ready
        if db_ready:
            try:
                return find_active_parking_session(plate_number), True
            except (DatabaseConfigurationError, DatabaseOperationError) as error:
                self._set_db_status(False, str(error))
                return None, False
        return None, True

    def _find_pending_active_session(self, plate_number: str) -> dict | None:
        target_key = _clean_plate_key(plate_number)
        with self.db_write_lock:
            for rec in reversed(self.pending_records):
                if (
                    _clean_plate_key(rec.get("plate_number")) == target_key
                    and rec.get("direction") == "IN"
                    and rec.get("parking_status") == "IN_PARKING"
                ):
                    return {
                        "id": None,
                        "recognized_at": str(rec.get("recognized_at")),
                        "embedding": rec.get("face_embedding"),
                    }
        return None

    def _commit_latched_pair(self, record: dict, best_face) -> None:
        """Trích xuất vector 512 chiều của Khuôn mặt chuẩn nhất từ Camera đối diện và:
        - Nếu là chiều VÀO ('IN'): Lưu đồng thời (Biển số + Khuôn mặt + VÀO) vào MySQL.
        - Nếu là chiều RA ('OUT'): Đối chiếu Cosine giữa Khuôn mặt hiện tại với lượt VÀO;
          nếu Khớp >= 65% thì ghi vào MySQL, nếu Lệch < 65% thì bật Cảnh báo an ninh."""
        commit_session_id = record.pop("_session_id", self.session_id)
        plate_key = record.pop("_plate_key", "")
        cached_active_session = record.pop("_active_session", None)
        embedding = None
        face_image = None
        if best_face is not None:
            face_image = _crop_to_data_url(
                best_face[2], best_face[3], max_w=320, max_h=320, pad_ratio=0.22
            )
            if self.face_service is not None:
                try:
                    embedding = self.face_service.embed_face(best_face[2], best_face[3])
                except Exception as error:  # noqa: BLE001
                    print(f"[WARN] Không trích xuất được vector khuôn mặt: {error}")
        record["face_embedding"] = embedding
        record["face_image"] = face_image

        direction = record["direction"]
        plate = record["plate_number"]
        now = time.monotonic()

        if direction == "OUT":
            check = None
            if cached_active_session is not None:
                prev_emb = cached_active_session.get("embedding")
                if embedding and prev_emb:
                    score = max(
                        -1.0, min(1.0, cosine_similarity(embedding, prev_emb))
                    )
                    check = {
                        "has_active_session": True,
                        "entry_id": cached_active_session.get("id"),
                        "entry_time": cached_active_session.get("recognized_at"),
                        "match_score": score,
                        "matched": score >= FACE_MATCH_THRESHOLD,
                    }
            if check is None:
                with self.lock:
                    db_ready = self.database_ready
                if db_ready:
                    try:
                        check = verify_checkout_face(plate, embedding)
                    except (DatabaseConfigurationError, DatabaseOperationError) as error:
                        self._set_db_status(False, str(error))

            if check is None or not check.get("has_active_session"):
                pending_sess = self._find_pending_active_session(plate)
                if pending_sess is not None:
                    prev_emb = pending_sess.get("embedding")
                    if embedding and prev_emb:
                        score = max(
                            -1.0, min(1.0, cosine_similarity(embedding, prev_emb))
                        )
                        check = {
                            "has_active_session": True,
                            "entry_id": None,
                            "entry_time": pending_sess["recognized_at"],
                            "match_score": score,
                            "matched": score >= FACE_MATCH_THRESHOLD,
                        }

            if check and check.get("has_active_session"):
                record["entry_record_id"] = check.get("entry_id")
                record["face_match_score"] = check.get("match_score")
                score_val = check.get("match_score")
                score_pct = (
                    f"{max(0.0, float(score_val)):.0%}"
                    if score_val is not None
                    else "0%"
                )

                if not check.get("matched", False):
                    # Lệch khuôn mặt: Chưa đặt cooldown để nếu Từ chối thì chủ xe thật quét lại được ngay
                    with self.lock:
                        if self.session_id != commit_session_id:
                            return
                        self.security_alert = {
                            "plate_key": plate_key,
                            "plate_number": plate,
                            "entry_time": check.get("entry_time") or "-",
                            "match_score_pct": score_pct,
                            "face_confidence_pct": f"{record['face_confidence']:.0%}",
                            "record": record,
                        }
                    return

                with self.lock:
                    if self.session_id != commit_session_id:
                        return
                    if plate_key:
                        self._lock_plate_cooldown_locked(plate_key, "OUT", now)
                    self._set_feedback_locked(
                        "success",
                        f"XE {plate} RA BÃI THÀNH CÔNG",
                    )
            else:
                with self.lock:
                    if self.session_id != commit_session_id:
                        return
                    if plate_key:
                        self._lock_plate_cooldown_locked(plate_key, "OUT", now)
                    self._set_feedback_locked(
                        "warn",
                        f"XE {plate} RA BÃI (CHƯA CÓ LƯỢT VÀO)",
                    )
        else:
            with self.lock:
                if self.session_id != commit_session_id:
                    return
                if plate_key:
                    self._lock_plate_cooldown_locked(plate_key, "IN", now)
                self._set_feedback_locked(
                    "success",
                    f"XE {plate} VÀO BÃI THÀNH CÔNG",
                )

        _save_snapshot_to_disk("plate", record["plate_number"], record.get("plate_image"))
        _save_snapshot_to_disk("face", record["plate_number"], face_image)

        preview = format_record_row("Mới", record)
        with self.lock:
            self.last_confirmed = {
                "seq": record["_seq"],
                "plate_number": record["plate_number"],
                "direction": preview["Luồng"],
                "recognized_at": preview["Thời gian nhận diện"],
                "consensus": preview["Đồng thuận biển số"],
                "face_status": preview["Khuôn mặt"],
                "match_status": preview["Đối chiếu"],
            }
        self.write_queue.put(record)

    def _background_startup(self) -> None:
        try:
            flushed = self.connect_database()
            if flushed:
                print(f"[DB] Đã đồng bộ {flushed} bản ghi chờ từ lần chạy trước.")
            self.get_cached_overview("", "all", HISTORY_LIMIT)
        except (DatabaseConfigurationError, DatabaseOperationError) as error:
            print(f"[WARN] Chưa kết nối được MySQL, bản ghi sẽ được lưu tạm: {error}")
        self.start_db_writer()
        self.load_ai_models()

    def startup(self) -> None:
        self.load_pending_from_disk()
        # Khởi tạo kết nối MySQL Aiven + tải mô hình AI trong luồng nền để cổng HTTP mở tức thì
        threading.Thread(target=self._background_startup, daemon=True).start()


state = SystemState()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state.startup()
    try:
        yield
    finally:
        state.stop_cameras()
        state.stop_db_writer()


app = FastAPI(
    title="Hệ thống Nhận diện Khuôn mặt & Biển số xe AI (2 Camera)",
    lifespan=lifespan,
)


class StartDualCameraRequest(BaseModel):
    cam1_index: int = Field(default=0, ge=0, le=10)
    cam2_index: int = Field(default=1, ge=0, le=10)
    prefer_browser: bool = False


class StartSingleCameraRequest(BaseModel):
    device_index: int = Field(default=0, ge=0, le=10)
    prefer_browser: bool = False


class BrowserDualFrameRequest(BaseModel):
    cam1_image: str | None = None
    cam2_image: str | None = None


class ResolveAlertRequest(BaseModel):
    action: Literal["approve", "reject"]


NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate"}


@app.api_route("/", methods=["GET", "HEAD"])
@app.api_route("/ui", methods=["GET", "HEAD"])
async def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"), headers=NO_CACHE_HEADERS)


@app.get("/styles.css")
async def serve_styles():
    return FileResponse(str(FRONTEND_DIR / "styles.css"), headers=NO_CACHE_HEADERS)


@app.get("/app.js")
async def serve_app_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"), headers=NO_CACHE_HEADERS)


def _serialize_cam_unit(cam: CameraUnitState) -> dict:
    vote_info = None
    vote_res = get_vote_result(cam.observations)
    if vote_res is not None:
        _, display, vote_count, vote_share, sample_count = vote_res
        vote_info = {
            "candidate": display,
            "vote_count": vote_count,
            "sample_count": sample_count,
            "vote_share": vote_share,
        }
    return {
        "cam_id": cam.cam_id,
        "active": cam.active,
        "mode": cam.mode,
        "device_index": cam.device_index,
        "backend": cam.backend_name,
        "plate_in_view": cam.plate_in_view,
        "current_plates": list(cam.current_plates),
        "current_faces": list(cam.current_faces),
        "ambiguous_frame": cam.ambiguous_frame,
        "vote": vote_info,
    }


@app.get("/api/camera/status")
def get_camera_status():
    now = time.monotonic()
    pending_count = len(state.pending_records)
    with state.lock:
        cam1_status = _serialize_cam_unit(state.cams[1])
        cam2_status = _serialize_cam_unit(state.cams[2])

        # Chọn thông tin vote đang hoạt động mạnh nhất để hiển thị trên pill tổng
        active_vote = cam2_status["vote"] or cam1_status["vote"]

        latched_info = None
        if state.latched is not None:
            remaining = max(
                0,
                round(LATCH_TIMEOUT_SECONDS - (now - state.latched["latched_at"])),
            )
            latched_info = {
                "direction": state.latched["direction"],
                "direction_label": (
                    "ĐI VÀO (Check-in)"
                    if state.latched["direction"] == "IN"
                    else "ĐI RA (Check-out)"
                ),
                "plate_number": state.latched["plate_number"],
                "plate_cam": state.latched["plate_cam"],
                "required_face_cam": state.latched["required_face_cam"],
                "remaining_seconds": remaining,
                "sampling_face": state.face_window_start is not None,
            }

        alert_info = None
        if state.security_alert is not None:
            alert_info = {
                "plate_number": state.security_alert["plate_number"],
                "entry_time": state.security_alert["entry_time"],
                "match_score_pct": state.security_alert["match_score_pct"],
                "face_confidence_pct": state.security_alert["face_confidence_pct"],
            }

        if (
            state.gate_feedback is not None
            and now >= state.gate_feedback.get("expires_at", 0.0)
        ):
            state.gate_feedback = None

        return {
            "running": state.running,
            "mode": "browser" if state.browser_mode else "local",
            "frame_count": state.frame_count,
            "cam1": cam1_status,
            "cam2": cam2_status,
            "vote": active_vote,
            "latched": latched_info,
            "security_alert": alert_info,
            "gate_feedback": state.gate_feedback,
            "ambiguous_frame": (
                cam1_status["ambiguous_frame"] or cam2_status["ambiguous_frame"]
            ),
            "error": state.camera_error,
            "last_confirmed": state.last_confirmed,
            "records_version": state.records_version,
            "database_ready": state.database_ready,
            "pending_count": pending_count,
            "face_matching": bool(state.face_service and state.face_service.can_embed),
        }


@app.post("/api/camera/cancel-latch")
def api_cancel_latch():
    state.cancel_latch()
    return {"status": "cancelled"}


@app.post("/api/camera/resolve-alert")
def api_resolve_alert(req: ResolveAlertRequest):
    approve = req.action.strip().lower() == "approve"
    return state.resolve_security_alert(approve)


@app.post("/api/camera/scan")
def scan_cameras():
    if os.getenv("SPACE_ID") is not None:
        return {"cameras": []}
    with state.control_lock:
        with state.lock:
            busy_local = {
                c.device_index: c.backend_name
                for c in state.cams.values()
                if c.active and c.mode == "local"
            }
        found = []
        for index in range(6):
            if index in busy_local:
                found.append({"index": index, "backend": busy_local[index] or "Đang kết nối"})
                continue
            test_cap, _, backend_name, _ = open_camera(index)
            if test_cap is not None:
                found.append({"index": index, "backend": backend_name})
                test_cap.release()
        return {"cameras": found}


@app.post("/api/camera/{cam_id}/start")
def api_start_single_camera(cam_id: int, req: StartSingleCameraRequest):
    if cam_id not in (1, 2):
        raise HTTPException(status_code=404, detail="Camera ID phải là 1 hoặc 2.")
    try:
        mode = state.start_camera(
            cam_id, req.device_index, prefer_browser=req.prefer_browser
        )
        return {
            "status": "started",
            "cam_id": cam_id,
            "mode": mode,
            "device_index": state.cams[cam_id].device_index,
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/camera/{cam_id}/stop")
def api_stop_single_camera(cam_id: int):
    if cam_id not in (1, 2):
        raise HTTPException(status_code=404, detail="Camera ID phải là 1 hoặc 2.")
    state.stop_camera(cam_id)
    return {"status": "stopped", "cam_id": cam_id}


@app.post("/api/camera/start")
def api_start_cameras(req: StartDualCameraRequest):
    try:
        mode1 = state.start_camera(
            1, req.cam1_index, prefer_browser=req.prefer_browser
        )
        mode2 = state.start_camera(
            2, req.cam2_index, prefer_browser=req.prefer_browser
        )
        return {
            "status": "started",
            "mode": "browser" if "browser" in (mode1, mode2) else "local",
            "cam1_index": state.cams[1].device_index,
            "cam2_index": state.cams[2].device_index,
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/camera/browser-frame")
def api_browser_frame(req: BrowserDualFrameRequest):
    return state.ingest_browser_frames(req.cam1_image, req.cam2_image)


@app.post("/api/camera/stop")
def api_stop_cameras():
    state.stop_cameras()
    return {"status": "stopped"}


@app.get("/api/camera/stream/{cam_id}")
def stream_camera_by_id(cam_id: int):
    if cam_id not in (1, 2):
        raise HTTPException(status_code=404, detail="Camera ID phải là 1 hoặc 2.")

    def generate():
        last_seq = -1
        while True:
            with state.lock:
                cam = state.cams[cam_id]
                if not cam.active:
                    break
                seq = cam.jpeg_seq
                jpeg_bytes = cam.latest_jpeg

            if jpeg_bytes is not None and seq != last_seq:
                last_seq = seq
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                )
            time.sleep(0.03)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/management/overview")
def get_management_overview(
    q: str = "", status: str = "all", limit: int = HISTORY_LIMIT
):
    limit = max(1, min(limit, 1000))
    pending_snapshot = state.get_pending_snapshot()
    pending_rows = [
        format_record_row("Chờ lưu", rec) for rec in reversed(pending_snapshot)
    ]

    with state.lock:
        ready = state.database_ready

    overview = None
    if ready:
        try:
            overview = state.get_cached_overview(q, status, limit)
        except (DatabaseConfigurationError, DatabaseOperationError) as error:
            state._set_db_status(False, str(error))

    with state.lock:
        return {
            "database_ready": state.database_ready,
            "database_error": state.database_error,
            "stats": overview["stats"] if overview else None,
            "revenue": overview["revenue"] if overview else None,
            "matched": overview["matched"] if overview else 0,
            "records": overview["records"] if overview else [],
            "pending_records": pending_rows,
            "records_version": state.records_version,
        }


@app.post("/api/management/reconnect")
def api_reconnect_database():
    try:
        flushed = state.connect_database()
        return {"status": "ok", "flushed": flushed}
    except (DatabaseConfigurationError, DatabaseOperationError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/management/flush-pending")
def api_flush_pending():
    try:
        flushed = state.flush_pending()
        return {"status": "flushed" if flushed else "empty", "flushed": flushed}
    except (DatabaseConfigurationError, DatabaseOperationError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    default_host = "0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1"
    default_port = "7860" if os.getenv("SPACE_ID") else "8000"
    host = os.getenv("APP_HOST", default_host)
    port = int(os.getenv("PORT", os.getenv("APP_PORT", default_port)))
    print(f"\n[SYS] Khoi dong He thong Nhan dien Khuon mat & Bien so xe (2 Camera) tai: http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port)

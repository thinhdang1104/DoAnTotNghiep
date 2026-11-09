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

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from ultralytics import YOLO

from database import (
    HISTORY_LIMIT,
    PARKING_FEE_VND,
    DatabaseConfigurationError,
    DatabaseOperationError,
    fetch_overview,
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
VOTE_SAMPLE_INTERVAL_SECONDS = 0.25
VOTE_MIN_SAMPLES = 3
VOTE_MIN_SHARE = 0.70

# Cơ chế "Lưu hờ" (Two-Phase Latch): đợi khuôn mặt chuẩn nhất ở Camera đối diện
FACE_MIN_CONFIDENCE = 0.85
FACE_SAMPLE_WINDOW_SECONDS = 0.50
FACE_RECENT_BUFFER_SECONDS = 1.20
LATCH_TIMEOUT_SECONDS = 15.0

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
PLATE_PATTERNS = (
    re.compile(r"^(\d{2}[A-Z]{1,2}\d?)(\d{5})$"),
    re.compile(r"^(\d{2}[A-Z]{1,2}\d?)(\d{4})$"),
)
TO_DIGIT = {"D": "0", "B": "8", "S": "5", "Z": "2", "G": "6"}
TO_LETTER = {"0": "D", "8": "B", "5": "S", "2": "Z", "6": "G", "4": "A"}


def normalize_plate(raw_text: str) -> tuple[str, str] | None:
    """Trả về (khóa bỏ phiếu, chuỗi hiển thị) hoặc None nếu không giống biển số VN."""
    if not raw_text:
        return None
    upper = raw_text.upper()
    chars = [ch for ch in upper if ch.isalnum()]
    if not 7 <= len(chars) <= 10:
        return None

    for i in (0, 1):
        chars[i] = TO_DIGIT.get(chars[i], chars[i])
    chars[2] = TO_LETTER.get(chars[2], chars[2])
    for i in range(len(chars) - 4, len(chars)):
        chars[i] = TO_DIGIT.get(chars[i], chars[i])
    key = "".join(chars)

    if upper.count("-") == 1:
        split_at = sum(ch.isalnum() for ch in upper.split("-")[0])
        series, number = key[:split_at], key[split_at:]
        if PLATE_SERIES_RE.match(series) and PLATE_NUMBER_RE.match(number):
            return key, f"{series}-{number}"

    for pattern in PLATE_PATTERNS:
        match = pattern.match(key)
        if match:
            return key, f"{match.group(1)}-{match.group(2)}"
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


def detect_plates(frame, plate_model: YOLO, char_model: YOLO, annotated=None):
    results = plate_model.predict(
        frame, conf=CONF_PLATE, iou=0.5, imgsz=640, verbose=False, **_yolo_kwargs()
    )[0]
    names = char_model.names
    height, width = frame.shape[:2]
    plate_reads: list[str] = []
    plate_boxes: list[dict] = []

    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x1 >= x2 or y1 >= y2:
            continue

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
        plate_reads.append(raw_text)

        normalized = normalize_plate(raw_text)
        label = normalized[1] if normalized else (raw_text or "?")
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

    return plate_reads, plate_boxes


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


def _face_score(face: FaceData) -> float:
    return face.confidence * math.sqrt(face.area)


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
        self.last_sample_time = 0.0
        self.last_plate_seen: float | None = None
        # Lưu các khuôn mặt chuẩn gần nhất (now, score, confidence, frame, box)
        self.recent_faces: deque = deque()


# ============================================================================
# Trạng thái hệ thống 2 Camera độc lập (Cam 1 · Phía trong + Cam 2 · Phía ngoài)
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
        self.write_queue: queue.Queue = queue.Queue()
        self.writer_stop = threading.Event()
        self.writer_thread: threading.Thread | None = None

        # Hai camera độc lập (bật/tắt riêng từng camera):
        # - Cam 1 (Phía trong): Soi Khuôn mặt chiều VÀO / Biển số chiều RA
        # - Cam 2 (Phía ngoài): Soi Biển số chiều VÀO / Khuôn mặt chiều RA
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
        }

    def _reset_session_state_locked(self) -> None:
        for cam in self.cams.values():
            cam.reset_tracking()
        # recent_confirms lưu thời điểm hết hạn khóa: token -> expire_monotonic_time
        self.recent_confirms: dict[str, float] = {}
        # Trạng thái Lưu hờ (Two-Phase Latch)
        self.latched: dict | None = None
        self.face_window_start: float | None = None
        self.best_face: tuple[float, float, object, tuple] | None = None

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
                    return
                except (DatabaseConfigurationError, DatabaseOperationError) as error:
                    self._set_db_status(False, str(error))

            if str(record.get("direction", "IN")).upper() == "OUT":
                for pending_rec in self.pending_records:
                    if (
                        pending_rec.get("plate_number") == record.get("plate_number")
                        and pending_rec.get("direction") == "IN"
                        and pending_rec.get("parking_status") == "IN_PARKING"
                    ):
                        pending_rec["parking_status"] = "COMPLETED"

            self.pending_records.append(record)
            self._persist_pending()
            self._bump_version()

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
            self.latched = None
            self.face_window_start = None
            self.best_face = None
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
                    f"Bảo vệ đã cho phép xe {record_to_save['plate_number']} "
                    "ra bãi (ngoại lệ lệch khuôn mặt).",
                )
            else:
                # Khi TỪ CHỐI: xóa cooldown của biển số này để chủ xe thật có thể quét lại ngay
                if plate_key:
                    self.recent_confirms.pop(f"{plate_key}:OUT", None)
                for cam in self.cams.values():
                    cam.observations.clear()
                self._set_feedback_locked(
                    "error",
                    f"Đã TỪ CHỐI cho xe {alert['record']['plate_number']} ra bãi "
                    "— Xe vẫn giữ trạng thái Đang gửi trong bãi.",
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
                shared_grabber = (
                    other.grabber
                    if other.active
                    and other.mode == "local"
                    and other.device_index == device_index
                    else None
                )
                shared_backend = other.backend_name

            use_browser = prefer_browser or os.getenv("SPACE_ID") is not None
            grabber = None
            backend = "WebRTC (trình duyệt)"

            if not use_browser:
                if shared_grabber is not None:
                    # Cổng này đang được camera còn lại dùng -> dùng chung luồng hình
                    grabber = shared_grabber
                    backend = shared_backend
                else:
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
        if grabber is not None and other.grabber is grabber:
            return None  # camera còn lại vẫn đang dùng chung luồng hình này
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
        if not data_str:
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
            if cam1_b64 and not self.cams[1].active:
                self.cams[1].active = True
                self.cams[1].mode = "browser"
                self.cams[1].backend_name = "WebRTC (trình duyệt)"
                self._refresh_running_locked()
            if cam2_b64 and not self.cams[2].active:
                self.cams[2].active = True
                self.cams[2].mode = "browser"
                self.cams[2].backend_name = "WebRTC (trình duyệt)"
                self._refresh_running_locked()
            b1 = self.cams[1].active and self.cams[1].mode == "browser"
            b2 = self.cams[2].active and self.cams[2].mode == "browser"
            if not (b1 or b2):
                return {"active": False}
            session_id = self.session_id

        frame1 = self._decode_b64_frame(cam1_b64) if b1 else None
        if b2 and cam2_b64 and cam2_b64 == cam1_b64 and frame1 is not None:
            frame2 = frame1
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
                    if g2 is g1:
                        frame2 = frame1
                    else:
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
        cam_id: int,
        frame,
        run_face_idle: bool,
        is_required_face_cam: bool,
        encode_jpeg: bool = True,
    ):
        annotated = frame.copy() if encode_jpeg else None
        if self.plate_model is not None and self.char_model is not None:
            plate_reads, plate_boxes = detect_plates(
                frame, self.plate_model, self.char_model, annotated
            )
        else:
            plate_reads, plate_boxes = [], []
        plate_present = bool(plate_reads)

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

        readings: dict[str, str] = {}
        for raw in plate_reads:
            normalized = normalize_plate(raw)
            if normalized:
                readings[normalized[0]] = normalized[1]

        return plate_present, readings, faces, jpeg_bytes, overlay_boxes

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
            active1 = self.cams[1].active
            active2 = self.cams[2].active

        # Chỉ 1 camera đang bật -> dùng khung hình của camera đó cho cả 2 vai trò (Biển số + Khuôn mặt)
        if active1 and not active2 and frame1 is not None:
            frame2 = frame1
        elif active2 and not active1 and frame2 is not None:
            frame1 = frame2

        run_face_idle = current_frame_idx % FACE_IDLE_EVERY_N_FRAMES == 0
        same_feed = frame1 is not None and frame1 is frame2

        if same_feed:
            res1 = self._analyze_single_cam_frame(
                1,
                frame1,
                run_face_idle,
                required_face_cam in (1, 2),
                encode_jpeg=encode_jpeg,
            )
            res2 = res1
        else:
            res1 = (
                self._analyze_single_cam_frame(
                    1,
                    frame1,
                    run_face_idle,
                    required_face_cam == 1,
                    encode_jpeg=encode_jpeg,
                )
                if frame1 is not None
                else None
            )
            res2 = (
                self._analyze_single_cam_frame(
                    2,
                    frame2,
                    run_face_idle,
                    required_face_cam == 2,
                    encode_jpeg=encode_jpeg,
                )
                if frame2 is not None
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
                plate_present, readings, faces, jpeg_bytes, overlay_boxes = res
                cam = self.cams[cam_id]

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
                    best_in_frame = max(valid_faces, key=_face_score)
                    cam.recent_faces.append(
                        (
                            now,
                            _face_score(best_in_frame),
                            best_in_frame.confidence,
                            raw_frame,
                            best_in_frame.box,
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

            # ------------------------------------------------------------------
            # Xử lý máy trạng thái 2 Pha (Lưu hờ Biển số -> Chốt Khuôn mặt Cam đối diện)
            #   - Cam 2 (Phía ngoài) chốt Biển số => Luồng ĐI VÀO (IN), lấy mặt ở Cam 1
            #   - Cam 1 (Phía trong) chốt Biển số => Luồng ĐI RA  (OUT), lấy mặt ở Cam 2
            # ------------------------------------------------------------------
            if self.security_alert is None:
                if self.latched is None:
                    shared_cam_mode = same_feed
                    scan_order = [(2, "IN", 1), (1, "OUT", 2)]
                    if shared_cam_mode:
                        v_check = get_vote_result(self.cams[2].observations) or get_vote_result(
                            self.cams[1].observations
                        )
                        if is_vote_confirmed(v_check):
                            _, cand_display, _, _, _ = v_check
                            if self._is_plate_currently_in_parking(cand_display):
                                scan_order = [(1, "OUT", 2), (2, "IN", 1)]

                    # Kiểm tra lần lượt theo thứ tự ưu tiên
                    for plate_cam_id, direction, target_face_cam_id in scan_order:
                        cam = self.cams[plate_cam_id]
                        vote = get_vote_result(cam.observations)
                        if not is_vote_confirmed(vote):
                            continue

                        key, display, vote_count, vote_share, sample_count = vote
                        cooldown_token = f"{key}:{direction}"
                        if cooldown_token in self.recent_confirms:
                            cam.observations.clear()
                            continue

                        self.latched = {
                            "direction": direction,
                            "plate_key": key,
                            "plate_number": display,
                            "vote_count": vote_count,
                            "sample_count": sample_count,
                            "consensus_rate": round(vote_share, 4),
                            "plate_cam": plate_cam_id,
                            "required_face_cam": target_face_cam_id,
                            "latched_at": now,
                        }
                        self.face_window_start = None
                        self.best_face = None
                        cam.observations.clear()
                        if shared_cam_mode:
                            self.cams[target_face_cam_id].observations.clear()

                        # Nếu trên Camera đối diện đã có sẵn khuôn mặt chuẩn vừa bắt được đồng thời,
                        # nạp ngay vào cửa sổ lấy mẫu để chốt cực nhanh
                        opp_cam = self.cams[target_face_cam_id]
                        if opp_cam.recent_faces:
                            best_recent = max(opp_cam.recent_faces, key=lambda item: item[1])
                            self.face_window_start = best_recent[0]
                            self.best_face = (
                                best_recent[1],
                                best_recent[2],
                                best_recent[3],
                                best_recent[4],
                            )
                        break

                if self.latched is not None:
                    elapsed_latch = now - self.latched["latched_at"]
                    if elapsed_latch > LATCH_TIMEOUT_SECONDS:
                        self._set_feedback_locked(
                            "warn",
                            f"Đã hủy lưu hờ biển số {self.latched['plate_number']} "
                            f"(Cam {self.latched['plate_cam']}) do không thấy khuôn mặt ở Cam {self.latched['required_face_cam']}.",
                        )
                        self.latched = None
                        self.face_window_start = None
                        self.best_face = None
                    else:
                        req_cam_id = self.latched["required_face_cam"]
                        req_cam = self.cams[req_cam_id]
                        if req_cam.recent_faces:
                            latest_face = req_cam.recent_faces[-1]
                            if self.face_window_start is None:
                                self.face_window_start = latest_face[0]
                            for _, f_score, f_conf, f_frame, f_box in req_cam.recent_faces:
                                if self.best_face is None or f_score > self.best_face[0]:
                                    self.best_face = (f_score, f_conf, f_frame, f_box)

                        if (
                            self.best_face is not None
                            and self.face_window_start is not None
                            and now - self.face_window_start >= FACE_SAMPLE_WINDOW_SECONDS
                        ):
                            latched_info = self.latched
                            best_face = self.best_face
                            self.confirm_seq += 1

                            commit_pair = (
                                {
                                    "_seq": self.confirm_seq,
                                    "_plate_key": latched_info["plate_key"],
                                    "plate_number": latched_info["plate_number"],
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
                            self.latched = None
                            self.face_window_start = None
                            self.best_face = None
                            req_cam.recent_faces.clear()

            self.frame_count += 1

        if commit_pair is not None:
            self._commit_latched_pair(*commit_pair)

    def _is_plate_currently_in_parking(self, plate_number: str) -> bool:
        if self._find_pending_active_session(plate_number) is not None:
            return True
        if self.database_ready:
            try:
                check = verify_checkout_face(plate_number, None)
                return bool(check and check.get("has_active_session"))
            except Exception:
                return False
        return False

    def _find_pending_active_session(self, plate_number: str) -> dict | None:
        with self.db_write_lock:
            for rec in reversed(self.pending_records):
                if (
                    rec.get("plate_number") == plate_number
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
        """Trích xuất vector 512 chiều của Khuôn mặt chuẩn nhất và:
        - Nếu là chiều VÀO ('IN'): Lưu đồng thời (Biển số Cam 2 + Khuôn mặt Cam 1 + VÀO) vào MySQL.
        - Nếu là chiều RA ('OUT'): Đối chiếu Cosine giữa Khuôn mặt Cam 2 với lượt VÀO;
          nếu Khớp >= 45% thì ghi vào MySQL, nếu Lệch < 45% thì bật Cảnh báo an ninh."""
        plate_key = record.pop("_plate_key", "")
        embedding = None
        if best_face is not None and self.face_service is not None:
            try:
                embedding = self.face_service.embed_face(best_face[2], best_face[3])
            except Exception as error:  # noqa: BLE001
                print(f"[WARN] Không trích xuất được vector khuôn mặt: {error}")
        record["face_embedding"] = embedding

        direction = record["direction"]
        plate = record["plate_number"]
        now = time.monotonic()

        if direction == "OUT":
            check = None
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
                    if plate_key:
                        self._lock_plate_cooldown_locked(plate_key, "OUT", now)
                    self._set_feedback_locked(
                        "success",
                        f"RA BÃI THÀNH CÔNG: Xe {plate} (Cam 1) — Khớp khuôn mặt tại Cam 2 "
                        f"({score_pct}). Đã mở cổng cho xe ra!",
                    )
            else:
                with self.lock:
                    if plate_key:
                        self._lock_plate_cooldown_locked(plate_key, "OUT", now)
                    self._set_feedback_locked(
                        "warn",
                        f"Đã ghi nhận xe {plate} RA BÃI (không tìm thấy phiên gửi vào trước đó).",
                    )
        else:
            with self.lock:
                if plate_key:
                    self._lock_plate_cooldown_locked(plate_key, "IN", now)
                self._set_feedback_locked(
                    "success",
                    f"VÀO BÃI THÀNH CÔNG: Đã lưu đồng thời Biển số {plate} (Cam 2) "
                    f"+ Khuôn mặt ({record['face_confidence']:.0%}, Cam 1) vào MySQL!",
                )

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


state = SystemState()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state.load_pending_from_disk()
    try:
        flushed = state.connect_database()
        if flushed:
            print(f"[DB] Đã đồng bộ {flushed} bản ghi chờ từ lần chạy trước.")
    except (DatabaseConfigurationError, DatabaseOperationError) as error:
        print(f"[WARN] Chưa kết nối được MySQL, bản ghi sẽ được lưu tạm: {error}")
    state.start_db_writer()
    # Tải mô hình AI trong luồng nền để cổng HTTP 7860 mở ngay lập tức (tránh timeout trên Cloud)
    threading.Thread(target=state.load_ai_models, daemon=True).start()
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
    cam1_index: int = 0
    cam2_index: int = 1
    prefer_browser: bool = False


class StartSingleCameraRequest(BaseModel):
    device_index: int = 0
    prefer_browser: bool = False


class BrowserDualFrameRequest(BaseModel):
    cam1_image: str | None = None
    cam2_image: str | None = None


class ResolveAlertRequest(BaseModel):
    action: str


NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate"}


@app.api_route("/", methods=["GET", "HEAD"])
@app.api_route("/ui", methods=["GET", "HEAD"])
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"), headers=NO_CACHE_HEADERS)


@app.get("/styles.css")
def serve_styles():
    return FileResponse(str(FRONTEND_DIR / "styles.css"), headers=NO_CACHE_HEADERS)


@app.get("/app.js")
def serve_app_js():
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
    pending_count = state.get_pending_count()
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
            overview = fetch_overview(q, status, limit)
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

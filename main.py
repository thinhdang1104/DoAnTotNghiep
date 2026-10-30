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
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from ultralytics import YOLO

from database import (
    HISTORY_LIMIT,
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

# Bỏ phiếu đồng thuận biển số
VOTE_WINDOW_SECONDS = 3.0
VOTE_SAMPLE_INTERVAL_SECONDS = 0.25
VOTE_MIN_SAMPLES = 3
VOTE_MIN_SHARE = 0.70

# Cơ chế "Lưu hờ" (Two-Phase Latch): đợi khuôn mặt chuẩn nhất ở Camera đối diện
FACE_MIN_CONFIDENCE = 0.85
FACE_SAMPLE_WINDOW_SECONDS = 0.50
LATCH_TIMEOUT_SECONDS = 25.0

# Không còn thấy khung biển số nào trong khoảng này => reset bộ đếm phiếu
PLATE_LOST_RESET_SECONDS = 1.5
# Cùng một biển số + cùng một luồng (IN/OUT) không ghi trùng trong khoảng này
PLATE_COOLDOWN_SECONDS = 20.0
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


def detect_plates(frame, plate_model: YOLO, char_model: YOLO, annotated):
    results = plate_model.predict(frame, conf=CONF_PLATE, iou=0.5, verbose=False)[0]
    names = char_model.names
    height, width = frame.shape[:2]
    plate_reads: list[str] = []

    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x1 >= x2 or y1 >= y2:
            continue

        crop = frame[y1:y2, x1:x2]
        char_res = char_model.predict(
            crop, conf=CONF_CHAR, iou=0.5, imgsz=640, verbose=False
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
        color = (0, 200, 0) if normalized else (0, 165, 255)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
        for _, _, _, _, (cx1, cy1, cx2, cy2) in chars:
            cv2.rectangle(
                annotated, (x1 + cx1, y1 + cy1), (x1 + cx2, y1 + cy2), (255, 0, 0), 1
            )
        label = normalized[1] if normalized else (raw_text or "?")
        cv2.putText(
            annotated,
            label,
            (x1, min(height - 5, y2 + 30)),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 255),
            2,
        )

    return plate_reads


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


def resize_camera_preview(frame, max_width: int = 1000, max_height: int = 640):
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
    MAX_CONSECUTIVE_FAILURES = 20

    def __init__(self, capture, first_frame) -> None:
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

    def next_frame(self, last_seq: int, timeout: float):
        with self._cond:
            self._cond.wait_for(
                lambda: self._seq != last_seq or self.failed or self._stopped, timeout
            )
            if self._seq == last_seq:
                return None, last_seq
            return self._frame, self._seq

    def stop(self) -> None:
        with self._cond:
            self._stopped = True
            self._cond.notify_all()
        self._thread.join(timeout=2.0)


# ============================================================================
# Trạng thái hệ thống
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

        # Camera & Active Cam Switcher (Giải pháp 1: 1 điện thoại đóng vai Cam 1 / Cam 2)
        # Mặc định bắt đầu ở Cam 2 (soi biển số xe ĐI VÀO)
        self.running = False
        self.session_id = 0
        self.device_index = 0
        self.backend_name: str | None = None
        self.active_cam: int = 2
        self.auto_switch_cam: bool = True

        self.worker_thread: threading.Thread | None = None
        self.latest_jpeg: bytes | None = None
        self.jpeg_seq = 0
        self.frame_count = 0
        self.current_plates: list[str] = []
        self.plate_in_view = False
        self.current_faces: list[float] = []
        self.ambiguous_frame = False
        self.camera_error: str | None = None
        self.last_confirmed: dict | None = None
        self.confirm_seq = 0

        # Thông báo kết quả cổng & cảnh báo an ninh khi lệch mặt lúc ra
        self.gate_feedback: dict | None = None
        self.security_alert: dict | None = None

        self._reset_vote_state_locked()

    def load_ai_models(self) -> None:
        if not PLATE_MODEL_PATH.is_file():
            raise RuntimeError(f"Không tìm thấy model biển số: {PLATE_MODEL_PATH}")
        if not CHAR_MODEL_PATH.is_file():
            raise RuntimeError(f"Không tìm thấy model ký tự: {CHAR_MODEL_PATH}")
        self.plate_model = YOLO(str(PLATE_MODEL_PATH))
        self.char_model = YOLO(str(CHAR_MODEL_PATH))
        self.face_service = FaceService()

    def _reset_vote_state_locked(self) -> None:
        self.observations: deque = deque()
        self.last_sample_time = 0.0
        self.last_plate_seen: float | None = None
        self.recent_confirms: dict[str, float] = {}
        # Trạng thái Lưu hờ (Two-Phase Latch)
        self.latched: dict | None = None
        self.face_window_start: float | None = None
        self.best_face: tuple[float, float, object, tuple] | None = None

    # ---------------------------------------------------------- hàng chờ (file)
    def load_pending_from_disk(self) -> None:
        if not PENDING_FILE.is_file():
            return
        try:
            items = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
            for item in items:
                item["recognized_at"] = datetime.fromisoformat(item["recognized_at"])
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

            # Nếu mất MySQL mà là lượt RA, cập nhật luôn phiên IN_PARKING trong pending_records nếu có
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

    # ------------------------------------------------- Active Cam & Latch APIs
    def switch_active_cam(
        self, active_cam: int | None = None, auto_switch: bool | None = None
    ) -> dict:
        with self.lock:
            if active_cam in (1, 2):
                if self.active_cam != active_cam:
                    self.active_cam = active_cam
                    self.observations.clear()
            if auto_switch is not None:
                self.auto_switch_cam = bool(auto_switch)
            return {
                "active_cam": self.active_cam,
                "auto_switch_cam": self.auto_switch_cam,
            }

    def cancel_latch(self) -> None:
        with self.lock:
            self.latched = None
            self.face_window_start = None
            self.best_face = None
            self.observations.clear()

    def resolve_security_alert(self, approve: bool) -> dict:
        record_to_save = None
        with self.lock:
            alert = self.security_alert
            if alert is None:
                return {"status": "none"}
            self.security_alert = None
            if approve:
                record_to_save = alert["record"]
                self.gate_feedback = {
                    "type": "warn",
                    "message": (
                        f"Bảo vệ đã cho phép xe {record_to_save['plate_number']} "
                        "ra bãi (ngoại lệ lệch khuôn mặt)."
                    ),
                }
            else:
                self.gate_feedback = {
                    "type": "error",
                    "message": (
                        f"Đã TỪ CHỐI cho xe {alert['record']['plate_number']} ra bãi "
                        "— Xe vẫn giữ trạng thái Đang gửi trong bãi."
                    ),
                }

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

    # ---------------------------------------------------------------- camera
    def start_camera(self, device_index: int) -> None:
        with self.control_lock:
            with self.lock:
                if self.running:
                    return

            capture, first_frame, backend_name, errors = open_camera(device_index)
            if capture is None:
                msg = (
                    f"Không mở/đọc được camera cổng {device_index}. "
                    f"Chi tiết: {'; '.join(errors)}. "
                    "Mở DroidCam Client và kết nối điện thoại trước; kiểm tra "
                    "Windows Settings > Privacy & security > Camera, đóng "
                    "ứng dụng khác đang dùng camera, rồi thử Dò cổng."
                )
                with self.lock:
                    self.camera_error = msg
                raise ValueError(msg)

            grabber = FrameGrabber(capture, first_frame)
            with self.lock:
                self.session_id += 1
                session_id = self.session_id
                self.device_index = device_index
                self.backend_name = backend_name
                self.running = True
                self.camera_error = None
                self.frame_count = 0
                self.latest_jpeg = None
                self.current_plates = []
                self.plate_in_view = False
                self.current_faces = []
                self.ambiguous_frame = False
                self.security_alert = None
                self._reset_vote_state_locked()

            self.worker_thread = threading.Thread(
                target=self._camera_loop, args=(session_id, grabber), daemon=True
            )
            self.worker_thread.start()

    def stop_camera(self) -> None:
        with self.control_lock:
            with self.lock:
                self.running = False
                self.session_id += 1
                worker = self.worker_thread
                self.worker_thread = None

            if worker is not None and worker.is_alive():
                worker.join(timeout=CAMERA_STOP_TIMEOUT_SECONDS)

            with self.lock:
                self.latest_jpeg = None
                self.current_plates = []
                self.plate_in_view = False
                self.current_faces = []
                self.ambiguous_frame = False
                self._reset_vote_state_locked()

    def _end_session_with_error(self, session_id: int, message: str) -> None:
        with self.lock:
            if self.session_id == session_id:
                self.running = False
                self.camera_error = message

    def _camera_loop(self, session_id: int, grabber: FrameGrabber) -> None:
        last_seq = 0
        try:
            while True:
                with self.lock:
                    if not self.running or self.session_id != session_id:
                        return

                frame, last_seq = grabber.next_frame(last_seq, timeout=2.0)
                if frame is None:
                    if grabber.failed:
                        self._end_session_with_error(
                            session_id,
                            "Camera bị ngắt tín hiệu hình ảnh. Kiểm tra kết nối "
                            "DroidCam / USB rồi bấm Kết nối camera lại.",
                        )
                        return
                    continue

                try:
                    self._process_frame(session_id, frame)
                except Exception as error:  # noqa: BLE001
                    self._end_session_with_error(
                        session_id, f"Lỗi xử lý AI trên khung hình: {error}"
                    )
                    return
        finally:
            grabber.stop()

    def _process_frame(self, session_id: int, frame) -> None:
        annotated = frame.copy()
        plate_reads = detect_plates(frame, self.plate_model, self.char_model, annotated)
        plate_present = bool(plate_reads)

        faces: list[FaceData] = []
        if self.face_service is not None and (
            plate_present
            or self.latched is not None
            or self.frame_count % FACE_IDLE_EVERY_N_FRAMES == 0
        ):
            faces = self.face_service.detect_from_bgr(frame)
            draw_faces(annotated, faces)

        ok_enc, buffer = cv2.imencode(
            ".jpg", resize_camera_preview(annotated), [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        )

        readings: dict[str, str] = {}
        for raw in plate_reads:
            normalized = normalize_plate(raw)
            if normalized:
                readings[normalized[0]] = normalized[1]

        now = time.monotonic()
        commit_pair = None

        with self.lock:
            if self.session_id != session_id:
                return

            while self.observations and now - self.observations[0][0] > VOTE_WINDOW_SECONDS:
                self.observations.popleft()
            self.recent_confirms = {
                k: t
                for k, t in self.recent_confirms.items()
                if now - t < PLATE_COOLDOWN_SECONDS
            }

            if plate_present:
                self.last_plate_seen = now
            elif (
                self.last_plate_seen is not None
                and now - self.last_plate_seen >= PLATE_LOST_RESET_SECONDS
            ):
                self.observations.clear()
                self.last_plate_seen = None

            # Nếu đang có cảnh báo an ninh chờ bảo vệ quyết định thì tạm dừng chốt lượt mới
            if self.security_alert is None:
                # --------------------------------------------------------------
                # PHA 1: Chưa có biển số Lưu hờ -> Đọc và bỏ phiếu Biển số
                #   - Cam 2 thấy Biển số => Luồng ĐI VÀO (đợi Khuôn mặt ở Cam 1)
                #   - Cam 1 thấy Biển số => Luồng ĐI RA  (đợi Khuôn mặt ở Cam 2)
                # --------------------------------------------------------------
                if self.latched is None:
                    if (
                        len(readings) == 1
                        and now - self.last_sample_time >= VOTE_SAMPLE_INTERVAL_SECONDS
                    ):
                        key, display = next(iter(readings.items()))
                        self.observations.append((now, key, display))
                        self.last_sample_time = now

                    vote = get_vote_result(self.observations)
                    if is_vote_confirmed(vote):
                        key, display, vote_count, vote_share, sample_count = vote
                        direction = "IN" if self.active_cam == 2 else "OUT"
                        cooldown_token = f"{key}:{direction}"

                        if cooldown_token in self.recent_confirms:
                            self.observations.clear()
                        else:
                            plate_cam = self.active_cam
                            required_face_cam = 1 if direction == "IN" else 2
                            self.latched = {
                                "direction": direction,
                                "plate_key": key,
                                "plate_number": display,
                                "vote_count": vote_count,
                                "sample_count": sample_count,
                                "consensus_rate": round(vote_share, 4),
                                "plate_cam": plate_cam,
                                "required_face_cam": required_face_cam,
                                "latched_at": now,
                            }
                            self.face_window_start = None
                            self.best_face = None
                            self.observations.clear()
                            # Chế độ 1 điện thoại đóng vai 2 Cam: tự động chuyển sang Cam đối diện để đón khuôn mặt
                            if self.auto_switch_cam:
                                self.active_cam = required_face_cam

                # --------------------------------------------------------------
                # PHA 2: Đã Lưu hờ Biển số -> Đợi Khuôn mặt chuẩn nhất ở Cam đối diện
                # --------------------------------------------------------------
                else:
                    elapsed_latch = now - self.latched["latched_at"]
                    if elapsed_latch > LATCH_TIMEOUT_SECONDS:
                        self.gate_feedback = {
                            "type": "warn",
                            "message": (
                                f"Đã hủy lưu hờ biển số {self.latched['plate_number']} "
                                "do quá thời gian chờ khuôn mặt."
                            ),
                        }
                        self.latched = None
                        self.face_window_start = None
                        self.best_face = None
                    elif self.active_cam == self.latched["required_face_cam"]:
                        valid_faces = [
                            f for f in faces if f.confidence >= FACE_MIN_CONFIDENCE
                        ]
                        if valid_faces:
                            candidate = max(valid_faces, key=_face_score)
                            score = _face_score(candidate)
                            if self.face_window_start is None:
                                self.face_window_start = now
                            if self.best_face is None or score > self.best_face[0]:
                                self.best_face = (
                                    score,
                                    candidate.confidence,
                                    frame,
                                    candidate.box,
                                )

                        if (
                            self.best_face is not None
                            and self.face_window_start is not None
                            and now - self.face_window_start
                            >= FACE_SAMPLE_WINDOW_SECONDS
                        ):
                            latched_info = self.latched
                            best_face = self.best_face
                            self.confirm_seq += 1
                            cooldown_token = (
                                f"{latched_info['plate_key']}:{latched_info['direction']}"
                            )
                            self.recent_confirms[cooldown_token] = now

                            commit_pair = (
                                {
                                    "_seq": self.confirm_seq,
                                    "plate_number": latched_info["plate_number"],
                                    "direction": latched_info["direction"],
                                    "parking_status": (
                                        "IN_PARKING"
                                        if latched_info["direction"] == "IN"
                                        else "EXITED"
                                    ),
                                    "recognized_at": datetime.now().replace(
                                        microsecond=0
                                    ),
                                    "vote_count": latched_info["vote_count"],
                                    "sample_count": latched_info["sample_count"],
                                    "consensus_rate": latched_info["consensus_rate"],
                                    "face_detected": True,
                                    "face_confidence": best_face[1],
                                    "camera_index": self.device_index,
                                },
                                best_face,
                            )
                            self.latched = None
                            self.face_window_start = None
                            self.best_face = None

            self.ambiguous_frame = len(readings) > 1
            self.plate_in_view = plate_present
            self.current_plates = list(readings.values())
            self.current_faces = [f.confidence for f in faces]
            self.frame_count += 1
            if ok_enc:
                self.latest_jpeg = buffer.tobytes()
                self.jpeg_seq += 1

        if commit_pair is not None:
            self._commit_latched_pair(*commit_pair)

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
        - Nếu là chiều VÀO ('IN'): Lưu đồng thời (Biển số + Khuôn mặt + VÀO) vào MySQL.
        - Nếu là chiều RA ('OUT'): Đối chiếu Cosine với lượt VÀO; nếu Khớp >= 45% thì ghi vào MySQL,
          nếu Lệch < 45% thì bật Cảnh báo an ninh chờ bảo vệ quyết định."""
        embedding = None
        if best_face is not None and self.face_service is not None:
            try:
                embedding = self.face_service.embed_face(best_face[2], best_face[3])
            except Exception as error:  # noqa: BLE001
                print(f"[WARN] Không trích xuất được vector khuôn mặt: {error}")
        record["face_embedding"] = embedding

        direction = record["direction"]
        plate = record["plate_number"]

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
                    with self.lock:
                        self.security_alert = {
                            "plate_number": plate,
                            "entry_time": check.get("entry_time") or "-",
                            "match_score_pct": score_pct,
                            "face_confidence_pct": f"{record['face_confidence']:.0%}",
                            "record": record,
                        }
                    return

                with self.lock:
                    self.gate_feedback = {
                        "type": "success",
                        "message": (
                            f"RA BÃI THÀNH CÔNG: Xe {plate} — Khớp khuôn mặt người gửi "
                            f"({score_pct}). Đã mở cổng cho xe ra!"
                        ),
                    }
            else:
                with self.lock:
                    self.gate_feedback = {
                        "type": "warn",
                        "message": (
                            f"Đã ghi nhận xe {plate} RA BÃI (không tìm thấy phiên gửi vào trước đó)."
                        ),
                    }
        else:
            with self.lock:
                self.gate_feedback = {
                    "type": "success",
                    "message": (
                        f"VÀO BÃI THÀNH CÔNG: Đã lưu đồng thời Biển số {plate} "
                        f"+ Khuôn mặt ({record['face_confidence']:.0%}) vào MySQL!"
                    ),
                }

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
    state.load_ai_models()
    state.load_pending_from_disk()
    try:
        flushed = state.connect_database()
        if flushed:
            print(f"[DB] Đã đồng bộ {flushed} bản ghi chờ từ lần chạy trước.")
    except (DatabaseConfigurationError, DatabaseOperationError) as error:
        print(f"[WARN] Chưa kết nối được MySQL, bản ghi sẽ được lưu tạm: {error}")
    state.start_db_writer()
    try:
        yield
    finally:
        state.stop_camera()
        state.stop_db_writer()


app = FastAPI(
    title="Hệ thống Nhận diện Khuôn mặt & Biển số xe AI",
    lifespan=lifespan,
)


class StartCameraRequest(BaseModel):
    device_index: int = 0


class SwitchCameraRequest(BaseModel):
    active_cam: int | None = None
    auto_switch: bool | None = None


class ResolveAlertRequest(BaseModel):
    action: str


@app.get("/")
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/styles.css")
def serve_styles():
    return FileResponse(str(FRONTEND_DIR / "styles.css"))


@app.get("/app.js")
def serve_app_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"))


@app.get("/api/camera/status")
def get_camera_status():
    now = time.monotonic()
    with state.lock:
        vote_info = None
        vote_res = get_vote_result(state.observations)
        if vote_res is not None:
            _, display, vote_count, vote_share, sample_count = vote_res
            vote_info = {
                "candidate": display,
                "vote_count": vote_count,
                "sample_count": sample_count,
                "vote_share": vote_share,
            }

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
            "device_index": state.device_index,
            "backend": state.backend_name,
            "active_cam": state.active_cam,
            "auto_switch_cam": state.auto_switch_cam,
            "frame_count": state.frame_count,
            "plate_in_view": state.plate_in_view,
            "current_plates": list(state.current_plates),
            "current_faces": list(state.current_faces),
            "vote": vote_info,
            "latched": latched_info,
            "security_alert": alert_info,
            "gate_feedback": state.gate_feedback,
            "ambiguous_frame": state.ambiguous_frame,
            "error": state.camera_error,
            "last_confirmed": state.last_confirmed,
            "records_version": state.records_version,
            "database_ready": state.database_ready,
            "pending_count": len(state.pending_records),
            "face_matching": bool(state.face_service and state.face_service.can_embed),
        }


@app.post("/api/camera/switch")
def api_switch_camera(req: SwitchCameraRequest):
    return state.switch_active_cam(req.active_cam, req.auto_switch)


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
    with state.control_lock:
        with state.lock:
            if state.running:
                raise HTTPException(
                    status_code=400,
                    detail="Vui lòng ngắt camera hiện tại trước khi dò thiết bị.",
                )
        found = []
        for index in range(6):
            test_cap, _, backend_name, _ = open_camera(index)
            if test_cap is not None:
                found.append({"index": index, "backend": backend_name})
                test_cap.release()
        return {"cameras": found}


@app.post("/api/camera/start")
def api_start_camera(req: StartCameraRequest):
    try:
        state.start_camera(req.device_index)
        return {"status": "started", "device_index": req.device_index}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/camera/stop")
def api_stop_camera():
    state.stop_camera()
    return {"status": "stopped"}


@app.get("/api/camera/stream")
def stream_camera():
    def generate():
        last_seq = -1
        while True:
            with state.lock:
                if not state.running:
                    break
                seq = state.jpeg_seq
                jpeg_bytes = state.latest_jpeg

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
    with state.lock:
        ready = state.database_ready
        pending_rows = []
        for rec in reversed(state.pending_records):
            row = format_record_row("Chờ lưu", rec)
            pending_rows.append(row)

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
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    print(f"\n[SYS] Khoi dong He thong Nhan dien Khuon mat & Bien so xe tai: http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port)

import os
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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from ultralytics import YOLO

from database import (
    DatabaseConfigurationError,
    DatabaseOperationError,
    flush_pending_plate_records,
    format_recognition_time,
    initialize_database,
    insert_plate_record,
)
from face_service import FaceData, FaceService


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
PLATE_MODEL_PATH = BASE_DIR / "weights" / "plate_best.pt"
CHAR_MODEL_PATH = BASE_DIR / "weights" / "chars_best.pt"

UNREADABLE_PLATE = "(không đọc được ký tự)"
MIN_PLATE_ALNUM_CHARS = 5
MAX_PLATE_ALNUM_CHARS = 12
MAX_HISTORY_RECORDS = 200

CONF_PLATE = 0.40
CONF_CHAR = 0.35

VOTE_WINDOW_SECONDS = 3.0
VOTE_SAMPLE_INTERVAL_SECONDS = 0.25
VOTE_MIN_SAMPLES = 3
VOTE_MIN_SHARE = 0.70
PLATE_LOST_RESET_SECONDS = 1.5

CAMERA_BACKENDS = (
    ("Media Foundation", cv2.CAP_MSMF),
    ("DirectShow", cv2.CAP_DSHOW),
    ("Tự động", cv2.CAP_ANY),
)


def is_readable_plate(text: str) -> bool:
    return bool(text and text != UNREADABLE_PLATE and text.strip())


def is_valid_plate_candidate(text: str) -> bool:
    if not is_readable_plate(text):
        return False
    alnum_count = sum(ch.isalnum() for ch in text)
    return MIN_PLATE_ALNUM_CHARS <= alnum_count <= MAX_PLATE_ALNUM_CHARS


def _box_iou(box_a, box_b) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union_area = area_a + area_b - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


def _deduplicate_chars(raw_chars, iou_threshold: float = 0.55):
    """Loại bỏ các box ký tự trùng lắp tại cùng vị trí, giữ box có confidence cao nhất."""
    sorted_by_conf = sorted(raw_chars, key=lambda item: item[3], reverse=True)
    kept = []
    for candidate in sorted_by_conf:
        candidate_box = candidate[4]
        if any(_box_iou(candidate_box, existing[4]) > iou_threshold for existing in kept):
            continue
        kept.append(candidate)
    return kept


def _assemble_plate_text(chars) -> str:
    """Ghép các ký tự (không rỗng) thành chuỗi biển số, tự động phân biệt biển 1 dòng và 2 dòng."""
    if len(chars) == 1:
        return chars[0][2]

    y_values = [char[1] for char in chars]
    char_heights = [max(1, char[4][3] - char[4][1]) for char in chars]
    avg_char_height = sum(char_heights) / len(char_heights)
    y_range = max(y_values) - min(y_values)

    if y_range < avg_char_height * 0.6:
        sorted_chars = sorted(chars, key=lambda char: char[0])
        return "".join(char[2] for char in sorted_chars)

    threshold = (min(y_values) + max(y_values)) / 2.0
    line_top = sorted(
        (char for char in chars if char[1] < threshold), key=lambda char: char[0]
    )
    line_bottom = sorted(
        (char for char in chars if char[1] >= threshold), key=lambda char: char[0]
    )

    text_top = "".join(char[2] for char in line_top)
    text_bottom = "".join(char[2] for char in line_bottom)
    if text_top and text_bottom:
        return f"{text_top}-{text_bottom}"
    return text_top + text_bottom


def detect_frame(
    frame,
    plate_model: YOLO,
    char_model: YOLO,
    face_service: FaceService | None,
):
    """Nhận diện biển số, ký tự và khuôn mặt trên một khung hình."""
    annotated = frame.copy()
    results = plate_model.predict(
        frame, conf=CONF_PLATE, iou=0.5, verbose=False
    )[0]
    plate_texts: list[str] = []
    names = char_model.names
    height, width = frame.shape[:2]

    for i, box in enumerate(results.boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)

        if x1 >= x2 or y1 >= y2:
            continue

        crop = frame[y1:y2, x1:x2]
        char_res = char_model.predict(
            crop,
            conf=CONF_CHAR,
            iou=0.5,
            imgsz=640,
            verbose=False,
        )[0]

        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(
            annotated,
            f"Plate {i + 1}",
            (x1, max(20, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )

        if len(char_res.boxes) == 0:
            plate_texts.append(UNREADABLE_PLATE)
            continue

        raw_chars = []
        for char_box in char_res.boxes:
            cx1, cy1, cx2, cy2 = map(int, char_box.xyxy[0])
            label = names[int(char_box.cls[0])]
            confidence = float(char_box.conf[0])
            x_center = (cx1 + cx2) / 2.0
            y_center = (cy1 + cy2) / 2.0
            raw_chars.append(
                (x_center, y_center, label, confidence, (cx1, cy1, cx2, cy2))
            )

        chars = _deduplicate_chars(raw_chars)
        plate_text = _assemble_plate_text(chars)
        plate_texts.append(plate_text)

        for _, _, _, _, (cx1, cy1, cx2, cy2) in chars:
            abs_x1, abs_y1 = x1 + cx1, y1 + cy1
            abs_x2, abs_y2 = x1 + cx2, y1 + cy2
            cv2.rectangle(
                annotated,
                (abs_x1, abs_y1),
                (abs_x2, abs_y2),
                (255, 0, 0),
                2,
            )

        cv2.putText(
            annotated,
            plate_text,
            (x1, min(height - 5, y2 + 30)),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 255),
            2,
        )

    faces: list[FaceData] = []
    if face_service is not None:
        faces = face_service.detect_from_bgr(frame, extract_embedding=False)
        for idx, face in enumerate(faces, start=1):
            fx1, fy1, fx2, fy2 = face.box
            cv2.rectangle(annotated, (fx1, fy1), (fx2, fy2), (255, 0, 255), 3)
            cv2.putText(
                annotated,
                f"Face {idx} ({face.confidence:.0%})",
                (fx1, max(20, fy1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 255),
                2,
            )

    return annotated, plate_texts, faces


def resize_camera_preview(frame, max_width: int = 1000, max_height: int = 640):
    height, width = frame.shape[:2]
    scale = min(max_width / width, max_height / height)
    if scale != 1.0:
        frame = cv2.resize(
            frame,
            (round(width * scale), round(height * scale)),
            interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR,
        )
    return frame


def get_vote_result(observations):
    votes = Counter(text for _, text in observations)
    if not votes:
        return None
    candidate, vote_count = votes.most_common(1)[0]
    return candidate, vote_count, vote_count / len(observations), len(observations)


def is_vote_confirmed(vote_result) -> bool:
    if vote_result is None:
        return False
    _, _, vote_share, sample_count = vote_result
    return sample_count >= VOTE_MIN_SAMPLES and vote_share >= VOTE_MIN_SHARE


def format_record_row(record_id, record: dict) -> dict:
    face_detected = record.get("face_detected", False)
    face_conf = record.get("face_confidence")
    if face_detected and face_conf is not None:
        face_label = f"Có ({face_conf:.0%})"
    elif face_detected:
        face_label = "Có"
    else:
        face_label = "Không rõ"

    return {
        "ID": record_id,
        "Biển số": record["plate_number"],
        "Thời gian nhận diện": format_recognition_time(record["recognized_at"]),
        "Đồng thuận biển số": (
            f"{record['vote_count']}/{record['sample_count']} "
            f"({record['consensus_rate']:.0%})"
        ),
        "Khuôn mặt": face_label,
        "Camera index": record["camera_index"],
    }


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


class SystemState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.plate_model: YOLO | None = None
        self.char_model: YOLO | None = None
        self.face_service: FaceService | None = None

        self.database_ready: bool = False
        self.database_error: str | None = None
        self.confirmed_records: list[dict] = []
        self.pending_records: list[dict] = []

        # Camera runtime state
        self.running: bool = False
        self.device_index: int = 0
        self.backend_name: str | None = None
        self.capture: cv2.VideoCapture | None = None
        self.worker_thread: threading.Thread | None = None
        self.latest_jpeg: bytes | None = None
        self.frame_count: int = 0
        self.current_plates: list[str] = []
        self.current_faces: list[float] = []
        self.ambiguous_frame: bool = False
        self.camera_error: str | None = None
        self.last_confirmed: dict | None = None

        # Voting state
        self.observations: deque = deque()
        self.last_sample_time: float = 0.0
        self.last_detection_time: float | None = None
        self.presence_confirmed: bool = False
        self.best_face_conf: float | None = None

    def load_ai_models(self) -> None:
        if not PLATE_MODEL_PATH.is_file():
            raise RuntimeError(f"Không tìm thấy model biển số: {PLATE_MODEL_PATH}")
        if not CHAR_MODEL_PATH.is_file():
            raise RuntimeError(f"Không tìm thấy model ký tự: {CHAR_MODEL_PATH}")
        self.plate_model = YOLO(str(PLATE_MODEL_PATH))
        self.char_model = YOLO(str(CHAR_MODEL_PATH))
        self.face_service = FaceService()

    def init_database(self) -> None:
        try:
            records = initialize_database()
            with self.lock:
                self.confirmed_records = records
                self.database_ready = True
                self.database_error = None
        except (DatabaseConfigurationError, DatabaseOperationError) as error:
            with self.lock:
                self.database_ready = False
                self.database_error = str(error)

    def start_camera(self, device_index: int) -> None:
        with self.lock:
            if self.running:
                return

        capture, first_frame, backend_name, errors = open_camera(device_index)
        if capture is None:
            error_details = "; ".join(errors)
            msg = (
                f"Không mở/đọc được camera index {device_index}. "
                f"Chi tiết backend: {error_details}. "
                "Mở DroidCam Client và kết nối điện thoại trước; kiểm tra "
                "Windows Settings > Privacy & security > Camera, đóng "
                "ứng dụng khác đang dùng camera, rồi thử Dò camera."
            )
            with self.lock:
                self.camera_error = msg
            raise ValueError(msg)

        with self.lock:
            self.capture = capture
            self.device_index = device_index
            self.backend_name = backend_name
            self.running = True
            self.camera_error = None
            self.frame_count = 0
            self.current_plates = []
            self.current_faces = []
            self.ambiguous_frame = False
            self.observations.clear()
            self.last_sample_time = 0.0
            self.last_detection_time = None
            self.presence_confirmed = False
            self.best_face_conf = None

        self.worker_thread = threading.Thread(
            target=self._camera_loop,
            args=(first_frame,),
            daemon=True,
        )
        self.worker_thread.start()

    def stop_camera(self) -> None:
        with self.lock:
            self.running = False
            capture = self.capture
            self.capture = None

        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.5)

        if capture is not None:
            capture.release()

        with self.lock:
            self.latest_jpeg = None
            self.current_plates = []
            self.current_faces = []
            self.ambiguous_frame = False
            self.observations.clear()
            self.last_detection_time = None
            self.presence_confirmed = False
            self.best_face_conf = None

    def _camera_loop(self, initial_frame) -> None:
        frame = initial_frame
        while True:
            with self.lock:
                if not self.running or self.capture is None:
                    break
                capture = self.capture

            if frame is None:
                ok, frame = capture.read()
                if not ok or frame is None:
                    with self.lock:
                        self.running = False
                        self.capture = None
                        self.camera_error = (
                            "Đã kết nối camera nhưng bị ngắt tín hiệu hình ảnh. "
                            "Kiểm tra kết nối DroidCam rồi bấm Bắt đầu lại."
                        )
                    capture.release()
                    break

            annotated, plate_texts, faces = detect_frame(
                frame,
                self.plate_model,
                self.char_model,
                self.face_service,
            )
            frame = None  # Đọc frame mới ở vòng lặp kế tiếp

            preview = resize_camera_preview(annotated)
            ok_enc, buffer = cv2.imencode(
                ".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            )
            jpeg_bytes = buffer.tobytes() if ok_enc else None

            now = time.monotonic()
            valid_texts = {
                text.strip().upper()
                for text in plate_texts
                if is_valid_plate_candidate(text)
            }

            with self.lock:
                while (
                    self.observations
                    and now - self.observations[0][0] > VOTE_WINDOW_SECONDS
                ):
                    self.observations.popleft()

                if valid_texts:
                    self.last_detection_time = now

                    if faces:
                        curr_face_conf = max(f.confidence for f in faces)
                        if (
                            self.best_face_conf is None
                            or curr_face_conf > self.best_face_conf
                        ):
                            self.best_face_conf = curr_face_conf

                    if len(valid_texts) == 1 and not self.presence_confirmed:
                        if (
                            now - self.last_sample_time
                            >= VOTE_SAMPLE_INTERVAL_SECONDS
                        ):
                            self.observations.append((now, next(iter(valid_texts))))
                            self.last_sample_time = now

                        vote_result = get_vote_result(self.observations)
                        if is_vote_confirmed(vote_result):
                            candidate, vote_count, vote_share, sample_count = (
                                vote_result
                            )
                            best_face_conf = self.best_face_conf
                            face_detected = best_face_conf is not None
                            recognized_at = datetime.now().replace(microsecond=0)
                            pending_record = {
                                "plate_number": candidate,
                                "recognized_at": recognized_at,
                                "vote_count": vote_count,
                                "sample_count": sample_count,
                                "consensus_rate": vote_share,
                                "face_detected": face_detected,
                                "face_confidence": best_face_conf,
                                "camera_index": self.device_index,
                            }
                            self._save_confirmed_record_locked(pending_record)
                            self.presence_confirmed = True
                            self.best_face_conf = None
                            self.observations.clear()
                elif (
                    self.last_detection_time is not None
                    and now - self.last_detection_time >= PLATE_LOST_RESET_SECONDS
                ):
                    self.observations.clear()
                    self.best_face_conf = None
                    self.presence_confirmed = False
                    self.last_detection_time = None

                self.ambiguous_frame = len(valid_texts) > 1
                self.current_plates = plate_texts
                self.current_faces = [f.confidence for f in faces]
                self.frame_count += 1
                if jpeg_bytes is not None:
                    self.latest_jpeg = jpeg_bytes

            time.sleep(0.01)

    def _save_confirmed_record_locked(self, pending_record: dict) -> None:
        formatted_preview = format_record_row("Mới", pending_record)
        self.last_confirmed = {
            "plate_number": pending_record["plate_number"],
            "recognized_at": formatted_preview["Thời gian nhận diện"],
            "consensus": formatted_preview["Đồng thuận biển số"],
            "face_status": formatted_preview["Khuôn mặt"],
        }

        if self.database_ready:
            try:
                record_id = insert_plate_record(**pending_record)
                self.confirmed_records.insert(
                    0, format_record_row(record_id, pending_record)
                )
                del self.confirmed_records[MAX_HISTORY_RECORDS:]
                self.database_error = None
            except (DatabaseConfigurationError, DatabaseOperationError) as error:
                self.pending_records.append(pending_record)
                self.database_ready = False
                self.database_error = str(error)
        else:
            self.pending_records.append(pending_record)


state = SystemState()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state.load_ai_models()
    state.init_database()
    try:
        yield
    finally:
        state.stop_camera()


app = FastAPI(
    title="Hệ thống Nhận diện Khuôn mặt & Biển số xe AI",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class StartCameraRequest(BaseModel):
    device_index: int = 0


@app.get("/")
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/styles.css")
def serve_styles():
    return FileResponse(str(FRONTEND_DIR / "styles.css"))


@app.get("/charts.js")
def serve_charts():
    return FileResponse(str(FRONTEND_DIR / "charts.js"))


@app.get("/app.js")
def serve_app_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"))


@app.get("/api/camera/status")
def get_camera_status():
    with state.lock:
        vote_info = None
        vote_res = get_vote_result(state.observations)
        if vote_res is not None:
            candidate, vote_count, vote_share, sample_count = vote_res
            vote_info = {
                "candidate": candidate,
                "vote_count": vote_count,
                "sample_count": sample_count,
                "vote_share": vote_share,
            }

        return {
            "running": state.running,
            "device_index": state.device_index,
            "backend": state.backend_name,
            "frame_count": state.frame_count,
            "current_plates": list(state.current_plates),
            "current_faces": list(state.current_faces),
            "vote": vote_info,
            "ambiguous_frame": state.ambiguous_frame,
            "error": state.camera_error,
            "last_confirmed": state.last_confirmed,
            "database_ready": state.database_ready,
            "pending_count": len(state.pending_records),
        }


@app.post("/api/camera/scan")
def scan_cameras():
    with state.lock:
        if state.running:
            raise HTTPException(
                status_code=400,
                detail="Vui lòng dừng camera hiện tại trước khi dò thiết bị.",
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
        while True:
            with state.lock:
                if not state.running:
                    break
                jpeg_bytes = state.latest_jpeg

            if jpeg_bytes is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                )
            time.sleep(0.04)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/management/overview")
def get_management_overview():
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    with state.lock:
        records = [
            {
                **row,
                "Thời gian nhận diện": format_recognition_time(
                    row["Thời gian nhận diện"]
                ),
            }
            for row in state.confirmed_records
        ]
        pending_formatted = [
            format_record_row("Chờ lưu", rec)
            for rec in reversed(state.pending_records)
        ]
        total = len(records)
        today_count = sum(
            1
            for r in records
            if str(r.get("Thời gian nhận diện", "")).startswith(today_prefix)
        )
        with_face_count = sum(
            1 for r in records if str(r.get("Khuôn mặt", "")).startswith("Có")
        )
        face_rate = round((with_face_count / total) * 100) if total > 0 else 0

        return {
            "database_ready": state.database_ready,
            "database_error": state.database_error,
            "stats": {
                "total_records": total,
                "today_records": today_count,
                "face_rate": face_rate,
                "pending_count": len(state.pending_records),
            },
            "pending_records": pending_formatted,
            "records": records,
        }


@app.post("/api/management/reconnect")
def api_reconnect_database():
    try:
        records = initialize_database()
        with state.lock:
            state.confirmed_records = records
            state.database_ready = True
            state.database_error = None
        return {"status": "ok"}
    except (DatabaseConfigurationError, DatabaseOperationError) as error:
        with state.lock:
            state.database_ready = False
            state.database_error = str(error)
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/management/flush-pending")
def api_flush_pending():
    with state.lock:
        if not state.pending_records:
            return {"status": "empty"}
        try:
            records = flush_pending_plate_records(state.pending_records)
            state.confirmed_records = records
            state.database_ready = True
            state.database_error = None
            return {"status": "flushed"}
        except (DatabaseConfigurationError, DatabaseOperationError) as error:
            state.database_ready = False
            state.database_error = str(error)
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

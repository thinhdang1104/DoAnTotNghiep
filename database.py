import math
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

import mysql.connector
from mysql.connector import Error as MySQLError
from dotenv import load_dotenv

from face_service import (
    FACE_MATCH_THRESHOLD,
    cosine_similarity,
    embedding_from_bytes,
    embedding_to_bytes,
)


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

HISTORY_LIMIT = 200
PARKING_FEE_VND = 2000  # 2.000 VNĐ / lượt giữ xe
SQLITE_DB_PATH = BASE_DIR / "data" / "parking_history.db"
_SQLITE_LOCK = threading.RLock()
_ACTIVE_BACKEND = "mysql"  # "mysql" hoặc "sqlite"


class DatabaseConfigurationError(RuntimeError):
    pass


class DatabaseOperationError(RuntimeError):
    pass


def _should_allow_sqlite_fallback() -> bool:
    """Cho phép tự động chuyển sang SQLite khi chạy trên Hugging Face Spaces hoặc khi bật cờ."""
    if os.getenv("SPACE_ID"):
        return True
    return os.getenv("DB_FALLBACK_SQLITE", "1").strip().lower() in ("1", "true", "yes")


def _connection_config():
    required = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_DATABASE")
    missing = [name for name in required if not os.getenv(name)]
    if os.getenv("MYSQL_PASSWORD") is None:
        missing.append("MYSQL_PASSWORD")
    if missing:
        raise DatabaseConfigurationError(
            "Thiếu cấu hình biến môi trường: " + ", ".join(missing)
        )

    try:
        port = int(os.getenv("MYSQL_PORT", "3306"))
    except ValueError as error:
        raise DatabaseConfigurationError("MYSQL_PORT phải là số nguyên.") from error

    return {
        "host": os.environ["MYSQL_HOST"],
        "port": port,
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "database": os.environ["MYSQL_DATABASE"],
        "connection_timeout": 8,
        "use_pure": True,
    }


def _connect_mysql():
    config = _connection_config()
    try:
        return mysql.connector.connect(**config)
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error


def _connect_sqlite():
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_DB_PATH), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_sqlite_table(conn: sqlite3.Connection) -> None:
    with _SQLITE_LOCK:
        cur = conn.cursor()
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS plate_recognition_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT NOT NULL,
                direction TEXT NOT NULL DEFAULT 'IN',
                parking_status TEXT NOT NULL DEFAULT 'IN_PARKING',
                entry_record_id INTEGER NULL,
                fee_amount INTEGER NOT NULL DEFAULT {PARKING_FEE_VND},
                recognized_at TEXT NOT NULL,
                vote_count INTEGER NOT NULL,
                sample_count INTEGER NOT NULL,
                consensus_rate REAL NOT NULL,
                face_detected INTEGER NOT NULL DEFAULT 0,
                face_confidence REAL NULL,
                face_embedding BLOB NULL,
                face_match_score REAL NULL,
                plate_image TEXT NULL,
                face_image TEXT NULL,
                camera_index INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        cur.execute("PRAGMA table_info(plate_recognition_history)")
        sqlite_cols = {row[1] for row in cur.fetchall()}
        if "plate_image" not in sqlite_cols:
            cur.execute("ALTER TABLE plate_recognition_history ADD COLUMN plate_image TEXT NULL")
        if "face_image" not in sqlite_cols:
            cur.execute("ALTER TABLE plate_recognition_history ADD COLUMN face_image TEXT NULL")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_sqlite_plate_rec ON plate_recognition_history (plate_number, recognized_at)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_sqlite_rec_at ON plate_recognition_history (recognized_at)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_sqlite_plate_status ON plate_recognition_history (plate_number, parking_status)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_sqlite_status_dir ON plate_recognition_history (parking_status, direction)"
        )
        cur.execute(
            "UPDATE plate_recognition_history SET fee_amount = 0 WHERE direction = 'OUT' AND fee_amount <> 0"
        )
        conn.commit()


def _ensure_mysql_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS plate_recognition_history (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            plate_number VARCHAR(32) NOT NULL,
            direction VARCHAR(8) NOT NULL DEFAULT 'IN',
            parking_status VARCHAR(16) NOT NULL DEFAULT 'IN_PARKING',
            entry_record_id BIGINT UNSIGNED NULL,
            fee_amount INT UNSIGNED NOT NULL DEFAULT 2000,
            recognized_at DATETIME NOT NULL,
            vote_count SMALLINT UNSIGNED NOT NULL,
            sample_count SMALLINT UNSIGNED NOT NULL,
            consensus_rate DECIMAL(5, 4) NOT NULL,
            face_detected TINYINT(1) NOT NULL DEFAULT 0,
            face_confidence DECIMAL(5, 4) NULL,
            face_embedding BLOB NULL,
            face_match_score DECIMAL(5, 4) NULL,
            plate_image LONGTEXT NULL,
            face_image LONGTEXT NULL,
            camera_index SMALLINT UNSIGNED NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_plate_recognized_at (plate_number, recognized_at),
            INDEX idx_recognized_at (recognized_at),
            INDEX idx_plate_status (plate_number, parking_status),
            INDEX idx_status_dir (parking_status, direction)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )

    cursor.execute("SHOW COLUMNS FROM plate_recognition_history")
    existing_columns = {
        row["Field"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()
    }
    column_migrations = [
        (
            "direction",
            "ALTER TABLE plate_recognition_history "
            "ADD COLUMN direction VARCHAR(8) NOT NULL DEFAULT 'IN' AFTER plate_number",
        ),
        (
            "parking_status",
            "ALTER TABLE plate_recognition_history "
            "ADD COLUMN parking_status VARCHAR(16) NOT NULL DEFAULT 'COMPLETED' AFTER direction",
        ),
        (
            "entry_record_id",
            "ALTER TABLE plate_recognition_history "
            "ADD COLUMN entry_record_id BIGINT UNSIGNED NULL AFTER parking_status",
        ),
        (
            "fee_amount",
            "ALTER TABLE plate_recognition_history "
            f"ADD COLUMN fee_amount INT UNSIGNED NOT NULL DEFAULT {PARKING_FEE_VND} AFTER entry_record_id",
        ),
        (
            "face_detected",
            "ALTER TABLE plate_recognition_history "
            "ADD COLUMN face_detected TINYINT(1) NOT NULL DEFAULT 0",
        ),
        (
            "face_confidence",
            "ALTER TABLE plate_recognition_history "
            "ADD COLUMN face_confidence DECIMAL(5, 4) NULL",
        ),
        (
            "face_embedding",
            "ALTER TABLE plate_recognition_history ADD COLUMN face_embedding BLOB NULL",
        ),
        (
            "face_match_score",
            "ALTER TABLE plate_recognition_history "
            "ADD COLUMN face_match_score DECIMAL(5, 4) NULL",
        ),
        (
            "plate_image",
            "ALTER TABLE plate_recognition_history ADD COLUMN plate_image LONGTEXT NULL",
        ),
        (
            "face_image",
            "ALTER TABLE plate_recognition_history ADD COLUMN face_image LONGTEXT NULL",
        ),
    ]
    for col_name, ddl in column_migrations:
        if col_name not in existing_columns:
            cursor.execute(ddl)

    cursor.execute(
        "UPDATE plate_recognition_history SET fee_amount = 0 WHERE direction = 'OUT' AND fee_amount <> 0"
    )

    cursor.execute("SHOW INDEX FROM plate_recognition_history")
    existing_indexes = {
        row["Key_name"] if isinstance(row, dict) else row[2]
        for row in cursor.fetchall()
    }
    if "idx_recognized_at" not in existing_indexes:
        cursor.execute(
            "ALTER TABLE plate_recognition_history "
            "ADD INDEX idx_recognized_at (recognized_at)"
        )
    if "idx_plate_status" not in existing_indexes:
        cursor.execute(
            "ALTER TABLE plate_recognition_history "
            "ADD INDEX idx_plate_status (plate_number, parking_status)"
        )
    if "idx_status_dir" not in existing_indexes:
        cursor.execute(
            "ALTER TABLE plate_recognition_history "
            "ADD INDEX idx_status_dir (parking_status, direction)"
        )


def _make_demo_embedding(seed_idx: int, shift: float = 0.0) -> list[float]:
    """Tạo vector khuôn mặt 512 chiều chuẩn hóa L2 dùng cho dữ liệu demo."""
    raw = [math.sin((i + 1) * (seed_idx + 1) * 0.17 + shift) for i in range(512)]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]


def _make_demo_row(
    plate: str,
    direction: str,
    rec_time: datetime,
    vc: int,
    sc: int,
    rate: float,
    f_conf: float,
    seed_idx: int,
    shift: float = 0.0,
    m_score: float | None = None,
) -> dict:
    is_in = direction == "IN"
    return {
        "plate_number": plate,
        "direction": direction,
        "parking_status": "IN_PARKING" if is_in else "EXITED",
        "fee_amount": PARKING_FEE_VND if is_in else 0,
        "recognized_at": rec_time,
        "vote_count": vc,
        "sample_count": sc,
        "consensus_rate": rate,
        "face_detected": True,
        "face_confidence": f_conf,
        "face_embedding": _make_demo_embedding(seed_idx, shift),
        "face_match_score": m_score,
        "camera_index": 2 if is_in else 1,
    }


def _build_demo_records_list() -> list[dict]:
    now = datetime.now().replace(microsecond=0)
    records: list[dict] = []

    # 1. Các lượt xe hoàn tất ở các tháng/ngày trước (để báo cáo Năm & Tháng sinh động)
    historical_completed = [
        ("59H1-304.88", 42, 180, 5, 5, 1.00, 0.98, 0.94, 1),
        ("60F2-719.25", 38, 210, 4, 5, 0.80, 0.97, 0.92, 2),
        ("59N2-841.60", 32, 145, 5, 6, 0.83, 0.99, 0.96, 3),
        ("71B3-209.14", 18, 195, 5, 5, 1.00, 0.96, 0.91, 4),
        ("59T1-662.39", 12, 160, 4, 5, 0.80, 0.98, 0.95, 5),
        ("61G1-530.72", 7, 240, 5, 5, 1.00, 0.97, 0.93, 6),
        ("59K2-194.55", 4, 175, 5, 6, 0.83, 0.99, 0.97, 7),
        ("62L1-883.07", 2, 150, 5, 5, 1.00, 0.96, 0.92, 8),
        ("59U1-417.90", 1, 200, 4, 5, 0.80, 0.98, 0.94, 9),
        ("59D2-756.31", 1, 130, 5, 5, 1.00, 0.97, 0.95, 10),
    ]
    for plate, days_ago, dur_min, vc, sc, rate, f_conf, m_score, s_idx in historical_completed:
        in_time = (now - timedelta(days=days_ago, hours=4, minutes=dur_min)).replace(
            hour=7, minute=(s_idx * 7) % 55, second=12
        )
        out_time = in_time + timedelta(minutes=dur_min)
        records.append(_make_demo_row(plate, "IN", in_time, vc, sc, rate, f_conf, s_idx, 0.0))
        records.append(
            _make_demo_row(
                plate, "OUT", out_time, vc, sc, rate, round(max(0.92, f_conf - 0.01), 2), s_idx, 0.06, m_score
            )
        )

    # 2. Các lượt xe đã gửi và đã lấy xe RA trong ngày HÔM NAY
    today_completed = [
        ("59A3-128.45", 240, 55, 5, 5, 1.00, 0.99, 0.96, 21),
        ("59G2-604.12", 215, 50, 4, 5, 0.80, 0.97, 0.93, 22),
        ("60B1-889.30", 185, 45, 5, 6, 0.83, 0.98, 0.95, 23),
        ("61C1-442.78", 155, 40, 5, 5, 1.00, 0.96, 0.91, 24),
        ("72D1-319.56", 125, 35, 5, 5, 1.00, 0.99, 0.97, 25),
        ("59P2-910.23", 95, 30, 4, 5, 0.80, 0.98, 0.94, 26),
    ]
    for plate, in_mins_ago, out_mins_ago, vc, sc, rate, f_conf, m_score, s_idx in today_completed:
        in_time = now - timedelta(minutes=in_mins_ago)
        if in_time.date() != now.date():
            in_time = now.replace(hour=max(0, now.hour - 2), minute=10, second=0)
        out_time = now - timedelta(minutes=out_mins_ago)
        if out_time <= in_time:
            out_time = in_time + timedelta(minutes=25)
        records.append(_make_demo_row(plate, "IN", in_time, vc, sc, rate, f_conf, s_idx, 0.0))
        records.append(
            _make_demo_row(
                plate, "OUT", out_time, vc, sc, rate, round(max(0.93, f_conf - 0.01), 2), s_idx, 0.05, m_score
            )
        )

    # 3. Các xe hiện ĐANG GỬI TRONG BÃI (IN_PARKING) hôm nay
    active_in_parking = [
        ("59S2-482.19", 72, 5, 5, 1.00, 0.99, 31),
        ("59X3-715.04", 58, 5, 6, 0.83, 0.97, 32),
        ("60B8-339.62", 44, 4, 5, 0.80, 0.98, 33),
        ("61D1-904.27", 31, 5, 5, 1.00, 0.96, 34),
        ("72C1-558.11", 19, 5, 5, 1.00, 0.99, 35),
        ("49E1-267.85", 8, 4, 5, 0.80, 0.98, 36),
    ]
    for plate, mins_ago, vc, sc, rate, f_conf, s_idx in active_in_parking:
        in_time = now - timedelta(minutes=mins_ago)
        if in_time.date() != now.date():
            in_time = now.replace(hour=max(0, now.hour - 1), minute=35, second=0)
        records.append(_make_demo_row(plate, "IN", in_time, vc, sc, rate, f_conf, s_idx, 0.0))

    return records


def _demo_seeding_enabled() -> bool:
    """Mặc định chỉ tự nạp dữ liệu demo khi dùng SQLite dự phòng trên Cloud; có thể ép bằng SEED_DEMO_DATA."""
    flag = os.getenv("SEED_DEMO_DATA")
    if flag is not None:
        return flag.strip().lower() in ("1", "true", "yes")
    return bool(os.getenv("SPACE_ID")) and _ACTIVE_BACKEND == "sqlite"


def seed_demo_records_if_empty() -> int:
    """Nạp bộ dữ liệu demo (38 bản ghi) nếu CSDL chưa có bộ demo này (phục vụ Demo Đồ án)."""
    if not _demo_seeding_enabled():
        return 0

    marker_plate = "59S2-482.19"
    try:
        if _ACTIVE_BACKEND == "sqlite":
            with _SQLITE_LOCK:
                conn = _connect_sqlite()
                try:
                    _ensure_sqlite_table(conn)
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT COUNT(*) FROM plate_recognition_history WHERE plate_number = ?",
                        (marker_plate,),
                    )
                    count = int(cur.fetchone()[0])
                finally:
                    conn.close()
            if count > 0:
                return 0
            demo_list = _build_demo_records_list()
            for rec in demo_list:
                insert_plate_record(rec)
            print(f"[DB] Đã tự động nạp {len(demo_list)} bản ghi mẫu (SQLite) phục vụ Demo!")
            return len(demo_list)

        connection = _connect_mysql()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM plate_recognition_history WHERE plate_number = %s",
                (marker_plate,),
            )
            row = cursor.fetchone()
            if row and int(row[0]) > 0:
                return 0
            demo_list = _build_demo_records_list()
            for rec in demo_list:
                insert_plate_record(rec, connection=connection)
            print(f"[DB] Đã tự động nạp {len(demo_list)} bản ghi mẫu (MySQL) phục vụ Demo!")
            return len(demo_list)
        finally:
            cursor.close()
            connection.close()
    except Exception as error:  # noqa: BLE001
        print(f"[WARN] Không thể nạp dữ liệu demo tự động: {error}")
        return 0


def initialize_database() -> None:
    """Kết nối thử MySQL; nếu chạy trên Cloud chưa có MySQL thì tự động khởi tạo SQLite."""
    global _ACTIVE_BACKEND
    try:
        connection = _connect_mysql()
        cursor = connection.cursor(dictionary=True)
        try:
            _ensure_mysql_table(cursor)
            connection.commit()
            _ACTIVE_BACKEND = "mysql"
            print(
                f"[DB] Đã kết nối MySQL thành công: "
                f"{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT', '3306')}/{os.getenv('MYSQL_DATABASE')}"
            )
        except MySQLError as error:
            raise DatabaseOperationError(str(error)) from error
        finally:
            cursor.close()
            connection.close()
        seed_demo_records_if_empty()
        return
    except (DatabaseConfigurationError, DatabaseOperationError) as error:
        if not _should_allow_sqlite_fallback():
            raise
        print(f"[WARN] Không kết nối được MySQL ({error}), chuyển sang SQLite dự phòng.")
        conn = _connect_sqlite()
        try:
            _ensure_sqlite_table(conn)
            _ACTIVE_BACKEND = "sqlite"
        finally:
            conn.close()
        seed_demo_records_if_empty()


# ----------------------------------------------------------------------------
# Định dạng hiển thị
# ----------------------------------------------------------------------------
def format_recognition_time(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def format_vnd(amount: int | float | None) -> str:
    val = int(round(float(amount or 0)))
    if val <= 0:
        return "-"
    return f"{val:,}".replace(",", ".") + " đ"


def format_direction_label(direction: str | None) -> str:
    if str(direction or "IN").upper() == "OUT":
        return "Ra bãi"
    return "Vào bãi"


def format_parking_status_label(direction: str | None, parking_status: str | None) -> str:
    status = str(parking_status or "").upper()
    if status == "IN_PARKING":
        return "Đang gửi"
    if str(direction or "IN").upper() == "OUT" or status == "EXITED":
        return "Đã ra bãi"
    return "Đã lấy xe"


def format_face_label(face_detected, face_confidence) -> str:
    if face_detected and face_confidence is not None:
        return f"Có ({float(face_confidence):.0%})"
    if face_detected:
        return "Có"
    return "Không rõ"


def format_match_label(
    direction: str | None, face_match_score, has_embedding: bool
) -> str:
    dir_code = str(direction or "IN").upper()
    if face_match_score is not None:
        score = float(face_match_score)
        verdict = "Khớp" if score >= FACE_MATCH_THRESHOLD else "Lệch"
        return f"{verdict} ({max(score, 0.0):.0%})"
    if dir_code == "IN":
        return "Đã lưu mẫu mặt" if has_embedding else "-"
    return "Chưa có lượt vào" if has_embedding else "-"


def format_record_row(record_id, record: dict) -> dict:
    direction = str(record.get("direction", "IN")).upper()
    parking_status = record.get("parking_status", "IN_PARKING")
    has_emb = bool(record.get("face_embedding"))
    default_fee = 0 if direction == "OUT" else PARKING_FEE_VND
    fee_amount = int(record.get("fee_amount", default_fee))
    fee_label = "Đã thu lúc vào" if direction == "OUT" else format_vnd(fee_amount)
    return {
        "ID": record_id,
        "Biển số": record["plate_number"],
        "Luồng": format_direction_label(direction),
        "Trạng thái bãi": format_parking_status_label(direction, parking_status),
        "Phí giữ xe": fee_label,
        "fee_amount": fee_amount,
        "Thời gian nhận diện": format_recognition_time(record["recognized_at"]),
        "Đồng thuận biển số": (
            f"{record['vote_count']}/{record['sample_count']} "
            f"({float(record['consensus_rate']):.0%})"
        ),
        "Khuôn mặt": format_face_label(
            record.get("face_detected"), record.get("face_confidence")
        ),
        "Đối chiếu": format_match_label(
            direction, record.get("face_match_score"), has_emb
        ),
        "plate_image": record.get("plate_image"),
        "face_image": record.get("face_image"),
        "Camera index": record["camera_index"],
    }


def _normalize_search(text: str) -> str:
    return "".join(ch for ch in str(text or "").upper() if ch.isalnum())


# ----------------------------------------------------------------------------
# Truy vấn & Đối chiếu phiên gửi xe (Hỗ trợ cả MySQL & SQLite)
# ----------------------------------------------------------------------------
def find_active_parking_session(plate_number: str, cursor=None) -> dict | None:
    """Tìm phiên gửi xe đang ở trong bãi (IN_PARKING) gần nhất của biển số này."""
    norm_plate = _normalize_search(plate_number)
    if _ACTIVE_BACKEND == "sqlite" and cursor is None:
        with _SQLITE_LOCK:
            conn = _connect_sqlite()
            try:
                _ensure_sqlite_table(conn)
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT id, plate_number, recognized_at, face_embedding
                    FROM plate_recognition_history
                    WHERE REPLACE(REPLACE(plate_number, '-', ''), '.', '') = ?
                      AND direction = 'IN'
                      AND parking_status = 'IN_PARKING'
                    ORDER BY recognized_at DESC, id DESC
                    LIMIT 1
                    """,
                    (norm_plate,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                raw_emb = row["face_embedding"]
                return {
                    "id": int(row["id"]),
                    "plate_number": row["plate_number"],
                    "recognized_at": format_recognition_time(row["recognized_at"]),
                    "embedding": embedding_from_bytes(
                        bytes(raw_emb) if raw_emb is not None else None
                    ),
                }
            finally:
                conn.close()

    own_conn = cursor is None
    connection = None
    if own_conn:
        connection = _connect_mysql()
        cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, plate_number, recognized_at, face_embedding
            FROM plate_recognition_history
            WHERE REPLACE(REPLACE(plate_number, '-', ''), '.', '') = %s
              AND direction = 'IN'
              AND parking_status = 'IN_PARKING'
            ORDER BY recognized_at DESC, id DESC
            LIMIT 1
            """,
            (norm_plate,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        if not isinstance(row, dict):
            row = {
                "id": row[0],
                "plate_number": row[1],
                "recognized_at": row[2],
                "face_embedding": row[3],
            }
        raw_emb = row.get("face_embedding")
        return {
            "id": int(row["id"]),
            "plate_number": row["plate_number"],
            "recognized_at": format_recognition_time(row["recognized_at"]),
            "embedding": embedding_from_bytes(
                bytes(raw_emb) if raw_emb is not None else None
            ),
        }
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error
    finally:
        if own_conn and connection is not None:
            cursor.close()
            connection.close()


def _find_last_embedding_mysql(cursor, plate_number: str) -> tuple[int | None, list[float] | None]:
    active = find_active_parking_session(plate_number, cursor=cursor)
    if active and active.get("embedding") is not None:
        return active["id"], active["embedding"]

    norm_plate = _normalize_search(plate_number)
    cursor.execute(
        """
        SELECT id, face_embedding
        FROM plate_recognition_history
        WHERE REPLACE(REPLACE(plate_number, '-', ''), '.', '') = %s AND face_embedding IS NOT NULL
        ORDER BY recognized_at DESC, id DESC
        LIMIT 1
        """,
        (norm_plate,),
    )
    row = cursor.fetchone()
    if not row:
        return (active["id"] if active else None), None
    if isinstance(row, dict):
        rec_id, raw = int(row["id"]), row["face_embedding"]
    else:
        rec_id, raw = int(row[0]), row[1]
    return rec_id, embedding_from_bytes(bytes(raw) if raw is not None else None)


def _find_last_embedding_sqlite(cur: sqlite3.Cursor, plate_number: str) -> tuple[int | None, list[float] | None]:
    norm_plate = _normalize_search(plate_number)
    cur.execute(
        """
        SELECT id, face_embedding
        FROM plate_recognition_history
        WHERE REPLACE(REPLACE(plate_number, '-', ''), '.', '') = ?
          AND direction = 'IN'
          AND parking_status = 'IN_PARKING'
        ORDER BY recognized_at DESC, id DESC
        LIMIT 1
        """,
        (norm_plate,),
    )
    row = cur.fetchone()
    if row and row["face_embedding"] is not None:
        return int(row["id"]), embedding_from_bytes(bytes(row["face_embedding"]))
    active_id = int(row["id"]) if row else None

    cur.execute(
        """
        SELECT id, face_embedding
        FROM plate_recognition_history
        WHERE REPLACE(REPLACE(plate_number, '-', ''), '.', '') = ? AND face_embedding IS NOT NULL
        ORDER BY recognized_at DESC, id DESC
        LIMIT 1
        """,
        (norm_plate,),
    )
    row2 = cur.fetchone()
    if not row2:
        return active_id, None
    return int(row2["id"]), embedding_from_bytes(
        bytes(row2["face_embedding"]) if row2["face_embedding"] is not None else None
    )


def verify_checkout_face(
    plate_number: str, exit_embedding: list[float] | None
) -> dict:
    active = find_active_parking_session(plate_number)
    if active is None:
        return {
            "has_active_session": False,
            "entry_id": None,
            "entry_time": None,
            "match_score": None,
            "matched": True,
        }

    entry_emb = active.get("embedding")
    if not exit_embedding or not entry_emb:
        return {
            "has_active_session": True,
            "entry_id": active["id"],
            "entry_time": active["recognized_at"],
            "match_score": None,
            "matched": False,
        }

    score = max(-1.0, min(1.0, cosine_similarity(exit_embedding, entry_emb)))
    return {
        "has_active_session": True,
        "entry_id": active["id"],
        "entry_time": active["recognized_at"],
        "match_score": score,
        "matched": score >= FACE_MATCH_THRESHOLD,
    }


def _fetch_revenue_report_mysql(cursor) -> dict:
    """Tính doanh thu giữ xe (2.000 đ / lượt gửi vào) theo Ngày, Tháng, Năm trên MySQL."""
    cursor.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN DATE(recognized_at) = CURDATE() AND direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_today,
            COALESCE(SUM(CASE WHEN DATE(recognized_at) = CURDATE() THEN fee_amount ELSE 0 END), 0) AS revenue_today,
            COALESCE(SUM(CASE WHEN YEAR(recognized_at) = YEAR(CURDATE()) AND MONTH(recognized_at) = MONTH(CURDATE()) AND direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_month,
            COALESCE(SUM(CASE WHEN YEAR(recognized_at) = YEAR(CURDATE()) AND MONTH(recognized_at) = MONTH(CURDATE()) THEN fee_amount ELSE 0 END), 0) AS revenue_month,
            COALESCE(SUM(CASE WHEN YEAR(recognized_at) = YEAR(CURDATE()) AND direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_year,
            COALESCE(SUM(CASE WHEN YEAR(recognized_at) = YEAR(CURDATE()) THEN fee_amount ELSE 0 END), 0) AS revenue_year,
            COALESCE(SUM(CASE WHEN direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_total,
            COALESCE(SUM(fee_amount), 0) AS revenue_total
        FROM plate_recognition_history
        """
    )
    summary = cursor.fetchone() or {}

    cursor.execute(
        """
        SELECT
            DATE_FORMAT(recognized_at, '%d/%m/%Y') AS period_label,
            DATE(recognized_at) AS sort_date,
            COUNT(*) AS ticket_count,
            COALESCE(SUM(fee_amount), 0) AS total_vnd
        FROM plate_recognition_history
        WHERE direction = 'IN'
        GROUP BY DATE(recognized_at), DATE_FORMAT(recognized_at, '%d/%m/%Y')
        ORDER BY sort_date DESC
        LIMIT 14
        """
    )
    daily_rows = [
        {
            "period": row["period_label"],
            "tickets": int(row["ticket_count"] or 0),
            "unit_price": PARKING_FEE_VND,
            "revenue": int(row["total_vnd"] or 0),
        }
        for row in cursor.fetchall()
    ]

    cursor.execute(
        """
        SELECT
            DATE_FORMAT(recognized_at, '%m/%Y') AS period_label,
            DATE_FORMAT(recognized_at, '%Y-%m') AS sort_month,
            COUNT(*) AS ticket_count,
            COALESCE(SUM(fee_amount), 0) AS total_vnd
        FROM plate_recognition_history
        WHERE direction = 'IN'
        GROUP BY sort_month, period_label
        ORDER BY sort_month DESC
        LIMIT 12
        """
    )
    monthly_rows = [
        {
            "period": f"Tháng {row['period_label']}",
            "tickets": int(row["ticket_count"] or 0),
            "unit_price": PARKING_FEE_VND,
            "revenue": int(row["total_vnd"] or 0),
        }
        for row in cursor.fetchall()
    ]

    cursor.execute(
        """
        SELECT
            CAST(YEAR(recognized_at) AS CHAR) AS period_label,
            YEAR(recognized_at) AS sort_year,
            COUNT(*) AS ticket_count,
            COALESCE(SUM(fee_amount), 0) AS total_vnd
        FROM plate_recognition_history
        WHERE direction = 'IN'
        GROUP BY sort_year, period_label
        ORDER BY sort_year DESC
        LIMIT 10
        """
    )
    yearly_rows = [
        {
            "period": f"Năm {row['period_label']}",
            "tickets": int(row["ticket_count"] or 0),
            "unit_price": PARKING_FEE_VND,
            "revenue": int(row["total_vnd"] or 0),
        }
        for row in cursor.fetchall()
    ]

    return {
        "unit_price": PARKING_FEE_VND,
        "today": {
            "tickets": int(summary.get("tickets_today") or 0),
            "revenue": int(summary.get("revenue_today") or 0),
        },
        "month": {
            "tickets": int(summary.get("tickets_month") or 0),
            "revenue": int(summary.get("revenue_month") or 0),
        },
        "year": {
            "tickets": int(summary.get("tickets_year") or 0),
            "revenue": int(summary.get("revenue_year") or 0),
        },
        "total": {
            "tickets": int(summary.get("tickets_total") or 0),
            "revenue": int(summary.get("revenue_total") or 0),
        },
        "daily": daily_rows,
        "monthly": monthly_rows,
        "yearly": yearly_rows,
    }


def _fetch_revenue_report_sqlite(cur: sqlite3.Cursor) -> dict:
    """Tính doanh thu giữ xe (2.000 đ / lượt gửi vào) theo Ngày, Tháng, Năm trên SQLite."""
    now = datetime.now()
    today_prefix = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    year_prefix = now.strftime("%Y")

    cur.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN substr(recognized_at, 1, 10) = ? AND direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_today,
            COALESCE(SUM(CASE WHEN substr(recognized_at, 1, 10) = ? THEN fee_amount ELSE 0 END), 0) AS revenue_today,
            COALESCE(SUM(CASE WHEN substr(recognized_at, 1, 7) = ? AND direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_month,
            COALESCE(SUM(CASE WHEN substr(recognized_at, 1, 7) = ? THEN fee_amount ELSE 0 END), 0) AS revenue_month,
            COALESCE(SUM(CASE WHEN substr(recognized_at, 1, 4) = ? AND direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_year,
            COALESCE(SUM(CASE WHEN substr(recognized_at, 1, 4) = ? THEN fee_amount ELSE 0 END), 0) AS revenue_year,
            COALESCE(SUM(CASE WHEN direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_total,
            COALESCE(SUM(fee_amount), 0) AS revenue_total
        FROM plate_recognition_history
        """,
        (today_prefix, today_prefix, month_prefix, month_prefix, year_prefix, year_prefix),
    )
    summary = cur.fetchone()

    cur.execute(
        """
        SELECT
            strftime('%d/%m/%Y', recognized_at) AS period_label,
            substr(recognized_at, 1, 10) AS sort_date,
            COUNT(*) AS ticket_count,
            COALESCE(SUM(fee_amount), 0) AS total_vnd
        FROM plate_recognition_history
        WHERE direction = 'IN'
        GROUP BY sort_date
        ORDER BY sort_date DESC
        LIMIT 14
        """
    )
    daily_rows = [
        {
            "period": row["period_label"] or row["sort_date"],
            "tickets": int(row["ticket_count"] or 0),
            "unit_price": PARKING_FEE_VND,
            "revenue": int(row["total_vnd"] or 0),
        }
        for row in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT
            strftime('%m/%Y', recognized_at) AS period_label,
            substr(recognized_at, 1, 7) AS sort_month,
            COUNT(*) AS ticket_count,
            COALESCE(SUM(fee_amount), 0) AS total_vnd
        FROM plate_recognition_history
        WHERE direction = 'IN'
        GROUP BY sort_month
        ORDER BY sort_month DESC
        LIMIT 12
        """
    )
    monthly_rows = [
        {
            "period": f"Tháng {row['period_label'] or row['sort_month']}",
            "tickets": int(row["ticket_count"] or 0),
            "unit_price": PARKING_FEE_VND,
            "revenue": int(row["total_vnd"] or 0),
        }
        for row in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT
            substr(recognized_at, 1, 4) AS period_label,
            COUNT(*) AS ticket_count,
            COALESCE(SUM(fee_amount), 0) AS total_vnd
        FROM plate_recognition_history
        WHERE direction = 'IN'
        GROUP BY period_label
        ORDER BY period_label DESC
        LIMIT 10
        """
    )
    yearly_rows = [
        {
            "period": f"Năm {row['period_label']}",
            "tickets": int(row["ticket_count"] or 0),
            "unit_price": PARKING_FEE_VND,
            "revenue": int(row["total_vnd"] or 0),
        }
        for row in cur.fetchall()
    ]

    return {
        "unit_price": PARKING_FEE_VND,
        "today": {
            "tickets": int(summary["tickets_today"] or 0) if summary else 0,
            "revenue": int(summary["revenue_today"] or 0) if summary else 0,
        },
        "month": {
            "tickets": int(summary["tickets_month"] or 0) if summary else 0,
            "revenue": int(summary["revenue_month"] or 0) if summary else 0,
        },
        "year": {
            "tickets": int(summary["tickets_year"] or 0) if summary else 0,
            "revenue": int(summary["revenue_year"] or 0) if summary else 0,
        },
        "total": {
            "tickets": int(summary["tickets_total"] or 0) if summary else 0,
            "revenue": int(summary["revenue_total"] or 0) if summary else 0,
        },
        "daily": daily_rows,
        "monthly": monthly_rows,
        "yearly": yearly_rows,
    }


def fetch_overview(
    query: str = "", status_filter: str = "all", limit: int = HISTORY_LIMIT
):
    """Thống kê toàn bộ bảng + báo cáo doanh thu Ngày/Tháng/Năm + danh sách bản ghi."""
    if _ACTIVE_BACKEND == "sqlite":
        with _SQLITE_LOCK:
            conn = _connect_sqlite()
            try:
                _ensure_sqlite_table(conn)
                cur = conn.cursor()
                today_prefix = datetime.now().strftime("%Y-%m-%d")
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        COALESCE(SUM(CASE WHEN substr(recognized_at, 1, 10) = ? THEN 1 ELSE 0 END), 0) AS today,
                        COALESCE(SUM(CASE WHEN direction = 'IN' AND parking_status = 'IN_PARKING' THEN 1 ELSE 0 END), 0) AS in_parking,
                        COALESCE(SUM(CASE WHEN direction = 'IN' THEN 1 ELSE 0 END), 0) AS total_in,
                        COALESCE(SUM(CASE WHEN direction = 'OUT' THEN 1 ELSE 0 END), 0) AS total_out,
                        COALESCE(SUM(CASE WHEN face_detected = 1 THEN 1 ELSE 0 END), 0) AS with_face
                    FROM plate_recognition_history
                    """,
                    (today_prefix,),
                )
                stats_row = cur.fetchone()
                total = int(stats_row["total"] or 0) if stats_row else 0
                with_face = int(stats_row["with_face"] or 0) if stats_row else 0
                in_parking = int(stats_row["in_parking"] or 0) if stats_row else 0
                total_in = int(stats_row["total_in"] or 0) if stats_row else 0
                total_out = int(stats_row["total_out"] or 0) if stats_row else 0
                today_cnt = int(stats_row["today"] or 0) if stats_row else 0

                revenue_report = _fetch_revenue_report_sqlite(cur)

                conditions = []
                params: list = []
                normalized_query = _normalize_search(query)
                if normalized_query:
                    conditions.append(
                        "REPLACE(REPLACE(plate_number, '-', ''), '.', '') LIKE ?"
                    )
                    params.append(f"%{normalized_query}%")

                if status_filter == "in_parking":
                    conditions.append("direction = 'IN' AND parking_status = 'IN_PARKING'")
                elif status_filter == "direction_in":
                    conditions.append("direction = 'IN'")
                elif status_filter == "direction_out":
                    conditions.append("direction = 'OUT'")
                elif status_filter == "with_face":
                    conditions.append("face_detected = 1")
                elif status_filter == "no_face":
                    conditions.append("face_detected = 0")

                where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                cur.execute(
                    f"SELECT COUNT(*) AS matched FROM plate_recognition_history {where_sql}",
                    params,
                )
                matched_row = cur.fetchone()
                matched = int(matched_row["matched"] or 0) if matched_row else 0

                cur.execute(
                    f"""
                    SELECT id, plate_number, direction, parking_status, entry_record_id,
                           fee_amount, recognized_at, vote_count, sample_count,
                           consensus_rate, face_detected, face_confidence,
                           (face_embedding IS NOT NULL) AS face_embedding, face_match_score,
                           plate_image, face_image, camera_index
                    FROM plate_recognition_history
                    {where_sql}
                    ORDER BY recognized_at DESC, id DESC
                    LIMIT ?
                    """,
                    [*params, int(limit)],
                )
                records = [
                    format_record_row(dict(row)["id"], dict(row))
                    for row in cur.fetchall()
                ]
                return {
                    "stats": {
                        "total_records": total,
                        "today_records": today_cnt,
                        "in_parking": in_parking,
                        "total_in": total_in,
                        "total_out": total_out,
                        "with_face": with_face,
                        "no_face": total - with_face,
                        "face_rate": round(with_face / total * 100) if total else 0,
                    },
                    "revenue": revenue_report,
                    "matched": matched,
                    "records": records,
                }
            finally:
                conn.close()

    connection = _connect_mysql()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(recognized_at >= CURDATE()), 0) AS today,
                COALESCE(SUM(direction = 'IN' AND parking_status = 'IN_PARKING'), 0) AS in_parking,
                COALESCE(SUM(direction = 'IN'), 0) AS total_in,
                COALESCE(SUM(direction = 'OUT'), 0) AS total_out,
                COALESCE(SUM(face_detected = 1), 0) AS with_face
            FROM plate_recognition_history
            """
        )
        stats_row = cursor.fetchone() or {}
        total = int(stats_row.get("total") or 0)
        with_face = int(stats_row.get("with_face") or 0)
        in_parking = int(stats_row.get("in_parking") or 0)
        total_in = int(stats_row.get("total_in") or 0)
        total_out = int(stats_row.get("total_out") or 0)

        revenue_report = _fetch_revenue_report_mysql(cursor)

        conditions = []
        params = []
        normalized_query = _normalize_search(query)
        if normalized_query:
            conditions.append(
                "REPLACE(REPLACE(plate_number, '-', ''), '.', '') LIKE %s"
            )
            params.append(f"%{normalized_query}%")

        if status_filter == "in_parking":
            conditions.append("direction = 'IN' AND parking_status = 'IN_PARKING'")
        elif status_filter == "direction_in":
            conditions.append("direction = 'IN'")
        elif status_filter == "direction_out":
            conditions.append("direction = 'OUT'")
        elif status_filter == "with_face":
            conditions.append("face_detected = 1")
        elif status_filter == "no_face":
            conditions.append("face_detected = 0")

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cursor.execute(
            f"SELECT COUNT(*) AS matched FROM plate_recognition_history {where_sql}",
            params,
        )
        matched = int((cursor.fetchone() or {}).get("matched") or 0)

        cursor.execute(
            f"""
            SELECT id, plate_number, direction, parking_status, entry_record_id,
                   fee_amount, recognized_at, vote_count, sample_count,
                   consensus_rate, face_detected, face_confidence,
                   face_embedding IS NOT NULL AS face_embedding, face_match_score,
                   plate_image, face_image, camera_index
            FROM plate_recognition_history
            {where_sql}
            ORDER BY recognized_at DESC, id DESC
            LIMIT %s
            """,
            [*params, int(limit)],
        )
        records = [format_record_row(row["id"], row) for row in cursor.fetchall()]

        return {
            "stats": {
                "total_records": total,
                "today_records": int(stats_row.get("today") or 0),
                "in_parking": in_parking,
                "total_in": total_in,
                "total_out": total_out,
                "with_face": with_face,
                "no_face": total - with_face,
                "face_rate": round(with_face / total * 100) if total else 0,
            },
            "revenue": revenue_report,
            "matched": matched,
            "records": records,
        }
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        connection.close()


def insert_plate_record(record: dict, connection=None) -> tuple[int, float | None]:
    """Lưu một lượt nhận diện (VÀO hoặc RA)."""
    if _ACTIVE_BACKEND == "sqlite" and connection is None:
        with _SQLITE_LOCK:
            conn = _connect_sqlite()
            try:
                _ensure_sqlite_table(conn)
                cur = conn.cursor()
                direction = str(record.get("direction") or "IN").upper()
                embedding = record.get("face_embedding")
                match_score = record.get("face_match_score")
                entry_id = record.get("entry_record_id")

                if direction == "OUT":
                    parking_status = "EXITED"
                    fee_amount = 0
                    if embedding and match_score is None:
                        found_id, previous_emb = _find_last_embedding_sqlite(
                            cur, record["plate_number"]
                        )
                        if entry_id is None:
                            entry_id = found_id
                        if previous_emb is not None:
                            match_score = max(
                                -1.0, min(1.0, cosine_similarity(embedding, previous_emb))
                            )
                    cur.execute(
                        """
                        UPDATE plate_recognition_history
                        SET parking_status = 'COMPLETED'
                        WHERE REPLACE(REPLACE(plate_number, '-', ''), '.', '') = ?
                          AND direction = 'IN'
                          AND parking_status = 'IN_PARKING'
                        """,
                        (_normalize_search(record["plate_number"]),),
                    )
                else:
                    direction = "IN"
                    parking_status = "IN_PARKING"
                    fee_amount = int(record.get("fee_amount", PARKING_FEE_VND))
                    cur.execute(
                        """
                        UPDATE plate_recognition_history
                        SET parking_status = 'COMPLETED'
                        WHERE REPLACE(REPLACE(plate_number, '-', ''), '.', '') = ?
                          AND direction = 'IN'
                          AND parking_status = 'IN_PARKING'
                        """,
                        (_normalize_search(record["plate_number"]),),
                    )

                cur.execute(
                    """
                    INSERT INTO plate_recognition_history (
                        plate_number, direction, parking_status, entry_record_id,
                        fee_amount, recognized_at, vote_count, sample_count,
                        consensus_rate, face_detected, face_confidence,
                        face_embedding, face_match_score, plate_image, face_image, camera_index
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["plate_number"],
                        direction,
                        parking_status,
                        entry_id,
                        fee_amount,
                        format_recognition_time(record["recognized_at"]),
                        record["vote_count"],
                        record["sample_count"],
                        record["consensus_rate"],
                        1 if record.get("face_detected") else 0,
                        record.get("face_confidence"),
                        embedding_to_bytes(embedding) if embedding else None,
                        match_score,
                        record.get("plate_image"),
                        record.get("face_image"),
                        record["camera_index"],
                    ),
                )
                conn.commit()
                return int(cur.lastrowid), match_score
            finally:
                conn.close()

    own_connection = connection is None
    if own_connection:
        connection = _connect_mysql()
    cursor = connection.cursor()
    try:
        direction = str(record.get("direction") or "IN").upper()
        embedding = record.get("face_embedding")
        match_score = record.get("face_match_score")
        entry_id = record.get("entry_record_id")

        if direction == "OUT":
            parking_status = "EXITED"
            fee_amount = 0
            if embedding and match_score is None:
                found_id, previous_emb = _find_last_embedding_mysql(
                    cursor, record["plate_number"]
                )
                if entry_id is None:
                    entry_id = found_id
                if previous_emb is not None:
                    match_score = max(
                        -1.0, min(1.0, cosine_similarity(embedding, previous_emb))
                    )
            cursor.execute(
                """
                UPDATE plate_recognition_history
                SET parking_status = 'COMPLETED'
                WHERE REPLACE(REPLACE(plate_number, '-', ''), '.', '') = %s
                  AND direction = 'IN'
                  AND parking_status = 'IN_PARKING'
                """,
                (_normalize_search(record["plate_number"]),),
            )
        else:
            direction = "IN"
            parking_status = "IN_PARKING"
            fee_amount = int(record.get("fee_amount", PARKING_FEE_VND))
            cursor.execute(
                """
                UPDATE plate_recognition_history
                SET parking_status = 'COMPLETED'
                WHERE REPLACE(REPLACE(plate_number, '-', ''), '.', '') = %s
                  AND direction = 'IN'
                  AND parking_status = 'IN_PARKING'
                """,
                (_normalize_search(record["plate_number"]),),
            )

        cursor.execute(
            """
            INSERT INTO plate_recognition_history (
                plate_number, direction, parking_status, entry_record_id,
                fee_amount, recognized_at, vote_count, sample_count,
                consensus_rate, face_detected, face_confidence,
                face_embedding, face_match_score, plate_image, face_image, camera_index
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record["plate_number"],
                direction,
                parking_status,
                entry_id,
                fee_amount,
                record["recognized_at"],
                record["vote_count"],
                record["sample_count"],
                record["consensus_rate"],
                1 if record.get("face_detected") else 0,
                record.get("face_confidence"),
                embedding_to_bytes(embedding) if embedding else None,
                match_score,
                record.get("plate_image"),
                record.get("face_image"),
                record["camera_index"],
            ),
        )
        connection.commit()
        return cursor.lastrowid, match_score
    except MySQLError as error:
        connection.rollback()
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        if own_connection:
            connection.close()


def flush_pending_plate_records(pending_records: list[dict]) -> int:
    """Ghi lần lượt các bản ghi chờ qua một kết nối."""
    if _ACTIVE_BACKEND == "sqlite":
        flushed = 0
        while pending_records:
            insert_plate_record(pending_records[0])
            pending_records.pop(0)
            flushed += 1
        return flushed

    connection = _connect_mysql()
    cursor = connection.cursor(dictionary=True)
    flushed = 0
    try:
        _ensure_mysql_table(cursor)
        connection.commit()
        while pending_records:
            insert_plate_record(pending_records[0], connection=connection)
            pending_records.pop(0)
            flushed += 1
        return flushed
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        connection.close()

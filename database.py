import math
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector import pooling
from dotenv import load_dotenv

from face_service import (
    FACE_MATCH_THRESHOLD,
    cosine_similarity,
    embedding_from_bytes,
    embedding_to_bytes,
)


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

PARKING_FEE_VND = 2000  # 2.000 VNĐ / lượt giữ xe
VN_TZ = timezone(timedelta(hours=7))

_POOL_LOCK = threading.Lock()
_MYSQL_POOL: pooling.MySQLConnectionPool | None = None
_POOL_CONFIG_KEY: tuple | None = None


def now_vn() -> datetime:
    """Trả về thời gian hiện tại theo múi giờ Việt Nam (UTC+7, naive datetime) đồng nhất trên cả Local & Cloud."""
    return datetime.now(VN_TZ).replace(tzinfo=None, microsecond=0)


class DatabaseConfigurationError(RuntimeError):
    pass


class DatabaseOperationError(RuntimeError):
    pass


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
    global _MYSQL_POOL, _POOL_CONFIG_KEY
    config = _connection_config()
    cfg_key = (
        config["host"],
        config["port"],
        config["user"],
        config["password"],
        config["database"],
    )
    try:
        with _POOL_LOCK:
            if _MYSQL_POOL is None or _POOL_CONFIG_KEY != cfg_key:
                _MYSQL_POOL = pooling.MySQLConnectionPool(
                    pool_name="datn_mysql_pool",
                    pool_size=6,
                    pool_reset_session=True,
                    **config,
                )
                _POOL_CONFIG_KEY = cfg_key
            pool = _MYSQL_POOL

        conn = None
        try:
            conn = pool.get_connection()
            conn.ping(reconnect=True, attempts=1, delay=0)
            return conn
        except pooling.PoolError:
            # Khi pool tạm thời cạn kết nối -> mở kết nối trực tiếp dự phòng thay vì báo lỗi mất DB
            return mysql.connector.connect(**config)
        except MySQLError:
            # Nếu kết nối cũ trong pool bị Aiven đóng và ping thất bại -> trả slot về pool rồi mở kết nối mới
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            return mysql.connector.connect(**config)
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error


def _ensure_mysql_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS plate_recognition_history (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            plate_number VARCHAR(32) NOT NULL,
            plate_key VARCHAR(32) NULL,
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
            INDEX idx_status_dir (parking_status, direction),
            INDEX idx_plate_key_dir_status (plate_key, direction, parking_status),
            INDEX idx_entry_record_id (entry_record_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )

    cursor.execute("SHOW COLUMNS FROM plate_recognition_history")
    existing_columns = {
        row["Field"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()
    }
    column_migrations = [
        (
            "plate_key",
            "ALTER TABLE plate_recognition_history "
            "ADD COLUMN plate_key VARCHAR(32) NULL AFTER plate_number",
        ),
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
        "UPDATE plate_recognition_history "
        "SET plate_key = UPPER(REPLACE(REPLACE(plate_number, '-', ''), '.', '')) "
        "WHERE plate_key IS NULL OR plate_key = ''"
    )
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
    if "idx_plate_key_dir_status" not in existing_indexes:
        cursor.execute(
            "ALTER TABLE plate_recognition_history "
            "ADD INDEX idx_plate_key_dir_status (plate_key, direction, parking_status)"
        )
    if "idx_entry_record_id" not in existing_indexes:
        cursor.execute(
            "ALTER TABLE plate_recognition_history "
            "ADD INDEX idx_entry_record_id (entry_record_id)"
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
    now = now_vn()
    records: list[dict] = []

    # 1. Các lượt xe hoàn tất ở các tháng/ngày trước (định dạng chuẩn normalize_plate không dấu chấm)
    historical_completed = [
        ("59H1-30488", 42, 180, 5, 5, 1.00, 0.98, 0.94, 1),
        ("60F2-71925", 38, 210, 4, 5, 0.80, 0.97, 0.92, 2),
        ("59N2-84160", 32, 145, 5, 6, 0.83, 0.99, 0.96, 3),
        ("71B3-20914", 18, 195, 5, 5, 1.00, 0.96, 0.91, 4),
        ("59T1-66239", 12, 160, 4, 5, 0.80, 0.98, 0.95, 5),
        ("61G1-53072", 7, 240, 5, 5, 1.00, 0.97, 0.93, 6),
        ("59K2-19455", 4, 175, 5, 6, 0.83, 0.99, 0.97, 7),
        ("62L1-88307", 2, 150, 5, 5, 1.00, 0.96, 0.92, 8),
        ("59U1-41790", 1, 200, 4, 5, 0.80, 0.98, 0.94, 9),
        ("59D2-75631", 1, 130, 5, 5, 1.00, 0.97, 0.95, 10),
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
        ("59A3-12845", 240, 55, 5, 5, 1.00, 0.99, 0.96, 21),
        ("59G2-60412", 215, 50, 4, 5, 0.80, 0.97, 0.93, 22),
        ("60B1-88930", 185, 45, 5, 6, 0.83, 0.98, 0.95, 23),
        ("61C1-44278", 155, 40, 5, 5, 1.00, 0.96, 0.91, 24),
        ("72D1-31956", 125, 35, 5, 5, 1.00, 0.99, 0.97, 25),
        ("59P2-91023", 95, 30, 4, 5, 0.80, 0.98, 0.94, 26),
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
        ("59S2-48219", 72, 5, 5, 1.00, 0.99, 31),
        ("59X3-71504", 58, 5, 6, 0.83, 0.97, 32),
        ("60B8-33962", 44, 4, 5, 0.80, 0.98, 33),
        ("61D1-90427", 31, 5, 5, 1.00, 0.96, 34),
        ("72C1-55811", 19, 5, 5, 1.00, 0.99, 35),
        ("49E1-26785", 8, 4, 5, 0.80, 0.98, 36),
    ]
    for plate, mins_ago, vc, sc, rate, f_conf, s_idx in active_in_parking:
        in_time = now - timedelta(minutes=mins_ago)
        if in_time.date() != now.date():
            in_time = now.replace(hour=max(0, now.hour - 1), minute=35, second=0)
        records.append(_make_demo_row(plate, "IN", in_time, vc, sc, rate, f_conf, s_idx, 0.0))

    return records


def _demo_seeding_enabled() -> bool:
    """Chỉ tự nạp dữ liệu demo khi bật cờ SEED_DEMO_DATA=1."""
    flag = os.getenv("SEED_DEMO_DATA")
    if flag is not None:
        return flag.strip().lower() in ("1", "true", "yes")
    return False


def seed_demo_records_if_empty() -> int:
    """Nạp bộ dữ liệu demo (38 bản ghi) nếu CSDL chưa có bộ demo này (phục vụ Demo Đồ án)."""
    if not _demo_seeding_enabled():
        return 0

    marker_key = "59S248219"
    try:
        connection = _connect_mysql()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM plate_recognition_history WHERE plate_key = %s",
                (marker_key,),
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
    """Kết nối và khởi tạo bảng trên MySQL."""
    connection = _connect_mysql()
    cursor = connection.cursor(dictionary=True)
    try:
        _ensure_mysql_table(cursor)
        connection.commit()
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
    return "Chưa đối chiếu" if has_embedding else "-"


def format_record_row(record_id, record: dict) -> dict:
    direction = str(record.get("direction", "IN")).upper()
    parking_status = record.get("parking_status", "IN_PARKING")
    has_emb = bool(record.get("face_embedding"))
    raw_entry_id = record.get("entry_record_id")
    entry_record_id = int(raw_entry_id) if raw_entry_id is not None else None
    raw_match = record.get("face_match_score")
    face_match_score = float(raw_match) if raw_match is not None else None
    return {
        "ID": record_id,
        "Biển số": record["plate_number"],
        "direction_code": direction,
        "parking_status_code": str(parking_status or "").upper(),
        "entry_record_id": entry_record_id,
        "face_match_score": face_match_score,
        "Luồng": format_direction_label(direction),
        "Trạng thái bãi": format_parking_status_label(direction, parking_status),
        "Thời gian nhận diện": format_recognition_time(record["recognized_at"]),
        "Khuôn mặt": format_face_label(
            record.get("face_detected"), record.get("face_confidence")
        ),
        "Đối chiếu": format_match_label(
            direction, record.get("face_match_score"), has_emb
        ),
        "plate_image": record.get("plate_image"),
        "face_image": record.get("face_image"),
    }


def _normalize_search(text: str) -> str:
    return "".join(ch for ch in str(text or "").upper() if ch.isalnum())


# ----------------------------------------------------------------------------
# Truy vấn & Đối chiếu phiên gửi xe (MySQL)
# ----------------------------------------------------------------------------
def find_active_parking_session(plate_number: str, cursor=None) -> dict | None:
    """Tìm phiên gửi xe đang ở trong bãi (IN_PARKING) gần nhất của biển số này."""
    norm_plate = _normalize_search(plate_number)
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
            WHERE plate_key = %s
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
    if active:
        return active["id"], active.get("embedding")
    return None, None


def _fetch_revenue_report_mysql(cursor) -> dict:
    """Tính doanh thu giữ xe (2.000 đ / lượt gửi vào) theo Ngày, Tháng, Năm trên MySQL (theo múi giờ VN UTC+7)."""
    vn_now = now_vn()
    today_start = vn_now.replace(hour=0, minute=0, second=0)
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    cursor.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN recognized_at >= %s AND direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_today,
            COALESCE(SUM(CASE WHEN recognized_at >= %s THEN fee_amount ELSE 0 END), 0) AS revenue_today,
            COALESCE(SUM(CASE WHEN recognized_at >= %s AND direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_month,
            COALESCE(SUM(CASE WHEN recognized_at >= %s THEN fee_amount ELSE 0 END), 0) AS revenue_month,
            COALESCE(SUM(CASE WHEN recognized_at >= %s AND direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_year,
            COALESCE(SUM(CASE WHEN recognized_at >= %s THEN fee_amount ELSE 0 END), 0) AS revenue_year,
            COALESCE(SUM(CASE WHEN direction = 'IN' THEN 1 ELSE 0 END), 0) AS tickets_total,
            COALESCE(SUM(fee_amount), 0) AS revenue_total
        FROM plate_recognition_history
        """,
        (today_start, today_start, month_start, month_start, year_start, year_start),
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


def fetch_overview(
    query: str = "",
    status_filter: str = "all",
    limit: int | None = None,
    page: int = 1,
    page_size: int = 10,
    include_records: bool = True,
    include_stats_and_revenue: bool = True,
):
    """Thống kê toàn bộ bảng + báo cáo doanh thu Ngày/Tháng/Năm + danh sách bản ghi phân trang."""
    connection = _connect_mysql()
    cursor = connection.cursor(dictionary=True)
    try:
        stats_payload = None
        revenue_report = None
        if include_stats_and_revenue:
            today_start = now_vn().replace(hour=0, minute=0, second=0)
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(recognized_at >= %s), 0) AS today,
                    COALESCE(SUM(direction = 'IN' AND parking_status = 'IN_PARKING'), 0) AS in_parking,
                    COALESCE(SUM(direction = 'IN'), 0) AS total_in,
                    COALESCE(SUM(direction = 'OUT'), 0) AS total_out
                FROM plate_recognition_history
                """,
                (today_start,),
            )
            stats_row = cursor.fetchone() or {}
            total = int(stats_row.get("total") or 0)
            in_parking = int(stats_row.get("in_parking") or 0)
            total_in = int(stats_row.get("total_in") or 0)
            total_out = int(stats_row.get("total_out") or 0)
            stats_payload = {
                "total_records": total,
                "today_records": int(stats_row.get("today") or 0),
                "in_parking": in_parking,
                "total_in": total_in,
                "total_out": total_out,
            }
            revenue_report = _fetch_revenue_report_mysql(cursor)

        if not include_records:
            return {
                "stats": stats_payload,
                "revenue": revenue_report,
                "matched": 0,
                "records": [],
            }

        conditions = []
        params = []
        normalized_query = _normalize_search(query)
        if normalized_query:
            conditions.append("plate_key LIKE %s")
            params.append(f"%{normalized_query}%")

        if status_filter == "in_parking":
            conditions.append("direction = 'IN' AND parking_status = 'IN_PARKING'")
        elif status_filter == "direction_in":
            conditions.append("direction = 'IN'")
        elif status_filter == "direction_out":
            conditions.append("direction = 'OUT'")

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cursor.execute(
            f"SELECT COUNT(*) AS matched FROM plate_recognition_history {where_sql}",
            params,
        )
        matched = int((cursor.fetchone() or {}).get("matched") or 0)

        if limit is not None:
            effective_limit = max(1, int(limit))
            safe_page = 1
            effective_offset = 0
        else:
            effective_limit = max(1, int(page_size))
            total_pages = max(1, math.ceil(matched / effective_limit)) if matched > 0 else 1
            safe_page = min(max(1, int(page)), total_pages)
            effective_offset = (safe_page - 1) * effective_limit

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
            LIMIT %s OFFSET %s
            """,
            [*params, effective_limit, effective_offset],
        )
        records = [format_record_row(row["id"], row) for row in cursor.fetchall()]

        return {
            "stats": stats_payload,
            "revenue": revenue_report,
            "matched": matched,
            "page": safe_page,
            "records": records,
        }
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        connection.close()


def fetch_parking_session_case(record_id: int) -> dict | None:
    """Truy vấn cặp bản ghi (Check-in & Check-out) trực tiếp từ MySQL theo ID được chọn và entry_record_id."""
    connection = _connect_mysql()
    cursor = connection.cursor(dictionary=True)
    select_cols = """
        SELECT id, plate_number, plate_key, direction, parking_status, entry_record_id,
               fee_amount, recognized_at, vote_count, sample_count,
               consensus_rate, face_detected, face_confidence,
               face_embedding IS NOT NULL AS face_embedding, face_match_score,
               plate_image, face_image, camera_index
        FROM plate_recognition_history
    """
    try:
        cursor.execute(f"{select_cols} WHERE id = %s LIMIT 1", (int(record_id),))
        target = cursor.fetchone()
        if not target:
            return None

        target_dir = str(target.get("direction") or "IN").upper()
        checkin_raw = None
        checkout_raw = None

        if target_dir == "OUT":
            checkout_raw = target
            entry_id = target.get("entry_record_id")
            if entry_id is not None:
                cursor.execute(f"{select_cols} WHERE id = %s LIMIT 1", (int(entry_id),))
                checkin_raw = cursor.fetchone()
            if checkin_raw is None:
                norm_plate = target.get("plate_key") or _normalize_search(
                    target.get("plate_number") or ""
                )
                cursor.execute(
                    f"""
                    {select_cols}
                    WHERE plate_key = %s
                      AND direction = 'IN'
                      AND (recognized_at < %s OR (recognized_at = %s AND id < %s))
                    ORDER BY recognized_at DESC, id DESC
                    LIMIT 1
                    """,
                    (
                        norm_plate,
                        target["recognized_at"],
                        target["recognized_at"],
                        int(target["id"]),
                    ),
                )
                checkin_raw = cursor.fetchone()
        else:
            checkin_raw = target
            cursor.execute(
                f"""
                {select_cols}
                WHERE direction = 'OUT' AND entry_record_id = %s
                ORDER BY recognized_at ASC, id ASC
                LIMIT 1
                """,
                (int(target["id"]),),
            )
            checkout_raw = cursor.fetchone()

            if checkout_raw is None:
                norm_plate = target.get("plate_key") or _normalize_search(
                    target.get("plate_number") or ""
                )
                cursor.execute(
                    """
                    SELECT id, recognized_at
                    FROM plate_recognition_history
                    WHERE plate_key = %s
                      AND direction = 'IN'
                      AND (recognized_at > %s OR (recognized_at = %s AND id > %s))
                    ORDER BY recognized_at ASC, id ASC
                    LIMIT 1
                    """,
                    (
                        norm_plate,
                        target["recognized_at"],
                        target["recognized_at"],
                        int(target["id"]),
                    ),
                )
                next_in = cursor.fetchone()
                if next_in:
                    cursor.execute(
                        f"""
                        {select_cols}
                        WHERE plate_key = %s
                          AND direction = 'OUT'
                          AND (recognized_at > %s OR (recognized_at = %s AND id > %s))
                          AND (recognized_at < %s OR (recognized_at = %s AND id < %s))
                        ORDER BY recognized_at ASC, id ASC
                        LIMIT 1
                        """,
                        (
                            norm_plate,
                            target["recognized_at"],
                            target["recognized_at"],
                            int(target["id"]),
                            next_in["recognized_at"],
                            next_in["recognized_at"],
                            int(next_in["id"]),
                        ),
                    )
                else:
                    cursor.execute(
                        f"""
                        {select_cols}
                        WHERE plate_key = %s
                          AND direction = 'OUT'
                          AND (recognized_at > %s OR (recognized_at = %s AND id > %s))
                        ORDER BY recognized_at ASC, id ASC
                        LIMIT 1
                        """,
                        (
                            norm_plate,
                            target["recognized_at"],
                            target["recognized_at"],
                            int(target["id"]),
                        ),
                    )
                checkout_raw = cursor.fetchone()

        checkin_row = (
            format_record_row(checkin_raw["id"], checkin_raw) if checkin_raw else None
        )
        checkout_row = (
            format_record_row(checkout_raw["id"], checkout_raw)
            if checkout_raw
            else None
        )
        in_status = (
            str(checkin_raw.get("parking_status") or "").upper()
            if checkin_raw
            else ""
        )
        session_closed_missing_exit = bool(
            checkin_raw is not None
            and checkout_raw is None
            and in_status != "IN_PARKING"
        )
        return {
            "target_id": int(target["id"]),
            "plate_number": (
                (checkin_row and checkin_row["Biển số"])
                or (checkout_row and checkout_row["Biển số"])
                or target.get("plate_number")
                or "-"
            ),
            "checkin_row": checkin_row,
            "checkout_row": checkout_row,
            "in_parking_status": in_status,
            "session_closed_missing_exit": session_closed_missing_exit,
        }
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        connection.close()


def insert_plate_record(record: dict, connection=None) -> tuple[int, float | None]:
    """Lưu một lượt nhận diện (VÀO hoặc RA) trực tiếp vào MySQL."""
    own_connection = connection is None
    if own_connection:
        connection = _connect_mysql()
    cursor = connection.cursor()
    try:
        direction = str(record.get("direction") or "IN").upper()
        embedding = record.get("face_embedding")
        match_score = record.get("face_match_score")
        entry_id = record.get("entry_record_id")
        plate_key = _normalize_search(record["plate_number"])

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
        else:
            direction = "IN"
            parking_status = "IN_PARKING"
            fee_amount = int(record.get("fee_amount", PARKING_FEE_VND))

        cursor.execute(
            """
            UPDATE plate_recognition_history
            SET parking_status = 'COMPLETED'
            WHERE plate_key = %s
              AND direction = 'IN'
              AND parking_status = 'IN_PARKING'
            """,
            (plate_key,),
        )

        cursor.execute(
            """
            INSERT INTO plate_recognition_history (
                plate_number, plate_key, direction, parking_status, entry_record_id,
                fee_amount, recognized_at, vote_count, sample_count,
                consensus_rate, face_detected, face_confidence,
                face_embedding, face_match_score, plate_image, face_image, camera_index
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record["plate_number"],
                plate_key,
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

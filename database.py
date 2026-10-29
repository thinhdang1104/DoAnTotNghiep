import os
from datetime import datetime
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


load_dotenv(Path(__file__).resolve().parent / ".env")

HISTORY_LIMIT = 200


class DatabaseConfigurationError(RuntimeError):
    pass


class DatabaseOperationError(RuntimeError):
    pass


def _connection_config():
    required = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_DATABASE")
    missing = [name for name in required if not os.getenv(name)]
    # Mật khẩu được phép rỗng (VD: XAMPP mặc định root / ""), chỉ báo thiếu khi không khai báo.
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
        "connection_timeout": 5,
    }


def _connect():
    config = _connection_config()
    try:
        return mysql.connector.connect(**config)
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error


def _ensure_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS plate_recognition_history (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            plate_number VARCHAR(32) NOT NULL,
            recognized_at DATETIME NOT NULL,
            vote_count SMALLINT UNSIGNED NOT NULL,
            sample_count SMALLINT UNSIGNED NOT NULL,
            consensus_rate DECIMAL(5, 4) NOT NULL,
            face_detected TINYINT(1) NOT NULL DEFAULT 0,
            face_confidence DECIMAL(5, 4) NULL,
            face_embedding BLOB NULL,
            face_match_score DECIMAL(5, 4) NULL,
            camera_index SMALLINT UNSIGNED NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_plate_recognized_at (plate_number, recognized_at),
            INDEX idx_recognized_at (recognized_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )

    cursor.execute("SHOW COLUMNS FROM plate_recognition_history")
    existing_columns = {
        row["Field"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()
    }
    column_migrations = [
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
    ]
    for col_name, ddl in column_migrations:
        if col_name not in existing_columns:
            cursor.execute(ddl)

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


def initialize_database() -> None:
    """Kết nối thử và tạo / nâng cấp bảng lịch sử nếu cần."""
    connection = _connect()
    cursor = connection.cursor(dictionary=True)
    try:
        _ensure_table(cursor)
        connection.commit()
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        connection.close()


# ----------------------------------------------------------------------------
# Định dạng hiển thị (dùng chung cho bản ghi trong DB và bản ghi đang chờ)
# ----------------------------------------------------------------------------
def format_recognition_time(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def format_face_label(face_detected, face_confidence) -> str:
    if face_detected and face_confidence is not None:
        return f"Có ({float(face_confidence):.0%})"
    if face_detected:
        return "Có"
    return "Không rõ"


def format_match_label(face_match_score, has_embedding: bool) -> str:
    if face_match_score is None:
        return "Lần đầu" if has_embedding else "-"
    score = float(face_match_score)
    verdict = "Khớp" if score >= FACE_MATCH_THRESHOLD else "Lệch"
    return f"{verdict} ({max(score, 0.0):.0%})"


def format_record_row(record_id, record: dict) -> dict:
    return {
        "ID": record_id,
        "Biển số": record["plate_number"],
        "Thời gian nhận diện": format_recognition_time(record["recognized_at"]),
        "Đồng thuận biển số": (
            f"{record['vote_count']}/{record['sample_count']} "
            f"({float(record['consensus_rate']):.0%})"
        ),
        "Khuôn mặt": format_face_label(
            record.get("face_detected"), record.get("face_confidence")
        ),
        "Đối chiếu": format_match_label(
            record.get("face_match_score"), bool(record.get("face_embedding"))
        ),
        "Camera index": record["camera_index"],
    }


# ----------------------------------------------------------------------------
# Truy vấn
# ----------------------------------------------------------------------------
def _normalize_search(text: str) -> str:
    return "".join(ch for ch in str(text or "").upper() if ch.isalnum())


def fetch_overview(query: str = "", face_filter: str = "all", limit: int = HISTORY_LIMIT):
    """Thống kê toàn bộ bảng + danh sách bản ghi (đã lọc) mới nhất."""
    connection = _connect()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(recognized_at >= CURDATE()), 0) AS today,
                COALESCE(SUM(face_detected = 1), 0) AS with_face
            FROM plate_recognition_history
            """
        )
        stats_row = cursor.fetchone() or {}
        total = int(stats_row.get("total") or 0)
        with_face = int(stats_row.get("with_face") or 0)

        conditions = []
        params: list = []
        normalized_query = _normalize_search(query)
        if normalized_query:
            conditions.append(
                "REPLACE(REPLACE(plate_number, '-', ''), '.', '') LIKE %s"
            )
            params.append(f"%{normalized_query}%")
        if face_filter == "with_face":
            conditions.append("face_detected = 1")
        elif face_filter == "no_face":
            conditions.append("face_detected = 0")
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cursor.execute(
            f"SELECT COUNT(*) AS matched FROM plate_recognition_history {where_sql}",
            params,
        )
        matched = int((cursor.fetchone() or {}).get("matched") or 0)

        cursor.execute(
            f"""
            SELECT id, plate_number, recognized_at, vote_count, sample_count,
                   consensus_rate, face_detected, face_confidence,
                   face_embedding IS NOT NULL AS face_embedding, face_match_score,
                   camera_index
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
                "with_face": with_face,
                "no_face": total - with_face,
                "face_rate": round(with_face / total * 100) if total else 0,
            },
            "matched": matched,
            "records": records,
        }
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        connection.close()


def _find_last_embedding(cursor, plate_number: str):
    cursor.execute(
        """
        SELECT face_embedding
        FROM plate_recognition_history
        WHERE plate_number = %s AND face_embedding IS NOT NULL
        ORDER BY recognized_at DESC, id DESC
        LIMIT 1
        """,
        (plate_number,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    raw = row[0] if not isinstance(row, dict) else row["face_embedding"]
    return embedding_from_bytes(bytes(raw) if raw is not None else None)


def insert_plate_record(record: dict, connection=None) -> tuple[int, float | None]:
    """Lưu một lượt nhận diện. Nếu có vector khuôn mặt thì đối chiếu với
    lần gần nhất của cùng biển số. Trả về (id, điểm Cosine hoặc None)."""
    own_connection = connection is None
    if own_connection:
        connection = _connect()
    cursor = connection.cursor()
    try:
        embedding = record.get("face_embedding")
        match_score = None
        if embedding:
            previous = _find_last_embedding(cursor, record["plate_number"])
            if previous is not None:
                match_score = max(-1.0, min(1.0, cosine_similarity(embedding, previous)))

        cursor.execute(
            """
            INSERT INTO plate_recognition_history (
                plate_number, recognized_at, vote_count, sample_count,
                consensus_rate, face_detected, face_confidence,
                face_embedding, face_match_score, camera_index
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record["plate_number"],
                record["recognized_at"],
                record["vote_count"],
                record["sample_count"],
                record["consensus_rate"],
                1 if record.get("face_detected") else 0,
                record.get("face_confidence"),
                embedding_to_bytes(embedding) if embedding else None,
                match_score,
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
    """Ghi lần lượt các bản ghi chờ qua một kết nối. Bản ghi nào ghi xong được
    xóa khỏi danh sách ngay, nên lỗi giữa chừng không làm ghi trùng."""
    connection = _connect()
    cursor = connection.cursor(dictionary=True)
    flushed = 0
    try:
        _ensure_table(cursor)
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

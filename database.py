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
            direction VARCHAR(8) NOT NULL DEFAULT 'IN',
            parking_status VARCHAR(16) NOT NULL DEFAULT 'IN_PARKING',
            entry_record_id BIGINT UNSIGNED NULL,
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
            INDEX idx_recognized_at (recognized_at),
            INDEX idx_plate_status (plate_number, parking_status)
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
    if "idx_plate_status" not in existing_indexes:
        cursor.execute(
            "ALTER TABLE plate_recognition_history "
            "ADD INDEX idx_plate_status (plate_number, parking_status)"
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
# Định dạng hiển thị
# ----------------------------------------------------------------------------
def format_recognition_time(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


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
    direction = record.get("direction", "IN")
    parking_status = record.get("parking_status", "IN_PARKING")
    has_emb = bool(record.get("face_embedding"))
    return {
        "ID": record_id,
        "Biển số": record["plate_number"],
        "Luồng": format_direction_label(direction),
        "Trạng thái bãi": format_parking_status_label(direction, parking_status),
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
        "Camera index": record["camera_index"],
    }


# ----------------------------------------------------------------------------
# Truy vấn & Đối chiếu phiên gửi xe
# ----------------------------------------------------------------------------
def _normalize_search(text: str) -> str:
    return "".join(ch for ch in str(text or "").upper() if ch.isalnum())


def find_active_parking_session(plate_number: str, cursor=None) -> dict | None:
    """Tìm phiên gửi xe đang ở trong bãi (IN_PARKING) gần nhất của biển số này."""
    own_conn = cursor is None
    connection = None
    if own_conn:
        connection = _connect()
        cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, plate_number, recognized_at, face_embedding
            FROM plate_recognition_history
            WHERE plate_number = %s
              AND direction = 'IN'
              AND parking_status = 'IN_PARKING'
            ORDER BY recognized_at DESC, id DESC
            LIMIT 1
            """,
            (plate_number,),
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


def _find_last_embedding(cursor, plate_number: str) -> tuple[int | None, list[float] | None]:
    """Ưu tiên lấy mẫu khuôn mặt của phiên đang gửi (IN_PARKING); nếu không có thì lấy lần gần nhất."""
    active = find_active_parking_session(plate_number, cursor=cursor)
    if active and active.get("embedding") is not None:
        return active["id"], active["embedding"]

    cursor.execute(
        """
        SELECT id, face_embedding
        FROM plate_recognition_history
        WHERE plate_number = %s AND face_embedding IS NOT NULL
        ORDER BY recognized_at DESC, id DESC
        LIMIT 1
        """,
        (plate_number,),
    )
    row = cursor.fetchone()
    if not row:
        return (active["id"] if active else None), None
    if isinstance(row, dict):
        rec_id, raw = int(row["id"]), row["face_embedding"]
    else:
        rec_id, raw = int(row[0]), row[1]
    return rec_id, embedding_from_bytes(bytes(raw) if raw is not None else None)


def verify_checkout_face(
    plate_number: str, exit_embedding: list[float] | None
) -> dict:
    """Đối chiếu vector khuôn mặt lúc RA với phiên gửi xe lúc VÀO trong MySQL.
    Trả về dict gồm: has_active_session, entry_id, entry_time, match_score, matched."""
    active = find_active_parking_session(plate_number)
    if active is None:
        return {
            "has_active_session": False,
            "entry_id": None,
            "entry_time": None,
            "match_score": None,
            "matched": True,  # Không có phiên gửi có mặt để chặn, hoặc cho phép ghi nhận
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


def fetch_overview(
    query: str = "", status_filter: str = "all", limit: int = HISTORY_LIMIT
):
    """Thống kê toàn bộ bảng + danh sách bản ghi mới nhất."""
    connection = _connect()
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

        conditions = []
        params: list = []
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
                   recognized_at, vote_count, sample_count,
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
                "in_parking": in_parking,
                "total_in": total_in,
                "total_out": total_out,
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


def insert_plate_record(record: dict, connection=None) -> tuple[int, float | None]:
    """Lưu một lượt nhận diện (VÀO hoặc RA).
    - Nếu là VÀO ('IN'): đóng các phiên IN_PARKING cũ (nếu có) của cùng biển số và mở phiên IN_PARKING mới.
    - Nếu là RA ('OUT'): đối chiếu Cosine với phiên IN_PARKING của biển số đó và cập nhật phiên đó thành COMPLETED.
    """
    own_connection = connection is None
    if own_connection:
        connection = _connect()
    cursor = connection.cursor()
    try:
        direction = str(record.get("direction") or "IN").upper()
        embedding = record.get("face_embedding")
        match_score = record.get("face_match_score")
        entry_id = record.get("entry_record_id")

        if direction == "OUT":
            parking_status = "EXITED"
            if embedding and match_score is None:
                found_id, previous_emb = _find_last_embedding(
                    cursor, record["plate_number"]
                )
                if entry_id is None:
                    entry_id = found_id
                if previous_emb is not None:
                    match_score = max(
                        -1.0, min(1.0, cosine_similarity(embedding, previous_emb))
                    )
            # Đóng phiên gửi xe đang mở của biển số này
            cursor.execute(
                """
                UPDATE plate_recognition_history
                SET parking_status = 'COMPLETED'
                WHERE plate_number = %s
                  AND direction = 'IN'
                  AND parking_status = 'IN_PARKING'
                """,
                (record["plate_number"],),
            )
        else:
            direction = "IN"
            parking_status = "IN_PARKING"
            # Đảm bảo mỗi biển số chỉ có 1 phiên IN_PARKING đang mở
            cursor.execute(
                """
                UPDATE plate_recognition_history
                SET parking_status = 'COMPLETED'
                WHERE plate_number = %s
                  AND direction = 'IN'
                  AND parking_status = 'IN_PARKING'
                """,
                (record["plate_number"],),
            )

        cursor.execute(
            """
            INSERT INTO plate_recognition_history (
                plate_number, direction, parking_status, entry_record_id,
                recognized_at, vote_count, sample_count,
                consensus_rate, face_detected, face_confidence,
                face_embedding, face_match_score, camera_index
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record["plate_number"],
                direction,
                parking_status,
                entry_id,
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
    """Ghi lần lượt các bản ghi chờ qua một kết nối."""
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

import os
from datetime import datetime
from pathlib import Path

import mysql.connector
from mysql.connector import Error as MySQLError
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")


class DatabaseConfigurationError(RuntimeError):
    pass


class DatabaseOperationError(RuntimeError):
    pass


def _connection_config():
    required = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise DatabaseConfigurationError(
            "Thiếu cấu hình biến môi trường: " + ", ".join(missing)
        )

    try:
        port = int(os.getenv("MYSQL_PORT", "3306"))
    except ValueError as error:
        raise DatabaseConfigurationError(
            "MYSQL_PORT phải là số nguyên."
        ) from error

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
            camera_index SMALLINT UNSIGNED NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_plate_recognized_at (plate_number, recognized_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )

    cursor.execute("SHOW COLUMNS FROM plate_recognition_history")
    existing_columns = {
        row["Field"] if isinstance(row, dict) else row[0]
        for row in cursor.fetchall()
    }
    migrations = [
        (
            "face_detected",
            "ALTER TABLE plate_recognition_history ADD COLUMN face_detected TINYINT(1) NOT NULL DEFAULT 0",
        ),
        (
            "face_confidence",
            "ALTER TABLE plate_recognition_history ADD COLUMN face_confidence DECIMAL(5, 4) NULL",
        ),
    ]
    for col_name, ddl in migrations:
        if col_name not in existing_columns:
            cursor.execute(ddl)


def _fetch_recent_history(cursor):
    cursor.execute(
        """
        SELECT
            id AS ID,
            plate_number AS `Biển số`,
            recognized_at AS `Thời gian nhận diện`,
            CONCAT(
                vote_count, '/', sample_count, ' (',
                ROUND(consensus_rate * 100), '%)'
            ) AS `Đồng thuận biển số`,
            CASE
                WHEN face_detected = 1 AND face_confidence IS NOT NULL
                THEN CONCAT('Có (', ROUND(face_confidence * 100), '%)')
                WHEN face_detected = 1
                THEN 'Có'
                ELSE 'Không rõ'
            END AS `Khuôn mặt`,
            camera_index AS `Camera index`
        FROM plate_recognition_history
        ORDER BY recognized_at DESC, id DESC
        LIMIT 200
        """
    )
    return cursor.fetchall()


def initialize_database():
    connection = _connect()
    cursor = connection.cursor(dictionary=True)
    try:
        _ensure_table(cursor)
        connection.commit()
        return _fetch_recent_history(cursor)
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        connection.close()


def insert_plate_record(
    plate_number,
    recognized_at,
    vote_count,
    sample_count,
    consensus_rate,
    camera_index,
    face_detected=False,
    face_confidence=None,
    connection=None,
):
    own_connection = connection is None
    if own_connection:
        connection = _connect()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO plate_recognition_history (
                plate_number,
                recognized_at,
                vote_count,
                sample_count,
                consensus_rate,
                face_detected,
                face_confidence,
                camera_index
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                plate_number,
                recognized_at,
                vote_count,
                sample_count,
                consensus_rate,
                1 if face_detected else 0,
                face_confidence,
                camera_index,
            ),
        )
        connection.commit()
        return cursor.lastrowid
    except MySQLError as error:
        connection.rollback()
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        if own_connection:
            connection.close()


def flush_pending_plate_records(pending_records):
    """Lưu danh sách bản ghi đang chờ và trả về lịch sử mới nhất qua một kết nối MySQL."""
    connection = _connect()
    cursor = connection.cursor(dictionary=True)
    try:
        _ensure_table(cursor)
        connection.commit()

        while pending_records:
            record = pending_records[0]
            insert_plate_record(**record, connection=connection)
            pending_records.pop(0)

        return _fetch_recent_history(cursor)
    except MySQLError as error:
        raise DatabaseOperationError(str(error)) from error
    finally:
        cursor.close()
        connection.close()


def format_recognition_time(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)

import sys
import threading
import unittest
from unittest import mock
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import database
from database import DatabaseOperationError
import face_service
import main


class TestPlateNormalizationAndAssembly(unittest.TestCase):
    def test_normalize_plate_standard_and_confusable_chars(self):
        # Biển 2 dòng / 1 dòng chuẩn Việt Nam (5 số và 4 số)
        self.assertEqual(main.normalize_plate("59V1-79379"), ("59V179379", "59V1-79379"))
        self.assertEqual(main.normalize_plate("30T4-1975"), ("30T41975", "30T4-1975"))
        self.assertEqual(main.normalize_plate("59a112345"), ("59A112345", "59A1-12345"))

        # Tự sửa lỗi OCR nhầm chữ <-> số (D<->0, B<->8, S<->5, Z<->2, G<->6)
        # "5901-123B5" -> ký tự thứ 3 '0' ở vị trí chữ cái thành 'D', 'B' ở phần số thành '8'
        self.assertEqual(main.normalize_plate("5901-123B5"), ("59D112385", "59D1-12385"))
        self.assertEqual(main.normalize_plate("DBB1-12345"), ("08B112345", "08B1-12345"))

    def test_normalize_plate_rejects_invalid_strings(self):
        self.assertIsNone(main.normalize_plate(""))
        self.assertIsNone(main.normalize_plate("123"))
        self.assertIsNone(main.normalize_plate("ABCDEFGHIJK"))
        self.assertIsNone(main.normalize_plate("59-12"))

    def test_deduplicate_and_assemble_plate_text(self):
        # 2 ký tự trùng vị trí (IoU > 0.55) -> giữ ký tự có confidence cao hơn
        raw_chars = [
            (10.0, 10.0, "5", 0.95, (0, 0, 20, 30)),
            (11.0, 10.0, "S", 0.60, (1, 0, 21, 30)),  # trùng box với '5'
            (35.0, 10.0, "9", 0.92, (25, 0, 45, 30)),
            (60.0, 10.0, "V", 0.91, (50, 0, 70, 30)),
            (85.0, 10.0, "1", 0.90, (75, 0, 95, 30)),
            # Dòng dưới (y = 55)
            (15.0, 55.0, "7", 0.94, (5, 40, 25, 70)),
            (40.0, 55.0, "9", 0.93, (30, 40, 50, 70)),
            (65.0, 55.0, "3", 0.92, (55, 40, 75, 70)),
            (90.0, 55.0, "7", 0.91, (80, 40, 100, 70)),
            (115.0, 55.0, "9", 0.95, (105, 40, 125, 70)),
        ]
        deduped = main._deduplicate_chars(raw_chars)
        self.assertEqual(len(deduped), 9)
        assembled = main._assemble_plate_text(deduped)
        self.assertEqual(assembled, "59V1-79379")

        # Biển 1 dòng ngang
        single_line = [
            (80.0, 12.0, "1", 0.90, (70, 0, 90, 24)),
            (10.0, 10.0, "5", 0.95, (0, 0, 20, 24)),
            (35.0, 11.0, "9", 0.92, (25, 0, 45, 24)),
            (60.0, 10.0, "A", 0.93, (50, 0, 70, 24)),
        ]
        self.assertEqual(main._assemble_plate_text(single_line), "59A1")


class TestMajorityVoting(unittest.TestCase):
    def test_get_vote_result_and_confirmation(self):
        self.assertIsNone(main.get_vote_result([]))
        self.assertFalse(main.is_vote_confirmed(None))

        # 2 mẫu chưa đủ VOTE_MIN_SAMPLES (3)
        obs_short = [
            (1.0, "59V179379", "59V1-79379"),
            (1.2, "59V179379", "59V1-79379"),
        ]
        res_short = main.get_vote_result(obs_short)
        self.assertFalse(main.is_vote_confirmed(res_short))

        # 4 mẫu: 3 mẫu giống nhau (75% >= 70%) -> confirmed
        obs_valid = [
            (1.0, "59V179379", "59V1-79379"),
            (1.2, "59V179379", "59V1-79379"),
            (1.4, "59V179378", "59V1-79378"),
            (1.6, "59V179379", "59V1-79379"),
        ]
        res_valid = main.get_vote_result(obs_valid)
        self.assertEqual(res_valid[0], "59V179379")
        self.assertEqual(res_valid[1], "59V1-79379")
        self.assertEqual(res_valid[2], 3)
        self.assertAlmostEqual(res_valid[3], 0.75)
        self.assertTrue(main.is_vote_confirmed(res_valid))


class TestFaceEmbeddings(unittest.TestCase):
    def test_cosine_similarity_and_serialization(self):
        vec = [float(i % 7) + 0.5 for i in range(face_service.EMBEDDING_SIZE)]
        raw = face_service.embedding_to_bytes(vec)
        restored = face_service.embedding_from_bytes(raw)
        self.assertIsNotNone(restored)
        self.assertEqual(len(restored), 512)
        self.assertAlmostEqual(face_service.cosine_similarity(vec, restored), 1.0, places=5)
        self.assertAlmostEqual(face_service.cosine_similarity(vec, [-v for v in vec]), -1.0, places=5)
        self.assertEqual(face_service.cosine_similarity([0.0] * 512, vec), 0.0)
        self.assertIsNone(face_service.embedding_from_bytes(b"invalid_short_bytes"))


class TestSystemStateRegressions(unittest.TestCase):
    def test_get_cached_overview_preserves_summary_on_midflight_version_bump(self):
        """Regression Bước 1.2:
        Khi need_summary == False và records_version tăng giữa chừng trong lúc fetch_overview đang chạy,
        kết quả trả về vẫn phải gắn đầy đủ stats & revenue từ cached_summary (không bao giờ trả về None).
        """
        st = main.SystemState()
        st.database_ready = True
        today_str = database.now_vn().strftime("%Y-%m-%d")
        st.overview_cache_date = today_str
        st.records_version = 5
        st.overview_summary_cache[(today_str, 5)] = {
            "stats": {"total_records": 42, "in_parking": 6},
            "revenue": {"unit_price": 2000, "total": {"tickets": 25, "revenue": 50000}},
        }

        def fake_fetch_overview(q, status, **kwargs):
            # Giả lập một lượt xe mới vừa ghi xong làm tăng records_version từ 5 lên 6 giữa lúc đang query
            st.records_version = 6
            return {
                "stats": None,
                "revenue": None,
                "matched": 1,
                "records": [{"ID": 42, "Biển số": "59V1-79379"}],
            }

        with mock.patch("main.fetch_overview", side_effect=fake_fetch_overview):
            out = st.get_cached_overview("59V1", "all", page=1, page_size=10)

        self.assertIsNotNone(out["stats"], "stats must not be None when version bumps mid-query")
        self.assertIsNotNone(out["revenue"], "revenue must not be None when version bumps mid-query")
        self.assertEqual(out["stats"]["total_records"], 42)
        self.assertEqual(out["revenue"]["unit_price"], 2000)
        self.assertEqual(len(st.overview_cache), 0, "Stale version response must not pollute new cache")
        st.stop_db_writer()

    def test_resolve_security_alert_preserves_alert_on_db_error(self):
        """Regression Bước 1.3:
        Khi bấm 'Cho phép ra' nhưng MySQL lỗi, phải giữ lại self.security_alert để bảo vệ bấm duyệt lại được.
        Khi MySQL thành công thì xóa self.security_alert và đặt cooldown.
        """
        st = main.SystemState()
        st.security_alert = {
            "plate_key": "30T41975",
            "plate_number": "30T4-1975",
            "entry_time": "2026-11-23 08:00:00",
            "match_score_pct": "45%",
            "record": {
                "_seq": 10,
                "plate_number": "30T4-1975",
                "direction": "OUT",
                "recognized_at": database.now_vn(),
                "vote_count": 4,
                "sample_count": 4,
                "consensus_rate": 1.0,
                "face_detected": True,
                "face_confidence": 0.95,
                "camera_index": 0,
            },
        }

        # Lần 1: MySQL mất kết nối -> trả db_error, giữ nguyên security_alert, không đặt cooldown
        with mock.patch(
            "main.insert_plate_record",
            side_effect=DatabaseOperationError("MySQL connection lost"),
        ):
            res_err = st.resolve_security_alert(approve=True)

        self.assertEqual(res_err["status"], "db_error")
        self.assertIsNotNone(st.security_alert, "security_alert must be preserved when DB write fails")
        self.assertFalse(st.alert_resolving)
        self.assertNotIn("30T41975:OUT", st.recent_confirms)

        # Lần 2: MySQL phục hồi -> bấm duyệt lại thành công
        with mock.patch("main.insert_plate_record", return_value=(99, 0.45)):
            res_ok = st.resolve_security_alert(approve=True)

        self.assertEqual(res_ok["status"], "approved")
        self.assertIsNone(st.security_alert, "security_alert must be cleared after DB commit succeeds")
        self.assertIn("30T41975:OUT", st.recent_confirms)
        st.stop_db_writer()

    def test_commit_latched_pair_async_executor_and_committing_plates(self):
        """Regression Bước 2.1:
        _commit_latched_pair() với async_db=True đẩy việc ghi DB sang commit_executor,
        khóa biển số trong committing_plates suốt thời gian chờ MySQL và gỡ khóa + báo thành công khi hoàn tất.
        """
        st = main.SystemState()
        st.session_id = 11

        class DummyFaceService:
            can_embed = True

            def embed_face(self, frame, box):
                return [0.1] * 512

        st.face_service = DummyFaceService()
        dummy_frame = np.zeros((80, 80, 3), dtype=np.uint8)
        best_face = (0.95, 0.96, dummy_frame, (10, 10, 50, 50), 26.0)
        rec = {
            "_session_id": 11,
            "_plate_key": "59V179379",
            "_active_session": None,
            "plate_number": "59V1-79379",
            "direction": "IN",
            "recognized_at": database.now_vn(),
            "vote_count": 4,
            "sample_count": 4,
            "consensus_rate": 1.0,
            "face_detected": True,
            "face_confidence": 0.96,
            "camera_index": 0,
        }

        entered_db = threading.Event()
        release_db = threading.Event()

        def slow_insert(record_arg):
            entered_db.set()
            release_db.wait(timeout=3.0)
            return (123, None)

        with mock.patch("main.insert_plate_record", side_effect=slow_insert), mock.patch(
            "main._save_snapshot_to_disk"
        ):
            st._commit_latched_pair(dict(rec), best_face, async_db=True)
            self.assertTrue(entered_db.wait(timeout=2.0), "Background DB task did not start")
            # Trong lúc MySQL đang ghi, biển số phải nằm trong committing_plates và chưa báo thành công sớm
            self.assertIn("59V179379", st.committing_plates)
            self.assertIsNone(st.gate_feedback)
            release_db.set()
            st.stop_db_writer()

        self.assertIsNotNone(st.gate_feedback)
        self.assertEqual(st.gate_feedback["type"], "success")
        self.assertIn("VÀO BÃI THÀNH CÔNG", st.gate_feedback["message"])
        self.assertIn("59V179379:IN", st.recent_confirms)
        self.assertNotIn("59V179379", st.committing_plates)

    def test_stop_cameras_does_not_drop_inflight_commit(self):
        """Regression Critical:
        Nếu người dùng bấm 'Tắt tất cả' (hoặc tắt server gọi stop_cameras() làm tăng session_id)
        đúng lúc bản ghi đã xác thực đang nằm trong commit_executor, bản ghi vẫn bắt buộc được ghi vào MySQL.
        """
        st = main.SystemState()
        st.start_camera(1)
        st.session_id = 20

        class DummyFaceService:
            can_embed = True

            def embed_face(self, frame, box):
                return [0.2] * 512

        st.face_service = DummyFaceService()
        dummy_frame = np.zeros((80, 80, 3), dtype=np.uint8)
        best_face = (0.95, 0.96, dummy_frame, (10, 10, 50, 50), 26.0)
        rec = {
            "_session_id": 20,
            "_plate_key": "30T41975",
            "_active_session": None,
            "plate_number": "30T4-1975",
            "direction": "IN",
            "recognized_at": database.now_vn(),
            "vote_count": 4,
            "sample_count": 4,
            "consensus_rate": 1.0,
            "face_detected": True,
            "face_confidence": 0.96,
            "camera_index": 0,
        }

        blocker_started = threading.Event()
        release_blocker = threading.Event()
        insert_calls = []

        def hold_executor():
            blocker_started.set()
            release_blocker.wait(timeout=3.0)

        def tracked_insert(record_arg):
            insert_calls.append(record_arg["plate_number"])
            return (555, None)

        with mock.patch("main.insert_plate_record", side_effect=tracked_insert), mock.patch(
            "main._save_snapshot_to_disk"
        ):
            # Giữ worker của commit_executor để bản ghi _finalize_db_commit nằm chờ trong queue
            st.commit_executor.submit(hold_executor)
            self.assertTrue(blocker_started.wait(timeout=2.0))
            st._commit_latched_pair(dict(rec), best_face, async_db=True)
            self.assertIn("30T41975", st.committing_plates)
            # Bấm tắt camera (làm tăng session_id từ 20 lên 21) trước khi _finalize_db_commit chạy
            st.stop_cameras()
            self.assertEqual(st.session_id, 21)
            release_blocker.set()
            st.stop_db_writer()

        self.assertEqual(insert_calls, ["30T4-1975"], "In-flight authenticated record must not be dropped on stop_cameras()")
        self.assertNotIn("30T41975", st.committing_plates)

    def test_zero_db_revenue_tab_when_summary_cached(self):
        """Regression Hiệu năng:
        Khi tab Doanh thu gọi get_cached_overview(..., include_records=False) và overview_summary_cache đã ấm,
        trả về ngay từ RAM mà không gọi fetch_overview / kết nối MySQL.
        """
        st = main.SystemState()
        st.database_ready = True
        today_str = database.now_vn().strftime("%Y-%m-%d")
        st.overview_cache_date = today_str
        st.records_version = 9
        st.overview_summary_cache[(today_str, 9)] = {
            "stats": {"total_records": 100, "in_parking": 12},
            "revenue": {"unit_price": 2000, "total": {"tickets": 60, "revenue": 120000}},
        }

        with mock.patch("main.fetch_overview") as mock_fetch:
            res = st.get_cached_overview("", "all", include_records=False)
            mock_fetch.assert_not_called()

        self.assertEqual(res["stats"]["total_records"], 100)
        self.assertEqual(res["revenue"]["total"]["revenue"], 120000)
        self.assertEqual(res["records"], [])
        st.stop_db_writer()

    def test_connect_mysql_closes_leaked_conn_on_ping_failure(self):
        """Regression Pool Leak:
        Khi pool.get_connection() trả về kết nối bị ngắt và conn.ping() ném MySQLError,
        phải gọi conn.close() để trả slot về pool rồi mới fallback sang mysql.connector.connect().
        """
        leaked_conn = mock.MagicMock()
        leaked_conn.ping.side_effect = database.MySQLError("Server has gone away")
        fresh_conn = mock.MagicMock()

        fake_pool = mock.MagicMock()
        fake_pool.get_connection.return_value = leaked_conn
        fake_cfg = {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "pw",
            "database": "defaultdb",
        }
        cfg_key = ("localhost", 3306, "root", "pw", "defaultdb")

        with mock.patch("database._connection_config", return_value=fake_cfg), mock.patch.object(
            database, "_MYSQL_POOL", fake_pool
        ), mock.patch.object(database, "_POOL_CONFIG_KEY", cfg_key), mock.patch(
            "database.mysql.connector.connect", return_value=fresh_conn
        ) as mock_direct_connect:
            conn = database._connect_mysql()

        self.assertIs(conn, fresh_conn)
        leaked_conn.close.assert_called_once()
        mock_direct_connect.assert_called_once()


if __name__ == "__main__":
    unittest.main()

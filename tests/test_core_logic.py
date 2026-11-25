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

    def test_fast_confirm_two_high_confidence_samples(self):
        # 2 mẫu liên tiếp cùng biển số chuẩn + avg_char_conf >= 0.75 -> Fast-Confirm ngay ở mẫu thứ 2
        obs_fast = [
            (1.0, "59V179379", "59V1-79379", 0.86),
            (1.15, "59V179379", "59V1-79379", 0.89),
        ]
        res_fast = main.get_vote_result(obs_fast)
        self.assertTrue(main.is_vote_confirmed(res_fast, obs_fast))

        # 2 mẫu liên tiếp nhưng độ tin cậy ký tự thấp (< 0.75) -> chưa chốt sớm, phải đợi đủ 3 mẫu
        obs_low_conf = [
            (1.0, "59V179379", "59V1-79379", 0.62),
            (1.15, "59V179379", "59V1-79379", 0.68),
        ]
        res_low = main.get_vote_result(obs_low_conf)
        self.assertFalse(main.is_vote_confirmed(res_low, obs_low_conf))

        # 2 mẫu khác biển số -> không bao giờ chốt sớm
        obs_conflict = [
            (1.0, "59V179379", "59V1-79379", 0.92),
            (1.15, "59V179378", "59V1-79378", 0.92),
        ]
        res_conflict = main.get_vote_result(obs_conflict)
        self.assertFalse(main.is_vote_confirmed(res_conflict, obs_conflict))


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

        # Lần 2: MySQL phục hồi -> bấm duyệt lại thành công, kèm sẵn camera_status và khóa chiều ngược 6.0s
        self.assertEqual(main.CROSS_DIRECTION_COOLDOWN_SECONDS, 6.0)
        with mock.patch("main.insert_plate_record", return_value=(99, 0.45)):
            res_ok = st.resolve_security_alert(approve=True)

        self.assertEqual(res_ok["status"], "approved")
        self.assertIn("camera_status", res_ok)
        self.assertIsNone(res_ok["camera_status"]["security_alert"])
        self.assertIsNone(st.security_alert, "security_alert must be cleared after DB commit succeeds")
        self.assertIn("30T41975:OUT", st.recent_confirms)

        # Kiểm tra nút Từ chối (approve=False) trả kèm camera_status ngay trong 1 vòng
        st.security_alert = {
            "plate_key": "59A112345",
            "plate_number": "59A1-12345",
            "entry_time": "2026-11-23 09:00:00",
            "match_score_pct": "32%",
            "record": {"plate_number": "59A1-12345", "direction": "OUT"},
        }
        res_rej = st.resolve_security_alert(approve=False)
        self.assertEqual(res_rej["status"], "rejected")
        self.assertIn("camera_status", res_rej)
        self.assertIsNone(res_rej["camera_status"]["security_alert"])
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

    def test_direct_connect_mysql_timeouts_and_error_wrapping(self):
        """Kiểm chứng kết nối trực tiếp MySQL (không dùng Pool tránh treo socket qua đêm):
        - Cấu hình luôn gắn đủ connection_timeout=8, read_timeout=10, write_timeout=10.
        - _connect_mysql() gọi thẳng mysql.connector.connect(**config) và bọc MySQLError thành DatabaseOperationError.
        """
        with mock.patch.dict(
            "os.environ",
            {
                "MYSQL_HOST": "localhost",
                "MYSQL_PORT": "3306",
                "MYSQL_USER": "root",
                "MYSQL_PASSWORD": "pw",
                "MYSQL_DATABASE": "defaultdb",
            },
            clear=False,
        ):
            cfg = database._connection_config()
            self.assertEqual(cfg["connection_timeout"], 8)
            self.assertEqual(cfg["read_timeout"], 10)
            self.assertEqual(cfg["write_timeout"], 10)

            fresh_conn = mock.MagicMock()
            with mock.patch(
                "database.mysql.connector.connect", return_value=fresh_conn
            ) as mock_connect:
                conn = database._connect_mysql()
                self.assertIs(conn, fresh_conn)
                mock_connect.assert_called_once_with(**cfg)

            with mock.patch(
                "database.mysql.connector.connect",
                side_effect=database.MySQLError("Connection refused"),
            ):
                with self.assertRaises(DatabaseOperationError):
                    database._connect_mysql()

    def test_fetch_overview_skips_revenue_and_count_queries_on_history_tab(self):
        """Kiểm chứng giảm vòng mạng tab Lịch sử & Phân trang:
        - Mở tab Lịch sử (include_revenue=False, q=''): chỉ chạy 2 câu SQL (stats + SELECT page), bỏ 4 câu revenue và bỏ SELECT COUNT(*).
        - Sang Trang 2 (known_stats có sẵn, include_stats=False, include_revenue=False): chỉ chạy đúng 1 câu SQL SELECT page.
        """
        executed_sqls = []
        fake_cursor = mock.MagicMock()

        def track_execute(sql, params=None):
            executed_sqls.append(" ".join(sql.split()))

        fake_cursor.execute.side_effect = track_execute
        fake_cursor.fetchone.return_value = {
            "total": 25,
            "today": 8,
            "in_parking": 7,
            "total_in": 16,
            "total_out": 9,
        }
        fake_cursor.fetchall.return_value = []

        with mock.patch(
            "database._run_read_query", side_effect=lambda fn: fn(fake_cursor)
        ), mock.patch("database._fetch_revenue_report_mysql") as mock_rev:
            res_p1 = database.fetch_overview(
                query="",
                status_filter="in_parking",
                page=1,
                page_size=10,
                include_records=True,
                include_stats=True,
                include_revenue=False,
            )
            mock_rev.assert_not_called()
            self.assertEqual(res_p1["matched"], 7)
            self.assertIsNone(res_p1["revenue"])
            self.assertEqual(
                len(executed_sqls),
                2,
                f"Expected exactly 2 SQL queries (stats + page), got: {executed_sqls}",
            )

            # Sang trang 2 khi đã có stats trong cache -> chỉ tốn đúng 1 câu SQL
            executed_sqls.clear()
            res_p2 = database.fetch_overview(
                query="",
                status_filter="all",
                page=2,
                page_size=10,
                include_records=True,
                include_stats=False,
                include_revenue=False,
                known_stats=res_p1["stats"],
            )
            self.assertEqual(res_p2["matched"], 25)
            self.assertEqual(res_p2["page"], 2)
            self.assertEqual(
                len(executed_sqls),
                1,
                f"Expected 1 SQL query on cached stats pagination, got: {executed_sqls}",
            )

    def test_session_case_short_circuits_in_parking_and_caches_by_version(self):
        """Kiểm chứng Modal Hồ sơ Mất xe:
        - Dòng IN đang IN_PARKING chỉ chạy đúng 1 câu SELECT theo ID (bỏ 3 câu tìm OUT).
        - SystemState.get_cached_session_case() lưu cache theo records_version và tự xóa khi _bump_version().
        """
        executed_sqls = []
        fake_cursor = mock.MagicMock()
        fake_cursor.execute.side_effect = lambda sql, params=None: executed_sqls.append(sql)
        fake_cursor.fetchone.return_value = {
            "id": 230,
            "plate_number": "72C1-60266",
            "plate_key": "72C160266",
            "direction": "IN",
            "parking_status": "IN_PARKING",
            "entry_record_id": None,
            "fee_amount": 2000,
            "recognized_at": database.now_vn(),
            "vote_count": 4,
            "sample_count": 4,
            "consensus_rate": 1.0,
            "face_detected": 1,
            "face_confidence": 0.98,
            "face_embedding": 1,
            "face_match_score": None,
            "plate_image": None,
            "face_image": None,
            "camera_index": 0,
        }

        with mock.patch("database._run_read_query", side_effect=lambda fn: fn(fake_cursor)):
            case_res = database.fetch_parking_session_case(230)

        self.assertEqual(len(executed_sqls), 1, "IN_PARKING must short-circuit after 1 query")
        self.assertEqual(case_res["plate_number"], "72C1-60266")
        self.assertIsNone(case_res["checkout_row"])
        self.assertEqual(case_res["in_parking_status"], "IN_PARKING")

        st = main.SystemState()
        with mock.patch(
            "main.fetch_parking_session_case", return_value=case_res
        ) as mock_fetch_case:
            c1 = st.get_cached_session_case(230)
            c2 = st.get_cached_session_case(230)
            self.assertEqual(c1["target_id"], 230)
            self.assertEqual(c2["target_id"], 230)
            mock_fetch_case.assert_called_once_with(230)

            st._bump_version()
            st.get_cached_session_case(230)
            self.assertEqual(mock_fetch_case.call_count, 2)
        st.stop_db_writer()

    def test_dual_cam_batched_yolo_and_two_frame_instant_commit(self):
        """Kiểm chứng gói tăng tốc nhận diện 2 Camera:
        - Khung 1: gọi batch plate_model.predict([frame1, frame2]) trong 1 lần duy nhất; Cam 1 ghi nhận mẫu 1, Cam 2 lưu sẵn mặt nét.
        - Khung 2: phối hợp 2 Cam bỏ qua quét biển dư thừa ở Cam 2, Cam 1 đủ 2 mẫu Fast-Confirm và chốt mặt tức thì ngay trong Khung 2 (0 frame chờ thêm ở Lưu hờ).
        """
        st = main.SystemState()
        st.database_ready = True
        st.start_camera(1)
        st.start_camera(2)
        sid = st.session_id

        predict_inputs = []

        class FakePlateResult:
            def __init__(self, has_plate: bool):
                self.boxes = ["dummy_box"] if has_plate else []

        class FakePlateModel:
            def predict(self, source, **kwargs):
                predict_inputs.append(source)
                if isinstance(source, list):
                    return [FakePlateResult(True), FakePlateResult(False)]
                return [FakePlateResult(True)]

        class FakeFaceService:
            can_embed = True

            def detect_from_bgr(self, frame):
                return [face_service.FaceData(box=(10, 10, 90, 90), confidence=0.91)]

            def embed_face(self, frame, box):
                return [0.25] * 512

        st.plate_model = FakePlateModel()
        st.char_model = mock.MagicMock()
        st.face_service = FakeFaceService()

        # Tạo khung hình có vân kẻ cờ vua để độ sắc nét Laplacian > 22.0 (đạt chuẩn chốt tức thì)
        sharp_frame = np.zeros((120, 120, 3), dtype=np.uint8)
        sharp_frame[::2, ::2] = 255
        frame1 = sharp_frame.copy()
        frame2 = sharp_frame.copy()

        def fake_extract(frame, result, char_model):
            if result.boxes:
                return (
                    True,
                    {"59V179379": "59V1-79379"},
                    [{"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.4, "label": "59V1-79379", "valid": True}],
                    {"59V179379": (40.0, "data:image/jpeg;base64,AA==")},
                    {"59V179379": 0.88},
                )
            return False, {}, [], {}, {}

        insert_done = threading.Event()

        def fast_insert(rec):
            insert_done.set()
            return (777, None)

        clock = [100.0]
        with mock.patch("main._extract_plates_from_result", side_effect=fake_extract), mock.patch(
            "main.find_active_parking_session", return_value=None
        ), mock.patch("main.insert_plate_record", side_effect=fast_insert), mock.patch(
            "main._save_snapshot_to_disk"
        ), mock.patch("main.time.monotonic", side_effect=lambda: clock[0]):
            # Khung 1: gom batch 2 ảnh trong 1 lần gọi plate_model.predict
            st._process_dual_frames(sid, frame1, frame2)
            self.assertEqual(len(predict_inputs), 1)
            self.assertIsInstance(predict_inputs[0], list)
            self.assertEqual(len(predict_inputs[0]), 2)
            self.assertEqual(len(st.cams[1].observations), 1)
            self.assertEqual(len(st.cams[2].recent_faces), 1)

            # Khung 2 (+0.12s): bỏ qua quét biển ở Cam 2, Cam 1 chốt Fast-Confirm 2/2 + chốt mặt tức thì
            clock[0] = 100.12
            st._process_dual_frames(sid, frame1, frame2)
            self.assertEqual(len(predict_inputs), 2)
            self.assertNotIsInstance(
                predict_inputs[1], list, "Cam 2 plate OCR should be skipped while Cam 1 tracks plate"
            )
            self.assertIsNone(st.latched, "Must commit immediately in Frame 2 without lingering in latched state")
            self.assertTrue(insert_done.wait(timeout=2.0))
            st.stop_db_writer()
            status_payload = st.get_status_payload()

        self.assertFalse(status_payload["committing"])
        self.assertIsNotNone(status_payload["gate_feedback"])
        self.assertIn("VÀO BÃI THÀNH CÔNG", status_payload["gate_feedback"]["message"])

    def test_warm_database_mirror_zero_db_reads_and_live_sync(self):
        """Kiểm chứng WarmDatabaseMirror:
        - Sau 1 lần nạp ban đầu, mọi thao tác Lịch sử / Tìm kiếm / Phân trang / Doanh thu / Hồ sơ mất xe / Kiểm tra IN_PARKING
          đều trả về tức thì từ RAM (0 truy vấn SQL sang Aiven), kể cả ngay sau khi có lượt xe mới vào/ra.
        """
        st = main.SystemState()
        st.database_ready = True
        fake_cursor = mock.MagicMock()
        fake_cursor.fetchall.side_effect = [[], []]  # meta_rows=[], active_rows=[]
        st.warm_mirror.load_from_cursor(fake_cursor)
        self.assertTrue(st.warm_mirror.ready)

        emb_vec = [0.2] * 512
        now_dt = database.now_vn()

        with mock.patch("main.insert_plate_record") as mock_insert, mock.patch(
            "main.fetch_overview"
        ) as mock_fetch_ov, mock.patch(
            "main.fetch_parking_session_case"
        ) as mock_fetch_case, mock.patch(
            "main.find_active_parking_session"
        ) as mock_find_act:
            # 1) Xe VÀO BÃI -> commit lên MySQL rồi cập nhật thẳng vào WarmDatabaseMirror
            mock_insert.return_value = (101, None)
            rec_in = {
                "plate_number": "72C1-60266",
                "direction": "IN",
                "fee_amount": 2000,
                "recognized_at": now_dt,
                "vote_count": 3,
                "sample_count": 3,
                "consensus_rate": 1.0,
                "face_detected": True,
                "face_confidence": 0.96,
                "face_embedding": emb_vec,
                "plate_image": "data:image/jpeg;base64,INPLATE",
                "face_image": "data:image/jpeg;base64,INFACE",
                "camera_index": 0,
            }
            self.assertTrue(st._store_record(rec_in))

            # Kiểm tra IN_PARKING từ RAM (0 query MySQL)
            act_sess, db_ok = st._get_active_parking_session("72C1-60266")
            self.assertTrue(db_ok)
            self.assertIsNotNone(act_sess)
            self.assertEqual(act_sess["id"], 101)
            mock_find_act.assert_not_called()

            # Xem Lịch sử & Doanh thu ngay sau khi xe vào -> 0 query MySQL
            ov_in = st.get_cached_overview("", "in_parking", page=1, page_size=10, include_revenue=True)
            self.assertEqual(ov_in["stats"]["in_parking"], 1)
            self.assertEqual(ov_in["revenue"]["today"]["revenue"], 2000)
            self.assertEqual(ov_in["matched"], 1)
            self.assertEqual(ov_in["records"][0]["ID"], 101)
            mock_fetch_ov.assert_not_called()

            # 2) Xe RA BÃI -> commit lên MySQL rồi đóng phiên IN_PARKING ngay trên RAM
            mock_insert.return_value = (102, 0.89)
            rec_out = {
                "plate_number": "72C1-60266",
                "direction": "OUT",
                "entry_record_id": 101,
                "fee_amount": 0,
                "recognized_at": now_dt,
                "vote_count": 2,
                "sample_count": 2,
                "consensus_rate": 1.0,
                "face_detected": True,
                "face_confidence": 0.95,
                "face_embedding": emb_vec,
                "face_match_score": 0.89,
                "plate_image": "data:image/jpeg;base64,OUTPLATE",
                "face_image": "data:image/jpeg;base64,OUTFACE",
                "camera_index": 1,
            }
            self.assertTrue(st._store_record(rec_out))

            act_after_out, _ = st._get_active_parking_session("72C1-60266")
            self.assertIsNone(act_after_out)
            mock_find_act.assert_not_called()

            # Mở Modal Hồ sơ Mất xe ở cả dòng IN (#101) lẫn dòng OUT (#102) -> 0 query MySQL, đủ cả 2 chiều
            case_from_in = st.get_cached_session_case(101)
            case_from_out = st.get_cached_session_case(102)
            self.assertEqual(case_from_in["checkin_row"]["ID"], 101)
            self.assertEqual(case_from_in["checkout_row"]["ID"], 102)
            self.assertEqual(case_from_out["checkin_row"]["ID"], 101)
            self.assertEqual(case_from_out["checkout_row"]["ID"], 102)
            mock_fetch_case.assert_not_called()
            mock_fetch_ov.assert_not_called()

        st.stop_db_writer()


if __name__ == "__main__":
    unittest.main()

import sys
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
        _commit_latched_pair() đẩy việc ghi DB sang commit_executor, chặn biển số trong committing_plates
        và chỉ báo thành công sau khi MySQL commit hoàn tất.
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
            "_seq": 1,
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

        with mock.patch("main.insert_plate_record", return_value=(123, None)):
            st._commit_latched_pair(dict(rec), best_face, async_db=False)

        self.assertIsNotNone(st.gate_feedback)
        self.assertEqual(st.gate_feedback["type"], "success")
        self.assertIn("VÀO BÃI THÀNH CÔNG", st.gate_feedback["message"])
        self.assertIn("59V179379:IN", st.recent_confirms)
        self.assertNotIn("59V179379", st.committing_plates)
        st.stop_db_writer()


if __name__ == "__main__":
    unittest.main()

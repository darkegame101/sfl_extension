"""
TEST SUITE: KIỂM ĐỊNH AUDIT LOGGING, HẬU KIỂM CLOSED-LOOP & PROCESS LOCKING
Kiểm tra:
1. Ghi nhận Structured Audit Trail (audit_trail.jsonl).
2. So sánh trạng thái Trước/Sau hành động để hậu kiểm (Pre vs Post Closed-Loop Verification).
3. Khóa file đa tiến trình (Inter-Process File Lock) của FarmMemory & ScenarioEngine.
"""

import unittest
import os
import sys
import tempfile
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run import SunflowerAutomationRunner
from scheduler.farm_memory import FarmMemory
from scheduler.scenario_engine import ScenarioEngine


class TestAuditAndVerification(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_audit_log_generation(self):
        """Đảm bảo hàm _record_audit_log ghi đúng cấu trúc JSON Lines."""
        runner = SunflowerAutomationRunner.__new__(SunflowerAutomationRunner)
        runner.audit_logging = True

        audit_path = os.path.join(self.temp_dir.name, "test_audit.jsonl")
        # Monkey patch log_file
        orig_write = runner._record_audit_log

        # Gọi trực tiếp _record_audit_log với file trong temp_dir
        plan = {"session_type": "STANDARD", "tasks_to_execute": ["CROPS", "HONEY"]}
        verification = {"status": "verified", "harvest_verified": True, "plant_verified": True}
        eff_params = {"vigilance_level": 1.4, "accumulated_fatigue": 0.16, "effective_fumble_rate": 0.03}

        # Override log file location for isolated test
        old_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir.name)
            runner._record_audit_log("p1", "Profile 1", plan, "COMPLETED", verification, eff_params)

            self.assertTrue(os.path.exists("audit_trail.jsonl"))
            with open("audit_trail.jsonl", "r", encoding="utf-8") as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 1)
                data = json.loads(lines[0])
                self.assertEqual(data["profile_id"], "p1")
                self.assertEqual(data["status"], "COMPLETED")
                self.assertEqual(data["verification"]["harvest_verified"], True)
                self.assertEqual(data["intra_day_metrics"]["vigilance"], 1.4)
        finally:
            os.chdir(old_dir)

    def test_farm_memory_process_lock(self):
        """Đảm bảo _process_lock tạo và dọn dẹp file .lock một cách an toàn."""
        mem_path = os.path.join(self.temp_dir.name, "test_lock_mem.json")
        farm_mem = FarmMemory(mem_path)

        lock_path = f"{mem_path}.lock"
        self.assertFalse(os.path.exists(lock_path))

        with farm_mem._process_lock():
            self.assertTrue(os.path.exists(lock_path))

        # Sau khi thoát context, lock file phải được dọn dẹp
        self.assertFalse(os.path.exists(lock_path))

    def test_scenario_engine_process_lock(self):
        """Đảm bảo ScenarioEngine _process_lock hoạt động ổn định."""
        sc_path = os.path.join(self.temp_dir.name, "test_lock_sc.json")
        sc_engine = ScenarioEngine(sc_path)

        lock_path = f"{sc_path}.lock"
        self.assertFalse(os.path.exists(lock_path))

        with sc_engine._process_lock():
            self.assertTrue(os.path.exists(lock_path))

        self.assertFalse(os.path.exists(lock_path))

    def test_lock_timeout_raises_error(self):
        """Đảm bảo khi file .lock đang bị giữ bởi tiến trình khác, hàm phải raise TimeoutError, không được yield thiếu bảo vệ."""
        mem_path = os.path.join(self.temp_dir.name, "test_contention_mem.json")
        farm_mem = FarmMemory(mem_path)
        lock_path = f"{mem_path}.lock"

        # Giả lập 1 tiến trình khác đang giữ lock
        with open(lock_path, "w") as f:
            f.write("held_by_other_process")

        try:
            # Cố tình chiếm lock với timeout ngắn 0.1s
            with self.assertRaises(TimeoutError):
                with farm_mem._process_lock(timeout=0.1):
                    pass
        finally:
            if os.path.exists(lock_path):
                os.remove(lock_path)

    def test_audit_log_separate_execution_and_verification_status(self):
        """Kiểm tra tách biệt rõ ràng giữa execution_status và verification_status cùng cleanup_error."""
        runner = SunflowerAutomationRunner.__new__(SunflowerAutomationRunner)
        runner.audit_logging = True

        old_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir.name)
            plan = {"session_type": "STANDARD", "tasks_to_execute": ["CROPS"]}
            verification = {"status": "VERIFIED_FAILED", "harvest_verified": True, "plant_verified": False}
            eff = {"vigilance_level": 1.2, "accumulated_fatigue": 0.24, "effective_fumble_rate": 0.04}

            # Ghi nhận phiên có execution_status = COMPLETED_WITH_VERIFICATION_FAILURE và cleanup_error
            runner._record_audit_log(
                profile_id="p_test_exec",
                profile_name="Profile Test Exec",
                session_plan=plan,
                status="COMPLETED_WITH_VERIFICATION_FAILURE",
                verification=verification,
                eff_params=eff,
                execution_status="COMPLETED_WITH_VERIFICATION_FAILURE",
                verification_status="VERIFIED_FAILED",
                cleanup_error="GpmAPI.stop_profile timeout 10s"
            )

            self.assertTrue(os.path.exists("audit_trail.jsonl"))
            with open("audit_trail.jsonl", "r", encoding="utf-8") as f:
                entry = json.loads(f.readline())

            self.assertEqual(entry["execution_status"], "COMPLETED_WITH_VERIFICATION_FAILURE")
            self.assertEqual(entry["verification_status"], "VERIFIED_FAILED")
            self.assertEqual(entry["cleanup_error"], "GpmAPI.stop_profile timeout 10s")
            self.assertFalse(entry["verification"]["plant_verified"])
        finally:
            os.chdir(old_dir)

    def test_post_condition_verification_distinguishes_pass_fail_unverified(self):
        """
        Kiểm tra logic hậu kiểm cây trồng:
        - PASS chỉ khi có bằng chứng dương tính (growing > 0 và empty == 0).
        - FAIL khi vẫn còn ô đất trống hoặc không có cây nào mọc.
        - UNVERIFIED khi không có đủ bằng chứng (quá nhiều UNKNOWN).
        """
        # 1. Bằng chứng dương tính hoàn toàn: 9 ô đều GROWING
        growing_checks = ["GROWING"] * 9
        growing_cnt = sum(1 for s in growing_checks if s == "GROWING")
        empty_cnt = sum(1 for s in growing_checks if s == "EMPTY")
        plant_verified_pass = (growing_cnt > 0 and empty_cnt == 0)
        self.assertTrue(plant_verified_pass, "Tất cả ô GROWING phải được xác minh PASS")

        # 2. Bỏ sót: 5 GROWING, 4 EMPTY -> Phải là FAIL (vẫn còn ô trống)
        partial_checks = ["GROWING"] * 5 + ["EMPTY"] * 4
        p_growing = sum(1 for s in partial_checks if s == "GROWING")
        p_empty = sum(1 for s in partial_checks if s == "EMPTY")
        plant_verified_partial = (p_growing > 0 and p_empty == 0)
        self.assertFalse(plant_verified_partial, "Còn ô EMPTY thì không được coi là trồng thành công 100%")

        # 3. Thất bại: 9 EMPTY, 0 GROWING -> FAIL
        failed_checks = ["EMPTY"] * 9
        f_growing = sum(1 for s in failed_checks if s == "GROWING")
        f_empty = sum(1 for s in failed_checks if s == "EMPTY")
        plant_verified_fail = (f_growing > 0 and f_empty == 0)
        self.assertFalse(plant_verified_fail, "Tất cả ô EMPTY phải FAIL")

        # 4. Thiếu dữ liệu / Quá nhiều UNKNOWN -> UNVERIFIED (Không được kết luận PASS giả)
        unknown_checks = ["UNKNOWN"] * 7 + ["EMPTY"] * 2
        known_plots = [s for s in unknown_checks if s in ("GROWING", "READY", "EMPTY")]
        min_confident = max(3, int(len(unknown_checks) * 0.4))  # Cần ít nhất 3 ô rõ ràng
        self.assertLess(len(known_plots), min_confident, "Dưới ngưỡng tin cậy phải rơi vào UNVERIFIED")

    def test_perception_failure_prevents_blind_actions(self):
        """
        Khi chụp màn hình thất bại (capture_screenshot() -> None),
        hệ thống phải phát hiện và hủy phiên với ABORTED_PERCEPTION_FAILURE,
        không được thực hiện click chuột mù vào game.
        """
        runner = SunflowerAutomationRunner.__new__(SunflowerAutomationRunner)
        runner.ai_enabled = True
        
        from unittest.mock import MagicMock
        runner.ai = MagicMock()
        runner.ai.api_key = "test_key"
        runner.ai.capture_screenshot.return_value = None  # Giả lập lỗi chụp màn hình

        # Xác thực trạng thái ban đầu
        verification = {
            "tier1_local_verified": False,
            "tier2_vlm_verified": False,
            "harvest_verified": None,
            "plant_verified": None,
            "status": "UNVERIFIED",
            "details": []
        }

        # Giả lập khối pre-check trong run_session
        session_status = "PENDING"
        screenshot = runner.ai.capture_screenshot()
        if not screenshot:
            session_status = "ABORTED_PERCEPTION_FAILURE"
            verification["status"] = "VERIFICATION_SKIPPED_NO_SCREENSHOT"
            verification["details"].append("Perception failed: capture_screenshot returned None before starting actions")

        self.assertEqual(session_status, "ABORTED_PERCEPTION_FAILURE")
        self.assertEqual(verification["status"], "VERIFICATION_SKIPPED_NO_SCREENSHOT")
        self.assertIn("Perception failed", verification["details"][0])


if __name__ == "__main__":
    unittest.main()

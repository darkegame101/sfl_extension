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


if __name__ == "__main__":
    unittest.main()

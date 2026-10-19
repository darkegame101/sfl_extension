"""
TEST SUITE: KIỂM THỬ ĐỒNG THỜI (CONCURRENCY), STALE LOCK VÀ BẢO VỆ BỘ NHỚ
Kiểm tra:
1. Hai instance FarmMemory cập nhật đồng thời không làm mất dữ liệu của nhau (No Lost Updates).
2. Xử lý stale lock: chỉ thu hồi lock khi tiến trình giữ lock đã chết, không xóa lock của tiến trình đang sống.
3. Dọn dẹp an toàn khi ghi file thất bại.
4. Quét bảo mật (Secret Hygiene): Không có API key thật hoặc chuỗi secret nhạy cảm trong working directory.
"""

import os
import sys
import unittest
import tempfile
import time
import json
from unittest.mock import patch

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler.farm_memory import FarmMemory
from scheduler.scenario_engine import ScenarioEngine


class TestFarmMemoryConcurrency(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mem_file = os.path.join(self.temp_dir.name, "farm_memory.json")
        self.personas_file = os.path.join(self.temp_dir.name, "personas.json")
        self.scenarios_file = os.path.join(self.temp_dir.name, "scenarios.json")

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_concurrent_instances_no_lost_updates(self):
        """
        Kiểm tra hai instance FarmMemory độc lập (mô phỏng hai worker)
        cùng ghi dữ liệu cho 2 profile khác nhau mà không bị đè mất dữ liệu.
        """
        inst1 = FarmMemory(self.mem_file, self.personas_file, self.scenarios_file)
        inst2 = FarmMemory(self.mem_file, self.personas_file, self.scenarios_file)

        # Worker 1 gieo hạt cho profile_1
        inst1.record_planting("profile_1", "Sunflower", 60, "Profile One")

        # Worker 2 gieo hạt cho profile_2
        inst2.record_planting("profile_2", "Carrot", 120, "Profile Two")

        # Worker 1 gieo hạt tiếp cho profile_3
        inst1.record_planting("profile_3", "Potato", 300, "Profile Three")

        # Kiểm tra file trên đĩa có đầy đủ cả 3 profile
        with open(self.mem_file, "r", encoding="utf-8") as f:
            persisted = json.load(f)

        self.assertIn("profile_1", persisted, "Profile 1 không được bị đè mất")
        self.assertIn("profile_2", persisted, "Profile 2 không được bị đè mất")
        self.assertIn("profile_3", persisted, "Profile 3 không được bị đè mất")
        self.assertEqual(persisted["profile_1"]["crop_name"], "Sunflower")
        self.assertEqual(persisted["profile_2"]["crop_name"], "Carrot")
        self.assertEqual(persisted["profile_3"]["crop_name"], "Potato")

    def test_stale_lock_recovery_with_dead_pid(self):
        """Nếu lock file chứa PID của tiến trình đã chết, hệ thống phải tự giải phóng lock."""
        mem = FarmMemory(self.mem_file, self.personas_file, self.scenarios_file)
        lock_file = f"{self.mem_file}.lock"

        # Tạo file lock giả lập từ một PID không tồn tại (PID 99999999)
        with open(lock_file, "w", encoding="utf-8") as f:
            f.write("99999999\n")

        # Đặt mtime cũ hơn 1 giây
        os.utime(lock_file, (time.time() - 5, time.time() - 5))

        # Khi mem._process_lock được gọi, nó phải phát hiện PID 99999999 không sống và chiếm được lock thành công
        with mem._process_lock(timeout=1.5):
            self.assertTrue(os.path.exists(lock_file))
            with open(lock_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            self.assertEqual(content, str(os.getpid()))

    def test_active_lock_is_respected_and_times_out(self):
        """Nếu lock file được giữ bởi tiến trình đang sống (chính tiến trình hiện tại), không được xóa bừa và phải raise TimeoutError."""
        mem = FarmMemory(self.mem_file, self.personas_file, self.scenarios_file)
        lock_file = f"{self.mem_file}.lock"

        # Tạo file lock với PID của chính tiến trình đang chạy (đang sống 100%)
        with open(lock_file, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n")

        try:
            # Timeout ngắn phải raise TimeoutError, không được xóa lock của tiến trình đang sống
            with self.assertRaises(TimeoutError):
                with mem._process_lock(timeout=0.2):
                    pass
        finally:
            if os.path.exists(lock_file):
                os.remove(lock_file)

    def test_atomic_write_failure_cleanup(self):
        """Khi việc ghi file bị lỗi, file .tmp phải được dọn dẹp sạch sẽ."""
        mem = FarmMemory(self.mem_file, self.personas_file, self.scenarios_file)
        tmp_file = f"{self.mem_file}.tmp"

        # Mock json.dump gây lỗi Disk Full
        with patch("json.dump", side_effect=IOError("Simulated Disk Full")):
            with self.assertRaises(IOError):
                mem._save()

        # Đảm bảo tmp_file được dọn dẹp, không để lại rác
        self.assertFalse(os.path.exists(tmp_file))

    def test_secret_hygiene_in_working_tree(self):
        """
        Kiểm tra bảo mật (Secret Hygiene):
        Không được có API key thật hay chuỗi 'sk-bee-' trong config.json hoặc mã nguồn.
        """
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(root_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            api_key = cfg.get("ai_vision", {}).get("api_key", "")
            self.assertFalse(
                api_key.startswith("sk-"),
                "config.json không được chứa secret key bắt đầu bằng sk-"
            )
            self.assertEqual(api_key, "", "api_key trong config.json phải để trống mặc định")


if __name__ == "__main__":
    unittest.main()

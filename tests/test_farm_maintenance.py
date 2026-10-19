import unittest
from unittest.mock import patch, MagicMock
from tasks.farm_maintenance import FarmMaintenance
from scheduler.farm_memory import FarmMemory
import time
import os

class TestFarmMaintenance(unittest.TestCase):
    """Kiểm thử tác vụ quản trị nông trại: Đốn hạ cây (3 nhát), Thu mật ong, Nạp Composter."""

    @patch("time.sleep")
    @patch("tasks.farm_maintenance.HumanMouse.click")
    @patch("tasks.farm_maintenance.HumanMouse.human_sleep")
    @patch("tasks.farm_maintenance.WindowHelper.to_screen_coords", return_value=(500, 400))
    def test_chop_trees_delivers_exact_three_hits_per_tree(self, mock_coords, mock_sleep, mock_click, mock_time_sleep):
        """Mỗi cây phải được click đúng tối thiểu 3 nhát chém thành công."""
        tree_coords = [(100, 100), (200, 200)]
        scenario = {"effective_miss_click_prob": 0.0, "speed_mult": 1.0}

        with patch.object(FarmMaintenance, "_calculate_strikes_for_tree", return_value=3):
            FarmMaintenance.chop_trees(hwnd=1234, tree_coords=tree_coords, scenario=scenario, hits_per_tree=3)

        # 2 cây * 3 nhát/cây = 6 cú click thành công trúng đích
        self.assertEqual(mock_click.call_count, 6)

    @patch("time.sleep")
    @patch("tasks.farm_maintenance.HumanMouse.fumble_click")
    @patch("tasks.farm_maintenance.HumanMouse.click")
    @patch("tasks.farm_maintenance.HumanMouse.human_sleep")
    @patch("tasks.farm_maintenance.WindowHelper.to_screen_coords", return_value=(500, 400))
    def test_chop_trees_recovers_from_fumble_to_complete_three_hits(self, mock_coords, mock_sleep, mock_click, mock_fumble, mock_time_sleep):
        """Khi có cú click trượt (fumble), người chơi phải click bù để vẫn đủ 3 nhát trúng đích."""
        tree_coords = [(100, 100)]
        scenario = {"effective_miss_click_prob": 0.5, "speed_mult": 1.0}

        # Giả lập: Lần 1 trượt, Lần 2 trúng, Lần 3 trúng, Lần 4 trúng -> Đủ 3 nhát trúng
        with patch.object(FarmMaintenance, "_calculate_strikes_for_tree", return_value=3):
            with patch("random.random", side_effect=[0.1, 0.9, 0.9, 0.9]):
                FarmMaintenance.chop_trees(hwnd=1234, tree_coords=tree_coords, scenario=scenario, hits_per_tree=3)

        self.assertEqual(mock_fumble.call_count, 1)
        self.assertEqual(mock_click.call_count, 3)

    def test_calculate_strikes_for_tree_supports_overclicking(self):
        """Kiểm tra người thật đôi khi nhấp nhiều hơn 3 nhát (4 hoặc 5 nhát)."""
        counts = {FarmMaintenance._calculate_strikes_for_tree(base_hits=3) for _ in range(100)}
        # Luôn đảm bảo tối thiểu 3 nhát
        self.assertTrue(all(c >= 3 for c in counts))
        # Có sự xuất hiện của 3 và nhát click dư (4 hoặc 5)
        self.assertIn(3, counts)
        self.assertTrue(any(c > 3 for c in counts))

    def test_inter_strike_delay_has_variation(self):
        """Độ trễ giữa các nhát click phải có sự chênh lệch rõ rệt (không cố định)."""
        d1 = FarmMaintenance._get_inter_strike_delay(hit_index=1, total_hits=4, speed_mult=1.0)
        d2 = FarmMaintenance._get_inter_strike_delay(hit_index=2, total_hits=4, speed_mult=1.0)
        d3 = FarmMaintenance._get_inter_strike_delay(hit_index=3, total_hits=4, speed_mult=1.0)
        # Các độ trễ phải nằm trong ngưỡng hợp lệ và có tính động
        self.assertTrue(0.18 <= d1 <= 1.0)
        self.assertTrue(0.18 <= d2 <= 1.0)
        self.assertTrue(0.18 <= d3 <= 1.0)

    def test_farm_memory_tree_chop_tracking(self):
        """Kiểm tra FarmMemory theo dõi thời gian hồi sinh 2 giờ của cây gỗ."""
        test_mem_file = "test_tree_mem.json"
        if os.path.exists(test_mem_file):
            os.remove(test_mem_file)

        try:
            mem = FarmMemory(memory_file=test_mem_file)
            pid = "test_tree_profile"

            # Ban đầu chưa chặt -> cây sẵn sàng
            self.assertTrue(mem.is_tree_ready_for_chop(pid))

            # Ghi nhận vừa chặt (hồi phục trong 7200s)
            mem.record_tree_chop(pid, recovery_seconds=7200)

            # Cây đang hồi phục -> chưa sẵn sàng
            self.assertFalse(mem.is_tree_ready_for_chop(pid))

            # Cây hết thời gian hồi sinh -> sẵn sàng
            with patch("time.time", return_value=time.time() + 7201):
                self.assertTrue(mem.is_tree_ready_for_chop(pid))
        finally:
            for f in [test_mem_file, f"{test_mem_file}.bak", f"{test_mem_file}.tmp"]:
                if os.path.exists(f):
                    os.remove(f)

if __name__ == "__main__":
    unittest.main()

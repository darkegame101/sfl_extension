import unittest
from unittest.mock import patch, MagicMock
from tasks.farm_maintenance import FarmMaintenance
from scheduler.farm_memory import FarmMemory
import time
import os

class TestFarmMaintenance(unittest.TestCase):
    """Kiểm thử tác vụ quản trị nông trại: Đốn hạ cây (3 nhát), Thu mật ong, Nạp Composter."""

    @patch("time.sleep")
    @patch("tasks.farm_maintenance.HumanMouse.click_in_place", return_value=MagicMock(success=True, events_inserted=2))
    @patch("tasks.farm_maintenance.HumanMouse.move_to")
    @patch("tasks.farm_maintenance.WindowHelper.to_screen_coords", return_value=(500, 400))
    def test_chop_trees_delivers_exact_three_hits_per_tree(self, mock_coords, mock_move, mock_click_in_place, mock_time_sleep):
        """Mỗi cây di chuyển chuột đúng 1 lần và phát đúng tối thiểu 3 nhát click_in_place tại chỗ."""
        tree_coords = [(100, 100), (200, 200)]
        scenario = {"effective_miss_click_prob": 0.0, "speed_mult": 1.0}

        with patch.object(FarmMaintenance, "_calculate_strikes_for_tree", return_value=3):
            result = FarmMaintenance.chop_trees(hwnd=1234, tree_coords=tree_coords, scenario=scenario, hits_per_tree=3)

        # 2 cây -> move_to đúng 2 lần (1 lần cho mỗi cây)
        self.assertEqual(mock_move.call_count, 2)
        # 2 cây * 3 nhát/cây = 6 cú click_in_place
        self.assertEqual(mock_click_in_place.call_count, 6)
        # Kiểm tra trạng thái: COMMANDS_ISSUED
        self.assertEqual(result["status"], "COMMANDS_ISSUED")
        self.assertEqual(result["commands_issued"], 6)
        self.assertEqual(result["trees_targeted"], 2)

    @patch("time.sleep")
    @patch("tasks.farm_maintenance.HumanMouse.fumble_click")
    @patch("tasks.farm_maintenance.HumanMouse.click_in_place", return_value=MagicMock(success=True, events_inserted=2))
    @patch("tasks.farm_maintenance.HumanMouse.move_to")
    @patch("tasks.farm_maintenance.WindowHelper.to_screen_coords", return_value=(500, 400))
    def test_chop_trees_does_not_invoke_simulated_fumble_clicks(self, mock_coords, mock_move, mock_click_in_place, mock_fumble, mock_time_sleep):
        """Đảm bảo không gọi fumble_click giả lập trong quy trình thực thi thông thường."""
        tree_coords = [(100, 100)]
        scenario = {"effective_miss_click_prob": 0.9, "speed_mult": 1.0}

        with patch.object(FarmMaintenance, "_calculate_strikes_for_tree", return_value=3):
            result = FarmMaintenance.chop_trees(hwnd=1234, tree_coords=tree_coords, scenario=scenario, hits_per_tree=3)

        # fumble_click tuyệt đối không được gọi
        mock_fumble.assert_not_called()
        self.assertEqual(mock_move.call_count, 1)
        self.assertEqual(mock_click_in_place.call_count, 3)
        self.assertEqual(result["status"], "COMMANDS_ISSUED")
        self.assertEqual(result["commands_issued"], 3)

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

    @patch("tasks.farm_maintenance.HumanMouse.human_sleep")
    @patch("tasks.farm_maintenance.HumanMouse.click")
    @patch("tasks.farm_maintenance.WindowHelper.to_screen_coords", return_value=(300, 300))
    def test_harvest_honey_returns_commands_issued_contract(self, mock_to_screen, mock_click, mock_sleep):
        """harvest_honey trả về hợp đồng kết quả chuẩn hóa với verified=False."""
        res = FarmMaintenance.harvest_honey(hwnd=1234, beehive_coords=[(10, 20), (30, 40)])
        self.assertEqual(res["status"], "COMMANDS_ISSUED")
        self.assertEqual(res["beehives_targeted"], 2)
        self.assertEqual(res["commands_issued"], 2)
        self.assertFalse(res["verified"])
        self.assertEqual(mock_click.call_count, 2)

    @patch("tasks.farm_maintenance.HumanMouse.human_sleep")
    @patch("tasks.farm_maintenance.HumanMouse.click")
    @patch("tasks.farm_maintenance.WindowHelper.to_screen_coords", return_value=(400, 400))
    def test_manage_composter_returns_commands_issued_contract(self, mock_to_screen, mock_click, mock_sleep):
        """manage_composter trả về hợp đồng kết quả chuẩn hóa với verified=False."""
        res = FarmMaintenance.manage_composter(hwnd=1234, composter_coord=(50, 60))
        self.assertEqual(res["status"], "COMMANDS_ISSUED")
        self.assertEqual(res["composter_targeted"], 1)
        self.assertEqual(res["commands_issued"], 1)
        self.assertFalse(res["verified"])
        mock_click.assert_called_once_with(400, 400, random_offset=4)


if __name__ == "__main__":
    unittest.main()

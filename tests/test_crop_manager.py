import unittest
from unittest.mock import patch, MagicMock, call
from tasks.crop_manager import CropManager


class TestCropManager(unittest.TestCase):
    """
    Unit test suite cho CropManager (tiến trình C2):
    - Đảm bảo 100% offline, mock toàn bộ Win32, HumanMouse, WindowHelper, LocalVisionEngine, FarmMemory.
    - Kiểm thử các trường hợp bình thường, danh sách rỗng, HWND/tọa độ không hợp lệ.
    - Kiểm thử lan truyền exception, thứ tự gọi hàm, và tách biệt COMMAND_ISSUED khỏi VERIFIED.
    - Kiểm toán hợp đồng hiện tại của record_planting (rủi ro ghi nhận trước khi xác minh).
    """

    def setUp(self):
        self.mock_memory = MagicMock()
        self.crop_mgr = CropManager(farm_memory=self.mock_memory, sync_delay=(0.1, 0.2))

    # --- 1. Khởi tạo & Cấu hình ---

    def test_init_defaults_and_custom_sync_delay(self):
        """Khởi tạo CropManager lưu đúng memory instance và sync_delay."""
        cm_default = CropManager(farm_memory=self.mock_memory)
        self.assertEqual(cm_default.sync_delay, (0.45, 0.85))
        self.assertIs(cm_default.memory, self.mock_memory)

        cm_custom = CropManager(farm_memory=self.mock_memory, sync_delay=(0.3, 0.6))
        self.assertEqual(cm_custom.sync_delay, (0.3, 0.6))

    # --- 2. harvest_plots ---

    @patch("tasks.crop_manager.HumanMouse.click")
    def test_harvest_plots_empty_coords_is_noop(self, mock_click):
        """Truyền plot_coords rỗng hoặc None phải trả về NOOP và không click chuột."""
        res_empty = self.crop_mgr.harvest_plots(hwnd=1234, plot_coords=[])
        self.assertEqual(res_empty["status"], "NOOP")
        self.assertEqual(res_empty["commands_issued"], 0)
        self.assertFalse(res_empty["verified"])
        mock_click.assert_not_called()

        res_none = self.crop_mgr.harvest_plots(hwnd=1234, plot_coords=None)
        self.assertEqual(res_none["status"], "NOOP")
        mock_click.assert_not_called()

    @patch("tasks.crop_manager.HumanMouse.click")
    def test_harvest_plots_invalid_hwnd(self, mock_click):
        """Truyền hwnd <= 0 phải trả về INVALID_HWND mà không click chuột."""
        res_zero = self.crop_mgr.harvest_plots(hwnd=0, plot_coords=[(100, 100)])
        self.assertEqual(res_zero["status"], "INVALID_HWND")
        self.assertEqual(res_zero["commands_issued"], 0)
        mock_click.assert_not_called()

        res_neg = self.crop_mgr.harvest_plots(hwnd=-1, plot_coords=[(100, 100)])
        self.assertEqual(res_neg["status"], "INVALID_HWND")
        mock_click.assert_not_called()

    @patch("tasks.crop_manager.HumanMouse.human_sleep")
    @patch("tasks.crop_manager.HumanMouse.click")
    @patch("tasks.crop_manager.WindowHelper.to_screen_coords")
    def test_harvest_plots_dispatches_clicks_for_all_plots(self, mock_to_screen, mock_click, mock_sleep):
        """Kiểm tra toàn bộ các ô đất đều được chuyển đổi tọa độ và phát lệnh click."""
        plot_coords = [(100, 200), (300, 400), (500, 600)]
        mock_to_screen.side_effect = lambda hwnd, rx, ry: (rx + 50, ry + 50)

        result = self.crop_mgr.harvest_plots(hwnd=1234, plot_coords=plot_coords)

        self.assertEqual(result["status"], "COMMANDS_ISSUED")
        self.assertEqual(result["plots_targeted"], 3)
        self.assertEqual(result["commands_issued"], 3)
        self.assertEqual(result["commands_attempted"], 3)
        self.assertFalse(result["verified"])

        # Kiểm tra tập hợp các tọa độ được click (không phụ thuộc thứ tự shuffle)
        clicked_coords = {call_args[0][:2] for call_args in mock_click.call_args_list}
        expected_coords = {(150, 250), (350, 450), (550, 650)}
        self.assertEqual(clicked_coords, expected_coords)
        self.assertEqual(mock_click.call_count, 3)

    @patch("tasks.crop_manager.HumanMouse.simulate_distraction")
    @patch("tasks.crop_manager.HumanMouse.fumble_click")
    @patch("tasks.crop_manager.HumanMouse.human_sleep")
    @patch("tasks.crop_manager.HumanMouse.click")
    @patch("tasks.crop_manager.WindowHelper.to_screen_coords", return_value=(500, 500))
    def test_harvest_plots_removes_fumble_and_distraction_noise(
        self, mock_to_screen, mock_click, mock_sleep, mock_fumble, mock_distract
    ):
        """Kịch bản có miss_prob=0.9 và distract_prob=0.9 không được kích hoạt fumble hay distraction."""
        scenario = {"effective_miss_click_prob": 0.9, "effective_distraction_prob": 0.9, "speed_mult": 1.0}
        self.crop_mgr.harvest_plots(hwnd=1234, plot_coords=[(100, 100), (200, 200)], scenario=scenario)

        mock_fumble.assert_not_called()
        mock_distract.assert_not_called()
        self.assertEqual(mock_click.call_count, 2)

    @patch("tasks.crop_manager.WindowHelper.to_screen_coords", side_effect=RuntimeError("Window mapping failure"))
    def test_harvest_plots_window_helper_exception_propagates(self, mock_to_screen):
        """Exception từ WindowHelper không được nuốt ngầm mà phải báo cáo FAILED tường minh kèm chi tiết lỗi."""
        res = self.crop_mgr.harvest_plots(hwnd=1234, plot_coords=[(100, 200)])
        self.assertEqual(res["status"], "FAILED")
        self.assertEqual(res["commands_issued"], 0)
        self.assertEqual(res["error"], "Window mapping failure")
        self.assertFalse(res["verified"])

    @patch("tasks.crop_manager.WindowHelper.to_screen_coords", return_value=(500, 500))
    @patch("tasks.crop_manager.HumanMouse.click", side_effect=OSError("SendInput failure"))
    def test_harvest_plots_human_mouse_error_propagates(self, mock_click, mock_to_screen):
        """Lỗi từ HumanMouse không được nuốt ngầm mà phải báo cáo FAILED tường minh kèm chi tiết lỗi."""
        res = self.crop_mgr.harvest_plots(hwnd=1234, plot_coords=[(100, 200)])
        self.assertEqual(res["status"], "FAILED")
        self.assertEqual(res["commands_issued"], 0)
        self.assertEqual(res["error"], "SendInput failure")
        self.assertFalse(res["verified"])

    # --- 3. ensure_active_seed_tool ---

    def test_ensure_active_seed_tool_invalid_hwnd(self):
        """Truyền hwnd <= 0 phải trả về lỗi INVALID_HWND."""
        res = self.crop_mgr.ensure_active_seed_tool(hwnd=0)
        self.assertFalse(res["success"])
        self.assertEqual(res["reason"], "INVALID_HWND")

    @patch("tasks.crop_manager.WindowHelper.get_client_rect_on_screen", return_value=(0, 0, 0, 0))
    def test_ensure_active_seed_tool_invalid_client_rect(self, mock_rect):
        """Client area có chiều rộng hoặc chiều cao <= 0 phải báo lỗi INVALID_CLIENT_RECT."""
        res = self.crop_mgr.ensure_active_seed_tool(hwnd=1234)
        self.assertFalse(res["success"])
        self.assertEqual(res["reason"], "INVALID_CLIENT_RECT")

    @patch("tasks.crop_manager.HumanMouse.human_sleep")
    @patch("tasks.crop_manager.HumanMouse.click")
    @patch("tasks.crop_manager.HumanMouse.curiosity_hover")
    @patch("tasks.crop_manager.LocalVisionEngine.get_hotbar_seed_coords", return_value=(1248, 201))
    @patch("tasks.crop_manager.WindowHelper.get_client_rect_on_screen", return_value=(100, 50, 1280, 720))
    def test_ensure_active_seed_tool_calculates_and_clicks_hotbar_slot(
        self, mock_rect, mock_hotbar, mock_hover, mock_click, mock_sleep
    ):
        """Tính đúng tọa độ tuyệt đối của slot Hotbar (100+1248, 50+201) và hover -> click."""
        res = self.crop_mgr.ensure_active_seed_tool(hwnd=1234, slot_index=1, crop_name="Potato")

        self.assertTrue(res["success"])
        self.assertEqual(res["target"], (1348, 251))
        self.assertEqual(res["status"], "COMMANDS_ISSUED")

        mock_hover.assert_called_once_with(1348, 251, hover_sec=0.35)
        mock_click.assert_called_once_with(1348, 251, random_offset=3)

    # --- 4. plant_plots ---

    @patch("tasks.crop_manager.CropManager.ensure_active_seed_tool")
    def test_plant_plots_empty_coords_does_not_mutate_memory(self, mock_tool):
        """Khi danh sách ô đất rỗng, không được gọi tool và tuyệt đối không ghi FarmMemory."""
        res = self.crop_mgr.plant_plots(
            hwnd=1234,
            seed_box_coord=(400, 560),
            plot_coords=[],
            profile_id="p_test",
            crop_name="Sunflower"
        )
        self.assertEqual(res["status"], "NOOP")
        mock_tool.assert_not_called()
        self.mock_memory.record_planting.assert_not_called()

    def test_plant_plots_invalid_hwnd(self):
        """plant_plots với hwnd <= 0 phải trả về INVALID_HWND mà không can thiệp bộ nhớ."""
        res = self.crop_mgr.plant_plots(
            hwnd=0,
            seed_box_coord=(400, 560),
            plot_coords=[(100, 200)],
            profile_id="p_test"
        )
        self.assertEqual(res["status"], "INVALID_HWND")
        self.mock_memory.record_planting.assert_not_called()

    @patch("tasks.crop_manager.HumanMouse.human_sleep")
    @patch("tasks.crop_manager.HumanMouse.click")
    @patch("tasks.crop_manager.WindowHelper.to_screen_coords")
    @patch("tasks.crop_manager.CropManager.ensure_active_seed_tool")
    def test_plant_plots_call_ordering_and_dispatches_clicks(
        self, mock_tool, mock_to_screen, mock_click, mock_sleep
    ):
        """Thứ tự gọi: ensure_active_seed_tool phải diễn ra trước khi click ô đất."""
        call_log = []
        mock_tool.side_effect = lambda *args, **kwargs: (call_log.append("tool"), {"success": True})[1]
        mock_to_screen.side_effect = lambda hwnd, rx, ry: (rx + 10, ry + 10)
        mock_click.side_effect = lambda *args, **kwargs: call_log.append("click")

        res = self.crop_mgr.plant_plots(
            hwnd=1234,
            seed_box_coord=(400, 560),
            plot_coords=[(100, 100), (200, 200)],
            profile_id="p_test",
            crop_name="Sunflower",
            grow_seconds=60
        )

        self.assertEqual(res["status"], "COMMANDS_ISSUED")
        self.assertEqual(res["plots_targeted"], 2)
        self.assertEqual(res["commands_issued"], 2)
        self.assertFalse(res["verified"])

        # Tool được gọi trước, sau đó là 2 cú click ô đất
        self.assertEqual(call_log[0], "tool")
        self.assertEqual(call_log.count("click"), 2)

    @patch("tasks.crop_manager.HumanMouse.human_sleep")
    @patch("tasks.crop_manager.HumanMouse.click")
    @patch("tasks.crop_manager.WindowHelper.to_screen_coords")
    @patch("tasks.crop_manager.CropManager.ensure_active_seed_tool")
    def test_plant_plots_auxiliary_seed_box_behavior(
        self, mock_tool, mock_to_screen, mock_click, mock_sleep
    ):
        """seed_box_coord tùy biến kích hoạt thêm click giỏ hạt; tọa độ mặc định thì bỏ qua."""
        mock_to_screen.side_effect = lambda hwnd, rx, ry: (rx, ry)

        # 1. Tọa độ tùy biến (khác 400, 560) -> Có click giỏ hạt phụ trợ
        self.crop_mgr.plant_plots(
            hwnd=1234,
            seed_box_coord=(450, 600),
            plot_coords=[(100, 100)],
            profile_id="p_test"
        )
        # 1 click giỏ hạt + 1 click ô đất = 2 click
        self.assertEqual(mock_click.call_count, 2)

        mock_click.reset_mock()

        # 2. Tọa độ mặc định (400, 560) -> Bỏ qua click giỏ hạt
        self.crop_mgr.plant_plots(
            hwnd=1234,
            seed_box_coord=(400, 560),
            plot_coords=[(100, 100)],
            profile_id="p_test"
        )
        # Chỉ 1 click ô đất
        self.assertEqual(mock_click.call_count, 1)

    @patch("tasks.crop_manager.HumanMouse.human_sleep")
    @patch("tasks.crop_manager.HumanMouse.click")
    @patch("tasks.crop_manager.WindowHelper.to_screen_coords", return_value=(500, 500))
    @patch("tasks.crop_manager.CropManager.ensure_active_seed_tool")
    def test_plant_plots_audits_unverified_farm_memory_mutation(
        self, mock_tool, mock_to_screen, mock_click, mock_sleep
    ):
        """
        Kiểm toán hợp đồng hiện tại của record_planting:
        CropManager hiện gọi FarmMemory.record_planting() ngay sau khi phát lệnh click.
        LƯU Ý RỦI RO KIẾN TRÚC: Đây là sự cam kết trạng thái trước khi có xác nhận thị giác,
        cần được tách rời sang bước xác minh vòng lặp đóng ở Giai đoạn C3 & C4.
        """
        self.crop_mgr.plant_plots(
            hwnd=1234,
            seed_box_coord=(400, 560),
            plot_coords=[(100, 100)],
            profile_id="p_audit_profile",
            crop_name="Carrot",
            grow_seconds=1800,
            profile_name="Farmer Nam"
        )

        self.mock_memory.record_planting.assert_called_once_with(
            "p_audit_profile",
            "Carrot",
            1800,
            profile_name="Farmer Nam"
        )

    @patch("tasks.crop_manager.HumanMouse.human_sleep")
    @patch("tasks.crop_manager.HumanMouse.click")
    @patch("tasks.crop_manager.CropManager.ensure_active_seed_tool", return_value={"success": False, "reason": "INVALID_CLIENT_RECT"})
    def test_plant_plots_tool_selection_failure_aborts_without_clicking_or_memory_mutation(
        self, mock_tool, mock_click, mock_sleep
    ):
        """Khi chọn seed tool thất bại, DỪNG LẠI NGAY LẬP TỨC: không click đất và không ghi nhớ bộ nhớ."""
        res = self.crop_mgr.plant_plots(
            hwnd=1234,
            seed_box_coord=(400, 560),
            plot_coords=[(100, 100), (200, 200)],
            profile_id="p_fail_tool",
            crop_name="Sunflower",
            grow_seconds=60
        )

        mock_click.assert_not_called()
        self.mock_memory.record_planting.assert_not_called()
        self.assertEqual(res["status"], "TOOL_SELECTION_FAILED")
        self.assertEqual(res["commands_attempted"], 0)
        self.assertEqual(res["commands_issued"], 0)
        self.assertFalse(res["verified"])
        self.assertEqual(res["error"], "INVALID_CLIENT_RECT")

    @patch("tasks.crop_manager.HumanMouse.human_sleep")
    @patch("tasks.crop_manager.HumanMouse.click")
    @patch("tasks.crop_manager.WindowHelper.to_screen_coords", return_value=(500, 500))
    @patch("tasks.crop_manager.CropManager.ensure_active_seed_tool", return_value={"success": True})
    def test_plant_plots_mid_loop_exception_returns_partial_execution(
        self, mock_tool, mock_to_screen, mock_click, mock_sleep
    ):
        """Nếu ngoại lệ xảy ra giữa vòng lặp gieo hạt, trả về PARTIALLY_EXECUTED mà không giấu kết quả một phần."""
        mock_click.side_effect = [None, RuntimeError("OS_INPUT_BLOCKED")]

        res = self.crop_mgr.plant_plots(
            hwnd=1234,
            seed_box_coord=(400, 560),
            plot_coords=[(100, 100), (200, 200)],
            profile_id="p_mid_error",
            crop_name="Sunflower",
            grow_seconds=60
        )

        self.assertEqual(res["status"], "PARTIALLY_EXECUTED")
        self.assertEqual(res["commands_attempted"], 2)
        self.assertEqual(res["commands_issued"], 1)
        self.assertEqual(res["error"], "OS_INPUT_BLOCKED")
        self.assertFalse(res["verified"])

    @patch("tasks.crop_manager.HumanMouse.human_sleep")
    @patch("tasks.crop_manager.HumanMouse.click")
    @patch("tasks.crop_manager.WindowHelper.to_screen_coords", return_value=(500, 500))
    def test_harvest_plots_mid_loop_exception_returns_partial_execution(
        self, mock_to_screen, mock_click, mock_sleep
    ):
        """Nếu ngoại lệ xảy ra giữa vòng lặp thu hoạch, trả về PARTIALLY_EXECUTED kèm chi tiết lệnh đã phát."""
        mock_click.side_effect = [None, RuntimeError("UIPI_BLOCKED")]

        res = self.crop_mgr.harvest_plots(
            hwnd=1234,
            plot_coords=[(100, 100), (200, 200)]
        )

        self.assertEqual(res["status"], "PARTIALLY_EXECUTED")
        self.assertEqual(res["commands_attempted"], 2)
        self.assertEqual(res["commands_issued"], 1)
        self.assertEqual(res["error"], "UIPI_BLOCKED")
        self.assertFalse(res["verified"])


if __name__ == "__main__":
    unittest.main()

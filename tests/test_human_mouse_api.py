import unittest
from unittest.mock import patch, MagicMock, call
import ctypes
from core.human_mouse import (
    HumanMouse,
    ClickResult,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_RIGHTDOWN,
    MOUSEEVENTF_RIGHTUP
)


class TestHumanMouseAPI(unittest.TestCase):
    """
    Unit test suite cho HumanMouse API (tiến trình C1):
    - Hợp đồng click_in_place(): không di chuyển, cờ Win32, kiểm tra giá trị trả về SendInput.
    - Hợp đồng tương thích ngược của click(x, y).
    - Tách biệt COMMAND_ISSUED khỏi POSTCONDITION_VERIFIED.
    """

    @patch("time.sleep")
    @patch("core.human_mouse.user32.SendInput", return_value=1)
    def test_click_in_place_left_button_flags_and_ordering(self, mock_send_input, mock_sleep):
        """Xác minh click_in_place('left') gửi đúng thứ tự LEFTDOWN -> LEFTUP và cờ Win32 tương ứng."""
        result = HumanMouse.click_in_place(button='left', hold_time=0.05)

        self.assertTrue(result.success)
        self.assertTrue(bool(result))
        self.assertTrue(result.down_inserted)
        self.assertTrue(result.up_inserted)
        self.assertEqual(result.events_inserted, 2)
        self.assertIsNone(result.error)

        # SendInput phải được gọi đúng 2 lần theo thứ tự: MOUSEEVENTF_LEFTDOWN -> MOUSEEVENTF_LEFTUP
        self.assertEqual(mock_send_input.call_count, 2)
        down_call_inp = mock_send_input.call_args_list[0][0][1]._obj
        up_call_inp = mock_send_input.call_args_list[1][0][1]._obj
        self.assertEqual(down_call_inp.u.mi.dwFlags, MOUSEEVENTF_LEFTDOWN)
        self.assertEqual(up_call_inp.u.mi.dwFlags, MOUSEEVENTF_LEFTUP)

        # Giữ phím tối thiểu kỹ thuật phải được gọi
        mock_sleep.assert_called_once_with(0.05)

    @patch("time.sleep")
    @patch("core.human_mouse.user32.SendInput", return_value=1)
    def test_click_in_place_right_button_flags_and_ordering(self, mock_send_input, mock_sleep):
        """Xác minh click_in_place('right') gửi cờ RIGHTDOWN -> RIGHTUP."""
        result = HumanMouse.click_in_place(button='right', hold_time=0.02)

        self.assertTrue(result.success)
        self.assertEqual(result.events_inserted, 2)
        self.assertEqual(mock_send_input.call_count, 2)
        down_call_inp = mock_send_input.call_args_list[0][0][1]._obj
        up_call_inp = mock_send_input.call_args_list[1][0][1]._obj
        self.assertEqual(down_call_inp.u.mi.dwFlags, MOUSEEVENTF_RIGHTDOWN)
        self.assertEqual(up_call_inp.u.mi.dwFlags, MOUSEEVENTF_RIGHTUP)
        mock_sleep.assert_called_once_with(0.02)

    @patch("time.sleep")
    @patch("core.human_mouse.HumanMouse.move_to")
    @patch("core.human_mouse.HumanMouse.set_cursor_pos")
    @patch("core.human_mouse.HumanMouse.calculate_fitts_duration")
    @patch("core.human_mouse.user32.SendInput", return_value=1)
    def test_click_in_place_does_not_invoke_move_to_or_trajectory(
        self, mock_send_input, mock_fitts, mock_set_cursor, mock_move_to, mock_sleep
    ):
        """click_in_place() tuyệt đối không gọi move_to, set_cursor_pos, hay tính Fitts/Bézier."""
        result = HumanMouse.click_in_place(button='left', hold_time=0.01)

        self.assertTrue(result.success)
        mock_move_to.assert_not_called()
        mock_set_cursor.assert_not_called()
        mock_fitts.assert_not_called()

    @patch("time.sleep")
    @patch("core.human_mouse.user32.SendInput", return_value=0)
    def test_click_in_place_zero_insertion_failure(self, mock_send_input, mock_sleep):
        """Khi user32.SendInput trả về 0 ở MouseDown (bị UIPI chặn), báo cáo lỗi thất bại rõ ràng."""
        result = HumanMouse.click_in_place(button='left')

        self.assertFalse(result.success)
        self.assertFalse(bool(result))
        self.assertFalse(result.down_inserted)
        self.assertFalse(result.up_inserted)
        self.assertEqual(result.events_inserted, 0)
        self.assertIsNotNone(result.error)
        self.assertIn("MouseDown", result.error)

        # Khi MouseDown thất bại, không gửi tiếp MouseUp để tránh input state không hợp lệ
        self.assertEqual(mock_send_input.call_count, 1)

    @patch("time.sleep")
    @patch("core.human_mouse.user32.SendInput", side_effect=[1, 0])
    def test_click_in_place_partial_insertion_failure(self, mock_send_input, mock_sleep):
        """Khi MouseDown thành công (1) nhưng MouseUp thất bại (0), báo cáo lỗi partial failure rõ ràng."""
        result = HumanMouse.click_in_place(button='left')

        self.assertFalse(result.success)
        self.assertFalse(bool(result))
        self.assertTrue(result.down_inserted)
        self.assertFalse(result.up_inserted)
        self.assertEqual(result.events_inserted, 1)
        self.assertIsNotNone(result.error)
        self.assertIn("partial failure", result.error.lower())
        self.assertEqual(mock_send_input.call_count, 2)

    def test_click_in_place_unsupported_button_raises_value_error(self):
        """Truyền nút không hỗ trợ (ví dụ 'middle') phải ném ValueError."""
        with self.assertRaises(ValueError):
            HumanMouse.click_in_place(button='middle')

    @patch("time.sleep")
    @patch("core.human_mouse.user32.SendInput", return_value=1)
    @patch("core.human_mouse.HumanMouse.move_to")
    def test_backward_compatible_click_with_coordinates(self, mock_move_to, mock_send_input, mock_sleep):
        """Đảm bảo HumanMouse.click(x, y) giữ nguyên tương thích ngược: gọi move_to rồi gửi input."""
        HumanMouse.click(target_x=450, target_y=650, button='left', random_offset=4)

        mock_move_to.assert_called_once_with(450, 650, random_offset=4)
        self.assertEqual(mock_send_input.call_count, 2)

    def test_click_result_boolean_semantics(self):
        """Kiểm tra tính chuyển đổi boolean của ClickResult."""
        success_res = ClickResult(success=True, down_inserted=True, up_inserted=True, events_inserted=2)
        failed_res = ClickResult(success=False, down_inserted=False, up_inserted=False, events_inserted=0, error="Err")
        partial_res = ClickResult(success=False, down_inserted=True, up_inserted=False, events_inserted=1, error="Partial")

        self.assertTrue(bool(success_res))
        self.assertFalse(bool(failed_res))
        self.assertFalse(bool(partial_res))


if __name__ == "__main__":
    unittest.main()

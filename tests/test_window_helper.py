import unittest
from unittest.mock import patch, MagicMock
from core.window_helper import WindowHelper, RECT, POINT

class TestWindowHelper(unittest.TestCase):
    """Kiểm thử tính năng quản lý cửa sổ và tọa độ tương đối của WindowHelper."""

    def test_ensure_interactive_desktop_does_not_crash(self):
        """Kiểm tra gọi ensure_interactive_desktop an toàn trên Windows."""
        res = WindowHelper.ensure_interactive_desktop()
        # res có thể là handle int hoặc None tùy thuộc vào môi trường sandbox
        self.assertTrue(res is None or isinstance(res, int))

    def test_find_windows_by_pid_zero_returns_empty(self):
        """Truyền PID không hợp lệ phải trả về danh sách rỗng."""
        self.assertEqual(WindowHelper.find_windows_by_pid(0), [])
        self.assertEqual(WindowHelper.find_windows_by_pid(-1), [])

    @patch.object(WindowHelper, "find_windows_by_pid")
    @patch.object(WindowHelper, "find_windows_by_keyword")
    def test_find_game_window_priority_order(self, mock_keyword, mock_pid):
        """Kiểm tra thứ tự ưu tiên: target_pid -> preferred_title -> keywords."""
        # 1. target_pid có cửa sổ -> trả về ngay
        mock_pid.return_value = [1001]
        mock_keyword.return_value = [2002]
        res = WindowHelper.find_game_window(preferred_title="MyProfile", target_pid=9999)
        self.assertEqual(res, 1001)
        mock_pid.assert_called_once_with(9999)

        # 2. target_pid không có cửa sổ -> tìm preferred_title
        mock_pid.return_value = []
        mock_keyword.side_effect = lambda kw: [2002] if kw == "MyProfile" else []
        res = WindowHelper.find_game_window(preferred_title="MyProfile", target_pid=9999)
        self.assertEqual(res, 2002)

        # 3. Không có target_pid và không có preferred_title -> tìm Sunflower Land
        mock_keyword.side_effect = lambda kw: [3003] if kw == "Sunflower Land" else []
        res = WindowHelper.find_game_window()
        self.assertEqual(res, 3003)

    def test_to_screen_coords_calculation(self):
        """Kiểm tra chuyển đổi tọa độ tương đối sang tọa độ màn hình thực tế."""
        with patch.object(WindowHelper, "get_client_rect_on_screen", return_value=(100, 200, 800, 600)):
            sx, sy = WindowHelper.to_screen_coords(hwnd=1234, rel_x=50, rel_y=75)
            self.assertEqual(sx, 150)
            self.assertEqual(sy, 275)

if __name__ == "__main__":
    unittest.main()

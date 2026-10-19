"""
TEST SUITE: KIỂM THỬ GPM-LOGIN API CONNECTOR (GpmAPI)
Bao gồm:
1. Unit tests với Mock HTTP session (chạy offline / CI)
2. Live Integration tests (chạy trực tiếp khi GPMLogin đang bật trên máy)
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gpm_api import GpmAPI


class TestGpmAPIMock(unittest.TestCase):
    """Kiểm thử tính đúng đắn logic của GpmAPI bằng Mocking (không cần bật GPMLogin)."""

    def setUp(self):
        self.gpm = GpmAPI(api_base_url="http://127.0.0.1:19995")
        self.gpm.session = MagicMock()

    def test_check_connection_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        self.gpm.session.get.return_value = mock_resp

        self.assertTrue(self.gpm.check_connection())
        self.gpm.session.get.assert_called_with("http://127.0.0.1:19995/v2/profiles", timeout=3)

    def test_check_connection_failure(self):
        self.gpm.session.get.side_effect = Exception("Connection refused")
        with patch.object(self.gpm, "auto_detect_api_url", return_value="http://127.0.0.1:19995"):
            self.assertFalse(self.gpm.check_connection())

    def test_get_profiles(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"id": "p1", "name": "Farm_01", "group_name": "Sunflower"},
            {"id": "p2", "name": "Farm_02", "group_name": "Pumpkin"},
            {"id": "p3", "name": "Test_03", "group_name": "Sunflower"}
        ]
        self.gpm.session.get.return_value = mock_resp

        # Test lấy toàn bộ
        all_profs = self.gpm.get_profiles()
        self.assertEqual(len(all_profs), 3)

        # Test lọc theo group
        sun_profs = self.gpm.get_profiles(group_filter="Sunflower")
        self.assertEqual(len(sun_profs), 2)
        self.assertEqual(sun_profs[0]["id"], "p1")

        # Test tìm kiếm theo tên
        searched = self.gpm.get_profiles(search="Farm_02")
        self.assertEqual(len(searched), 1)
        self.assertEqual(searched[0]["name"], "Farm_02")

    def test_start_profile(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": True,
            "selenium_remote_debug_address": "127.0.0.1:54321",
            "browser_location": "C:\\path\\to\\chrome.exe"
        }
        self.gpm.session.get.return_value = mock_resp

        with patch.object(self.gpm, "find_pid_by_port", return_value=12345):
            res = self.gpm.start_profile("test_pid_01", window_size="1280x720")
            self.assertTrue(res["success"])
            self.assertEqual(res["selenium_remote_debug_address"], "127.0.0.1:54321")
            self.assertEqual(res["remote_debug_port"], 54321)
            self.assertEqual(res["process_id"], 12345)

    def test_stop_profile(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        self.gpm.session.get.return_value = mock_resp

        ok = self.gpm.stop_profile("test_pid_01")
        self.assertTrue(ok)
        self.gpm.session.get.assert_called_with(
            "http://127.0.0.1:19995/v2/stop",
            params={"profile_id": "test_pid_01"},
            timeout=10
        )

    def test_create_and_delete_profile(self):
        # Mock Create
        mock_resp_create = MagicMock()
        mock_resp_create.status_code = 200
        mock_resp_create.json.return_value = {"status": True, "profile_id": "new_p_99"}
        self.gpm.session.get.return_value = mock_resp_create

        c_res = self.gpm.create_profile(name="TestProfile")
        self.assertTrue(c_res["success"])
        self.assertEqual(c_res["profile_id"], "new_p_99")

        # Mock Delete
        mock_resp_del = MagicMock()
        mock_resp_del.status_code = 200
        mock_resp_del.text = "ok"
        self.gpm.session.get.return_value = mock_resp_del

        d_ok = self.gpm.delete_profile("new_p_99")
        self.assertTrue(d_ok)


class TestGpmAPILive(unittest.TestCase):
    """Kiểm thử kết nối thực tế tới GPM-Login nếu ứng dụng đang chạy trên máy."""

    @classmethod
    def setUpClass(cls):
        cls.gpm = GpmAPI()
        cls.is_live = cls.gpm.check_connection()

    def test_live_connection_and_profile_retrieval(self):
        if not self.is_live:
            self.skipTest("GPMLogin không đang chạy trên máy, bỏ qua live test.")
        
        self.assertTrue(self.is_live, "GPM API phải phản hồi thành công")
        profiles = self.gpm.get_profiles()
        self.assertIsInstance(profiles, list)
        print(f"\n[Live Test] Đã kết nối GPM thành công! Tìm thấy {len(profiles)} profile thực tế.")


if __name__ == "__main__":
    unittest.main()

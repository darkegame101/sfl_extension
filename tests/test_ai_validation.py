"""
TEST SUITE: KIỂM THỬ XÁC THỰC DỮ LIỆU AI VISION & LÁ CHẮN CAPTCHA
Kiểm tra Bounds checking, Schema sanitizer và chế độ phòng thủ Fail-Safe
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ai_vision import AIVision
from tasks.captcha_guard import CaptchaGuard


class TestAIValidationAndGuard(unittest.TestCase):

    def test_schema_sanitizer_normal(self):
        """Dữ liệu chuẩn từ mô hình phải được giữ nguyên."""
        raw = {
            "has_blocking_popup": True,
            "popup_close_button": [450, 300],
            "is_syncing": False,
            "has_captcha": False,
            "has_mushrooms": True,
            "mushroom_positions": [[200, 150], [600, 400]],
            "plots_summary": {"has_ready_crops": True, "has_empty_plots": False}
        }
        res = AIVision.validate_and_sanitize(raw, max_w=1280, max_h=720)
        self.assertTrue(res["valid_schema"])
        self.assertEqual(res["popup_close_button"], [450, 300])
        self.assertEqual(len(res["mushroom_positions"]), 2)
        self.assertTrue(res["plots_summary"]["has_ready_crops"])

    def test_schema_sanitizer_out_of_bounds(self):
        """Tọa độ vượt ngoài biên màn hình (Negative hoặc > Max dimension) phải bị loại bỏ."""
        raw = {
            "has_blocking_popup": True,
            "popup_close_button": [-50, 9999],  # Tọa độ rác ngoài màn hình
            "mushroom_positions": [[-10, 200], [500, 300], [2000, 500]]
        }
        res = AIVision.validate_and_sanitize(raw, max_w=1280, max_h=720)
        # Nút close ngoài biên phải bị set về None
        self.assertIsNone(res["popup_close_button"])
        # Chỉ cây nấm hợp lệ [500, 300] được giữ lại
        self.assertEqual(len(res["mushroom_positions"]), 1)
        self.assertEqual(res["mushroom_positions"][0], [500, 300])

    def test_schema_sanitizer_malformed_types(self):
        """Dữ liệu sai kiểu (chuỗi thay vì số) phải được ép kiểu hoặc lọc bỏ an toàn."""
        raw = {
            "has_blocking_popup": "yes",  # Chuỗi thay vì boolean
            "is_syncing": "false",       # Chuỗi 'false' phải ra False, không bị Python bool() ép thành True
            "mushroom_positions": "invalid_string",
            "plots_summary": {"has_ready_crops": "False", "has_empty_plots": "0"}
        }
        res = AIVision.validate_and_sanitize(raw, max_w=1280, max_h=720)
        self.assertIsInstance(res["has_blocking_popup"], bool)
        self.assertTrue(res["has_blocking_popup"])
        self.assertFalse(res["is_syncing"])
        self.assertFalse(res["plots_summary"]["has_ready_crops"])
        self.assertFalse(res["plots_summary"]["has_empty_plots"])
        self.assertIsInstance(res["mushroom_positions"], list)
        self.assertIsInstance(res["plots_summary"], dict)

    def test_captcha_guard_fail_safe(self):
        """Khi AI gặp lỗi (success: False), CaptchaGuard phải kích hoạt cảnh báo an toàn (Fail-Safe), không được fail-open."""
        mock_ai_error = {
            "success": False,
            "error": "Timeout 504 Gateway Error"
        }
        # Ở chế độ fail_safe=True, hàm phải trả về True (kích hoạt phòng vệ)
        is_blocked = CaptchaGuard.check_and_guard(mock_ai_error, fail_safe=True)
        self.assertTrue(is_blocked)

    def test_config_ai_vision_loaded(self):
        """Kiểm tra cấu hình AI Vision với endpoint và model hợp lệ, tuân thủ an toàn bí mật (Rule F)."""
        import json
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        ai_cfg = cfg.get("ai_vision", {})
        self.assertIn("enabled", ai_cfg)
        self.assertIn("beeknoee.com", ai_cfg.get("base_url", ""))
        self.assertEqual(ai_cfg.get("model_id"), "bee-tok/claude-haiku-5-5")
        # Chấp nhận key qua config.json hoặc biến môi trường AI_VISION_API_KEY mà không bắt buộc commit secret vào git
        api_key = os.environ.get("AI_VISION_API_KEY") or ai_cfg.get("api_key", "")
        self.assertIsInstance(api_key, str)


if __name__ == "__main__":
    unittest.main()


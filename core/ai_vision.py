"""
HỆ THỐNG 3A: AI VISION CLIENT (CLAUDE HAIKU 5.5 ĐÔI MẮT & BỘ NÃO)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Tối ưu cho bee-tok/claude-haiku-5-5 (1.375đ / 1M token)
"""

import base64
import json
import os
import time
from io import BytesIO
from typing import Dict, Optional, Tuple, Any
import requests
from PIL import Image


class AIVision:
    """
    Module xử lý thị giác AI:
    - Chụp ảnh màn hình cửa sổ game siêu tốc.
    - Gửi ảnh qua API Claude Haiku 5.5 phân tích toàn diện.
    - Nhận diện Pop-up, nấm mọc (Mushrooms), ô đất chín/trống, vòng xoay Syncing và Captcha.
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://platform.beeknoee.com/v1",
        model_id: str = "bee-tok/claude-haiku-5-5"
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.session = requests.Session()

    @staticmethod
    def capture_screenshot(region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Image.Image]:
        """
        Chụp ảnh màn hình cửa sổ game:
        - Ưu tiên dùng PIL ImageGrab khi ở desktop tương tác.
        - Fallback an toàn nếu môi trường không có màn hình ảo.
        """
        try:
            from core.window_helper import WindowHelper
            WindowHelper.ensure_interactive_desktop()
        except Exception:
            pass

        try:
            from PIL import ImageGrab
            if region:
                # bbox = (left, top, right, bottom)
                bbox = (region[0], region[1], region[0] + region[2], region[1] + region[3])
                img = ImageGrab.grab(bbox=bbox, all_screens=True)
            else:
                img = ImageGrab.grab(all_screens=True)
            return img
        except Exception as e:
            # Fallback mss
            try:
                import mss
                with mss.mss() as sct:
                    if region:
                        mon = {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
                    else:
                        mon = sct.monitors[1]
                    sct_img = sct.grab(mon)
                    return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception as e2:
                print(f"[AIVision Warning] Khong the chup man hinh truc tiep: {e2}")
                return None

    @staticmethod
    def image_to_base64(img: Image.Image, max_dim: int = 1280) -> str:
        """
        Nén ảnh thành chuỗi base64 JPEG tối ưu để giảm dung lượng và tiết kiệm chi phí token.
        """
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def analyze_screen(self, img: Image.Image) -> Dict:
        """
        Gửi ảnh chụp game đến Claude Haiku 5.5 để phân tích trạng thái game.
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Chua cau hinh API Key trong config.json",
                "state": "unconfigured"
            }

        b64_image = self.image_to_base64(img)
        img_width, img_height = img.size

        system_prompt = (
            "Bạn là chuyên gia thị giác AI phân tích ảnh chụp màn hình game Sunflower Land.\n"
            "Nhiệm vụ của bạn là kiểm tra màn hình và trả về JSON chuẩn xác (không giải thích thêm):\n"
            "{\n"
            '  "has_blocking_popup": false, // Có bảng thông báo / Daily Reward / Event đang che màn hình không?\n'
            '  "popup_close_button": null, // Nếu có popup, tọa độ pixel [x, y] của nút đóng (nút X / OK / Claim)\n'
            '  "is_syncing": false, // Có biểu tượng vòng xoay đồng bộ "Syncing..." đang quay không?\n'
            '  "has_captcha": false, // Có xuất hiện bảng Captcha / Proof of Humanity / Bot Check không?\n'
            '  "captcha_details": null, // Chi tiết loại captcha nếu có\n'
            '  "has_mushrooms": false, // Có cây nấm hoang dã nào mọc trên các thảm cỏ trống không?\n'
            '  "mushroom_positions": [], // Danh sách tọa độ pixel [[x, y], ...] của từng cây nấm\n'
            '  "plots_summary": {\n'
            '    "has_ready_crops": false, // Có ô đất nào đã chín sẵn sàng thu hoạch không?\n'
            '    "has_empty_plots": false // Có ô đất nâu trống chưa gieo hạt không?\n'
            '  }\n'
            "}\n"
            f"Kích thước ảnh thực tế là: {img_width}x{img_height}. Tọa độ x, y phải nằm trong khung này."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 800,
            "temperature": 0.1
        }

        url = f"{self.base_url}/chat/completions"

        try:
            start_time = time.time()
            resp = self.session.post(url, headers=headers, json=payload, timeout=20)
            latency = round(time.time() - start_time, 2)

            if resp.status_code == 200:
                result_json = resp.json()
                raw_text = result_json["choices"][0]["message"]["content"].strip()

                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()

                data = json.loads(raw_text)
                sanitized = self.validate_and_sanitize(data, img_width, img_height)
                sanitized["success"] = True
                sanitized["latency"] = latency
                return sanitized
            else:
                return {
                    "success": False,
                    "error": f"API Error {resp.status_code}: {resp.text}",
                    "latency": latency
                }
        except Exception as e:
            return {"success": False, "error": f"Exception: {str(e)}"}

    @staticmethod
    def _to_bool(val: Any, default: bool = False) -> bool:
        """Ép kiểu boolean chuẩn xác, tránh lỗi chuỗi 'false' hoặc 'False' bị cast thành True."""
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val != 0
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ("true", "1", "yes", "t", "y"):
                return True
            if s in ("false", "0", "no", "f", "n", "none", "null"):
                return False
        return default

    @classmethod
    def validate_and_sanitize(cls, data: dict, max_w: int, max_h: int) -> dict:
        """
        Kiểm tra kiểu dữ liệu và giới hạn biên (Bounds checking) của kết quả JSON từ mô hình:
        - Đảm bảo tọa độ [x, y] không âm và không vượt quá kích thước màn hình.
        - Ép kiểu an toàn cho các trường boolean (tránh chuỗi 'false' thành True) và danh sách tọa độ.
        """
        to_b = cls._to_bool
        sanitized = {
            "has_blocking_popup": to_b(data.get("has_blocking_popup"), False),
            "popup_close_button": None,
            "is_syncing": to_b(data.get("is_syncing"), False),
            "has_captcha": to_b(data.get("has_captcha"), False),
            "captcha_details": str(data.get("captcha_details", "")) if data.get("captcha_details") else None,
            "has_mushrooms": to_b(data.get("has_mushrooms"), False),
            "mushroom_positions": [],
            "plots_summary": {
                "has_ready_crops": False,
                "has_empty_plots": False
            },
            "valid_schema": True
        }

        # 1. Kiểm tra tọa độ nút popup close
        close_btn = data.get("popup_close_button")
        if isinstance(close_btn, (list, tuple)) and len(close_btn) == 2:
            try:
                x, y = int(close_btn[0]), int(close_btn[1])
                if 0 <= x <= max_w and 0 <= y <= max_h:
                    sanitized["popup_close_button"] = [x, y]
            except (ValueError, TypeError):
                sanitized["valid_schema"] = False

        # 2. Kiểm tra danh sách tọa độ nấm
        mushrooms = data.get("mushroom_positions")
        if isinstance(mushrooms, list):
            valid_mushrooms = []
            for m in mushrooms:
                if isinstance(m, (list, tuple)) and len(m) == 2:
                    try:
                        x, y = int(m[0]), int(m[1])
                        if 0 <= x <= max_w and 0 <= y <= max_h:
                            valid_mushrooms.append([x, y])
                    except (ValueError, TypeError):
                        continue
            sanitized["mushroom_positions"] = valid_mushrooms

        # 3. Kiểm tra plots_summary
        plots = data.get("plots_summary")
        if isinstance(plots, dict):
            sanitized["plots_summary"]["has_ready_crops"] = to_b(plots.get("has_ready_crops"), False)
            sanitized["plots_summary"]["has_empty_plots"] = to_b(plots.get("has_empty_plots"), False)

        return sanitized

    def generate_narrative(self, prompt: str) -> Optional[str]:
        """
        Gửi prompt văn bản đến mô hình ngôn ngữ (Claude Haiku / OpenAI compatible)
        để sáng tạo cuốn nhật ký đời thường sinh động cho nhân vật.
        """
        if not self.api_key:
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 120,
            "temperature": 0.8
        }
        try:
            url = f"{self.base_url}/chat/completions"
            resp = self.session.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                result = resp.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                print(f"[AIVision Warning] Lỗi API LLM sinh nhật ký ({resp.status_code}): {resp.text}")
                return None
        except Exception as e:
            print(f"[AIVision Warning] Ngoại lệ khi gọi LLM sinh nhật ký: {e}")
            return None


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 3A: AI Vision Client ---")
    ai = AIVision()
    print("AI Vision Client san sang!")

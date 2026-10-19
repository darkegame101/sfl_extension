"""
HỆ THỐNG 3B: THỊ GIÁC CỤC BỘ OFFLINE & XÁC MINH VÒNG LẶP ĐÓNG (LOCAL VISION ENGINE)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Chạy cục bộ bằng OpenCV & NumPy (0ms cloud latency, 0đ token, hoạt động 100% offline)
"""

import math
import os
import sys
from typing import Dict, List, Optional, Tuple, Union, Any
import cv2
import numpy as np
from PIL import Image


class LocalVisionEngine:
    """
    Bộ động cơ thị giác máy tính cục bộ cho Sunflower Land:
    - Nhận diện trạng thái ô đất: GROWING (có timer), READY (chín), EMPTY (đất trống).
    - Định vị thanh công cụ Hotbar mép phải và tính tọa độ slot hạt giống.
    - So sánh sai khác trạng thái trước/sau thao tác (Closed-Loop Differential State Verification).
    """

    # Bảng dải màu HSV chuẩn cho Sunflower Land pixel art
    # Đất trống tilled soil: Tone nâu đặc trưng
    SOIL_HSV_LOWER = np.array([10, 60, 50])
    SOIL_HSV_UPPER = np.array([25, 255, 180])

    # Timer Badge: Hộp viền màu xanh đen / xám tối phía dưới cây
    TIMER_BADGE_HSV_LOWER = np.array([100, 30, 20])
    TIMER_BADGE_HSV_UPPER = np.array([140, 255, 80])

    # Màu mầm cây / lá cây xanh
    PLANT_GREEN_HSV_LOWER = np.array([35, 70, 70])
    PLANT_GREEN_HSV_UPPER = np.array([85, 255, 255])

    @staticmethod
    def to_cv2_image(img: Union[Image.Image, np.ndarray]) -> np.ndarray:
        """Chuyển đổi PIL Image hoặc ndarray sang chuẩn OpenCV BGR."""
        if isinstance(img, Image.Image):
            rgb = np.array(img.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        elif isinstance(img, np.ndarray):
            if len(img.shape) == 2:
                return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            return img
        raise ValueError(f"Khong the chuyen doi kieu du lieu {type(img)} sang OpenCV BGR!")

    @classmethod
    def get_roi(cls, img: np.ndarray, center_x: int, center_y: int, radius: int = 22) -> Optional[np.ndarray]:
        """Trích xuất vùng ảnh quan tâm (ROI) xung quanh tâm (center_x, center_y)."""
        h, w = img.shape[:2]
        x1 = max(0, int(center_x - radius))
        y1 = max(0, int(center_y - radius))
        x2 = min(w, int(center_x + radius))
        y2 = min(h, int(center_y + radius))

        if x2 <= x1 or y2 <= y1:
            return None
        return img[y1:y2, x1:x2]

    @classmethod
    def analyze_plot_state(cls, img_input: Union[Image.Image, np.ndarray], plot_x: int, plot_y: int) -> Dict[str, Any]:
        """
        Phân tích trạng thái thị giác của một ô đất tại tọa độ (plot_x, plot_y):
        - GROWING: Có timer badge hoặc thanh đếm giờ.
        - READY: Cây nở to/nông sản chín, không còn timer badge.
        - EMPTY: Ô đất trống, chỉ có màu nâu đất.
        """
        bgr = cls.to_cv2_image(img_input)
        roi = cls.get_roi(bgr, plot_x, plot_y, radius=22)
        if roi is None or roi.size == 0:
            return {"state": "UNKNOWN", "confidence": 0.0, "has_timer": False}

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        total_pixels = roi.shape[0] * roi.shape[1]

        # 1. Đo tỷ lệ diện tích hộp Timer Badge (phía dưới ô đất)
        # Timer box trong SFL thường ở nửa dưới của ô đất
        h_half = roi.shape[0] // 2
        lower_half_hsv = hsv[h_half:, :]
        badge_mask = cv2.inRange(lower_half_hsv, cls.TIMER_BADGE_HSV_LOWER, cls.TIMER_BADGE_HSV_UPPER)
        badge_ratio = float(np.count_nonzero(badge_mask)) / max(1, (lower_half_hsv.shape[0] * lower_half_hsv.shape[1]))

        # 2. Đo tỷ lệ đất trống màu nâu
        soil_mask = cv2.inRange(hsv, cls.SOIL_HSV_LOWER, cls.SOIL_HSV_UPPER)
        soil_ratio = float(np.count_nonzero(soil_mask)) / total_pixels

        # 3. Đo tỷ lệ màu cây xanh / nông sản
        plant_mask = cv2.inRange(hsv, cls.PLANT_GREEN_HSV_LOWER, cls.PLANT_GREEN_HSV_UPPER)
        plant_ratio = float(np.count_nonzero(plant_mask)) / total_pixels

        has_timer = badge_ratio > 0.08

        if has_timer:
            return {
                "state": "GROWING",
                "confidence": min(1.0, 0.75 + badge_ratio),
                "has_timer": True,
                "badge_ratio": round(badge_ratio, 3),
                "soil_ratio": round(soil_ratio, 3)
            }
        elif plant_ratio > 0.18:
            return {
                "state": "READY",
                "confidence": min(1.0, 0.70 + plant_ratio),
                "has_timer": False,
                "plant_ratio": round(plant_ratio, 3),
                "soil_ratio": round(soil_ratio, 3)
            }
        elif soil_ratio > 0.25:
            return {
                "state": "EMPTY",
                "confidence": min(1.0, 0.65 + soil_ratio),
                "has_timer": False,
                "soil_ratio": round(soil_ratio, 3)
            }
        else:
            return {
                "state": "UNKNOWN",
                "confidence": 0.5,
                "has_timer": False,
                "badge_ratio": round(badge_ratio, 3),
                "soil_ratio": round(soil_ratio, 3),
                "plant_ratio": round(plant_ratio, 3)
            }

    @classmethod
    def get_hotbar_seed_coords(
        cls,
        window_width: int,
        window_height: int,
        slot_index: int = 1
    ) -> Tuple[int, int]:
        """
        Tính toán tọa độ thích ứng của ô Slot trên thanh Hotbar mép phải:
        - Slot 1: Hạt giống chính (Sunflower / Potato...)
        - Slot 2: Hạt giống phụ / hoa
        - Slot 3: Rìu / Công cụ
        Thanh Hotbar luôn bám sát lề phải màn hình (Right margin ≈ 25 - 35px).
        """
        right_margin_offset = 32
        x = window_width - right_margin_offset

        # Tọa độ Y cơ sở cho Hotbar trong Sunflower Land
        # Bắt đầu dưới cụm nút Chest/Tools (khoảng Y = 270 với tỷ lệ tiêu chuẩn)
        base_y = int(window_height * 0.28)
        slot_gap = 48  # Khoảng cách giữa các ô slot (44-50px)

        y = base_y + (slot_index - 1) * slot_gap
        return x, y

    @classmethod
    def verify_action_diff(
        cls,
        pre_img: Union[Image.Image, np.ndarray],
        post_img: Union[Image.Image, np.ndarray],
        action_x: int,
        action_y: int,
        action_type: str = "harvest",
        radius: int = 24
    ) -> Dict[str, Any]:
        """
        XÁC MINH HẬU KIỂM VÒNG LẶP ĐÓNG (CLOSED-LOOP DIFFERENTIAL VERIFICATION):
        - So sánh vùng ROI trước và sau thao tác chuột.
        - Đo độ sai khác pixel và chuyển dịch trạng thái:
          + "harvest": từ READY -> EMPTY (hoặc pixel delta > 9%)
          + "plant": từ EMPTY -> SEEDLING/GROWING (pixel delta > 6%)
        """
        pre_bgr = cls.to_cv2_image(pre_img)
        post_bgr = cls.to_cv2_image(post_img)

        pre_roi = cls.get_roi(pre_bgr, action_x, action_y, radius=radius)
        post_roi = cls.get_roi(post_bgr, action_x, action_y, radius=radius)

        if pre_roi is None or post_roi is None or pre_roi.shape != post_roi.shape:
            return {
                "verified": False,
                "status": "VERIFY_ERROR",
                "reason": "ROI out of bounds or shape mismatch",
                "delta": 0.0
            }

        # 1. Tính toán hiệu số sai khác pixel (Absolute Difference)
        diff = cv2.absdiff(pre_roi, post_roi)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, 20, 255, cv2.THRESH_BINARY)
        delta_ratio = float(np.count_nonzero(thresh)) / (thresh.shape[0] * thresh.shape[1])

        # 2. Phân tích trạng thái sau thao tác
        post_state_info = cls.analyze_plot_state(post_bgr, action_x, action_y)
        post_state = post_state_info.get("state", "UNKNOWN")

        # 3. Đánh giá tính thành công theo logic nghiệp vụ
        if action_type == "harvest":
            is_success = delta_ratio >= 0.09 or post_state == "EMPTY"
        elif action_type == "plant":
            is_success = delta_ratio >= 0.06 or post_state in ("GROWING", "READY")
        else:
            is_success = delta_ratio >= 0.05

        return {
            "verified": is_success,
            "status": "VERIFIED_SUCCESS" if is_success else "VERIFIED_NO_CHANGE",
            "delta_ratio": round(delta_ratio, 4),
            "post_state": post_state,
            "confidence": post_state_info.get("confidence", 0.0)
        }


if __name__ == "__main__":
    print("--- Test He thong 3B: Local Vision Engine ---")
    dummy = np.zeros((600, 800, 3), dtype=np.uint8)
    dummy[250:300, 350:400] = [35, 75, 120]
    res = LocalVisionEngine.analyze_plot_state(dummy, 375, 275)
    print("Ket qua phan tich o mau dat:", res)
    hotbar_x, hotbar_y = LocalVisionEngine.get_hotbar_seed_coords(1920, 1080, slot_index=1)
    print(f"Toa do Hotbar Slot 1 tren man hinh 1920x1080: ({hotbar_x}, {hotbar_y})")
    print("Local Vision Engine khoi tao thanh cong 100%!")

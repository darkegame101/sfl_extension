"""
HỆ THỐNG 5B: SĂN NẤM HOANG DÃ (MUSHROOM HUNTER)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Tự động nhặt nấm Wild/Magic Mushrooms khi AI phát hiện trên bãi cỏ
"""

import os
import sys
import time
from typing import List, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.human_mouse import HumanMouse
from core.window_helper import WindowHelper


class MushroomHunter:
    """
    Tự động nhặt nấm mọc trên các thảm cỏ:
    - Nhận danh sách tọa độ nấm do AI Vision phát hiện.
    - Di chuyển chuột uốn lượn Bézier tới nhặt từng cây nấm.
    """

    @staticmethod
    def harvest_mushrooms(hwnd: int, mushroom_coords: List[Tuple[int, int]], is_screen_coords: bool = True):
        if not mushroom_coords:
            return

        print(f"[MushroomHunter] Phát hiện {len(mushroom_coords)} cây nấm! Đang tiến hành nhặt...")
        for idx, (coord_x, coord_y) in enumerate(mushroom_coords, 1):
            if is_screen_coords or hwnd == 0:
                screen_x, screen_y = int(coord_x), int(coord_y)
            else:
                screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, int(coord_x), int(coord_y))

            print(f" -> Nhặt nấm thứ {idx} tại ({screen_x}, {screen_y})...")
            HumanMouse.click(screen_x, screen_y, random_offset=3)
            HumanMouse.human_sleep(0.6, 1.0)

        print("[MushroomHunter] Đã nhặt xong toàn bộ nấm trên nông trại!")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 5B: Mushroom Hunter ---")
    print("Mushroom Hunter khoi tao thanh cong!")

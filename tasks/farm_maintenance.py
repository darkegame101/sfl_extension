"""
HỆ THỐNG 5C: QUẢN TRỊ NÔNG TRẠI ĐA NHIỆM (FARM MAINTENANCE)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Điều phối các tác vụ Phụ trợ (Chặt cây, Thu hoạch Mật ong, Nạp Composter)
"""

import random
import time
from typing import List, Tuple, Dict, Any
from core.human_mouse import HumanMouse
from core.window_helper import WindowHelper


class FarmMaintenance:
    """
    Xử lý các tác vụ đa nhiệm phụ trợ khi SessionPlan phân loại phiên là STANDARD hoặc FULL_MAINTENANCE:
    1. Chặt cây (TREES): Di chuyển đến từng gốc cây, click nhiều nhịp kèm độ rung tự nhiên.
    2. Thu mật ong (HONEY): Thu hoạch tổ ong khi có hiệu ứng hoa nở và mật đầy.
    3. Nạp thùng ủ phân (COMPOSTER): Bấm nạp rơm rạ / phế phẩm nông nghiệp vào thùng ủ.
    """

    @staticmethod
    def chop_trees(hwnd: int, tree_coords: List[Tuple[int, int]], scenario: Dict[str, Any] = None):
        """Chặt cây lấy gỗ theo danh sách tọa độ."""
        if not tree_coords or not hwnd:
            return

        miss_prob = scenario.get("effective_miss_click_prob", scenario.get("miss_click_prob", 0.05)) if scenario else 0.05
        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0
        print(f"[FarmMaintenance] Bắt đầu đốn hạ {len(tree_coords)} cây cổ thụ trên đảo (Tốc độ: {speed_mult:.2f}x)...")

        for idx, (rel_x, rel_y) in enumerate(tree_coords, 1):
            screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, rel_x, rel_y)
            print(f" -> Đang chặt cây thứ {idx} tại ({screen_x}, {screen_y})...")

            # Click nhiều nhịp (3 - 5 nhịp búa đốn cây)
            strikes = random.randint(3, 5)
            for s in range(strikes):
                if random.random() < miss_prob:
                    HumanMouse.fumble_click(screen_x, screen_y, miss_offset=12)
                else:
                    HumanMouse.click(screen_x, screen_y, random_offset=4)
                HumanMouse.human_sleep(0.35 * speed_mult, 0.65 * speed_mult)

            # Nghỉ nhịp thở giữa 2 cây
            HumanMouse.human_sleep(0.8 * speed_mult, 1.6 * speed_mult)

        print("[FarmMaintenance] Đã đốn hạ xong toàn bộ cây theo kế hoạch phiên!")

    @staticmethod
    def harvest_honey(hwnd: int, beehive_coords: List[Tuple[int, int]], scenario: Dict[str, Any] = None):
        """Thu hoạch mật ong từ các tổ ong chín."""
        if not beehive_coords or not hwnd:
            return

        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0
        print(f"[FarmMaintenance] Đang thu hoạch {len(beehive_coords)} tổ ong mật (Tốc độ: {speed_mult:.2f}x)...")
        for idx, (rel_x, rel_y) in enumerate(beehive_coords, 1):
            screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, rel_x, rel_y)
            print(f" -> Thu mật tại tổ {idx} ({screen_x}, {screen_y})...")
            HumanMouse.click(screen_x, screen_y, random_offset=3)
            HumanMouse.human_sleep(0.6 * speed_mult, 1.2 * speed_mult)

        print("[FarmMaintenance] Đã thu hoạch xong mật ong!")

    @staticmethod
    def manage_composter(hwnd: int, composter_coord: Tuple[int, int], scenario: Dict[str, Any] = None):
        """Bấm nạp phế phẩm hữu cơ vào thùng ủ phân Composter."""
        if not composter_coord or not hwnd:
            return

        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0
        screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, composter_coord[0], composter_coord[1])
        print(f"[FarmMaintenance] Đang kiểm tra và nạp phế phẩm vào thùng Composter tại ({screen_x}, {screen_y}) (Tốc độ: {speed_mult:.2f}x)...")
        HumanMouse.click(screen_x, screen_y, random_offset=4)
        HumanMouse.human_sleep(0.8 * speed_mult, 1.5 * speed_mult)
        print("[FarmMaintenance] Đã nạp Composter thành công!")

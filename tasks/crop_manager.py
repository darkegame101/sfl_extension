"""
HỆ THỐNG 5A: QUẢN LÝ THU HOẠCH & GIEO HẠT (CROP MANAGER)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Thực thi thao tác farm bằng chuột phần cứng Win32 có nhịp thở và xáo trộn ô
"""

import os
import random
import sys
import time
from typing import List, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.human_mouse import HumanMouse
from core.window_helper import WindowHelper
from core.local_vision_engine import LocalVisionEngine
from scheduler.farm_memory import FarmMemory


class CropManager:
    """
    Quản lý thu hoạch và gieo trồng trên các ô đất:
    - Bắn sự kiện chuột phần cứng thật (SendInput).
    - Có nhịp thở sau mỗi cú click (450ms - 850ms) để game đồng bộ với server.
    - Xáo trộn ngẫu nhiên thứ tự ô đất (Shuffle) để không tạo thành pattern robot.
    """

    def __init__(self, farm_memory: FarmMemory, sync_delay: Tuple[float, float] = (0.45, 0.85)):
        self.memory = farm_memory
        self.sync_delay = sync_delay

    def harvest_plots(
        self,
        hwnd: int,
        plot_coords: List[Tuple[int, int]],
        scenario: dict = None
    ):
        """
        Thu hoạch danh sách các ô đất chín:
        - Xáo trộn ngẫu nhiên thứ tự thu hoạch.
        - TÍNH BẤT ĐỊNH:
          + Xác suất xảy ra Miss-click (bấm trượt rìa ô đất rồi bấm lại).
          + Xác suất xảy ra Xao nhãng AFK (dừng lại 15-35s như có điện thoại).
          + Xác suất di chuột lơ đễnh ngắm cảnh.
        """
        if not plot_coords:
            return

        miss_prob = scenario.get("effective_miss_click_prob", scenario.get("miss_click_prob", scenario.get("fumble_rate", 0.05))) if scenario else 0.05
        distract_prob = scenario.get("effective_distraction_prob", scenario.get("distraction_prob", scenario.get("distract_rate", 0.10))) if scenario else 0.10
        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0

        # Xáo trộn ngẫu nhiên thứ tự click
        plots = list(plot_coords)
        random.shuffle(plots)

        # Quyết định vị trí xảy ra xao nhãng (nếu có)
        trigger_distract_at = random.randint(2, max(2, len(plots) - 1)) if (random.random() < distract_prob) else -1

        print(f"[CropManager] Bắt đầu thu hoạch {len(plots)} ô đất (Tốc độ: {speed_mult:.2f}x, Xác suất trượt: {miss_prob*100:.1f}%, Xao nhãng: {distract_prob*100:.1f}%)...")
        for idx, (rel_x, rel_y) in enumerate(plots, 1):
            screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, rel_x, rel_y)

            # 1. Yếu tố bất định: Click trượt (Fumble click)
            if random.random() < miss_prob:
                print(f"[CropManager Chaos] Xảy ra cú click trượt ô đất thứ {idx}!")
                HumanMouse.fumble_click(screen_x, screen_y, miss_offset=18)
            else:
                HumanMouse.click(screen_x, screen_y, random_offset=5)

            # 2. Yếu tố bất định: Xao nhãng AFK giữa chừng
            if idx == trigger_distract_at:
                HumanMouse.simulate_distraction(min_sec=10.0, max_sec=30.0)

            # 3. Yếu tố bất định: Di chuột lơ đễnh ngắm cảnh (3% xác suất)
            if random.random() < 0.03:
                HumanMouse.idle_wandering(duration=1.8 * speed_mult)

            # Nhịp thở chờ game gửi POST và cập nhật state (Sync Delay) có nhân hệ số tốc độ Persona
            HumanMouse.human_sleep(self.sync_delay[0] * speed_mult, self.sync_delay[1] * speed_mult)

        print(f"[CropManager] Đã thu hoạch xong {len(plots)} ô đất!")

    def ensure_active_seed_tool(
        self,
        hwnd: int,
        slot_index: int = 1,
        crop_name: str = "Sunflower",
        speed_mult: float = 1.0
    ):
        """
        KÍCH HOẠT HẠT GIỐNG TRÊN THANH HOTBAR BÊN PHẢI (ACTIVE TOOL SELECTOR):
        - Nếu người chơi đang cầm Rìu (Axe) hoặc Hạt hoa, click vào đất trống sẽ không thể trồng cây.
        - Hàm này di chuyển chuột sang mép phải màn hình (Slot 1 của Hotbar) để click chọn hạt giống.
        """
        cx, cy, cw, ch = WindowHelper.get_client_rect_on_screen(hwnd)
        if cw <= 0 or ch <= 0:
            return

        rel_x, rel_y = LocalVisionEngine.get_hotbar_seed_coords(cw, ch, slot_index=slot_index)
        hotbar_sx = cx + rel_x
        hotbar_sy = cy + rel_y

        print(f"[CropManager Hotbar] Kích hoạt hạt giống '{crop_name}' (Slot {slot_index}) tại ({hotbar_sx}, {hotbar_sy})...")
        # Rê chuột tò mò rồi click chọn
        HumanMouse.curiosity_hover(hotbar_sx, hotbar_sy, hover_sec=0.35 * speed_mult)
        HumanMouse.click(hotbar_sx, hotbar_sy, random_offset=3)
        # Nghỉ nhẹ để game phản hồi và kích hoạt item trên tay
        HumanMouse.human_sleep(0.35 * speed_mult, 0.65 * speed_mult)

    def plant_plots(
        self,
        hwnd: int,
        seed_box_coord: Tuple[int, int],
        plot_coords: List[Tuple[int, int]],
        profile_id: str,
        crop_name: str = "Sunflower",
        grow_seconds: int = 60,
        scenario: dict = None,
        profile_name: str = ""
    ):
        """
        Gieo hạt vào danh sách các ô đất trống:
        1. Kích hoạt hạt giống trên thanh Hotbar bên phải (đảm bảo không bị kẹt Rìu).
        2. Click lần lượt vào từng ô đất trống kèm yếu tố bất định.
        3. Ghi nhớ vào FarmMemory để hẹn giờ cho phiên sau.
        """
        if not plot_coords:
            return

        miss_prob = scenario.get("effective_miss_click_prob", scenario.get("miss_click_prob", scenario.get("fumble_rate", 0.05))) if scenario else 0.05
        distract_prob = scenario.get("effective_distraction_prob", scenario.get("distraction_prob", scenario.get("distract_rate", 0.10))) if scenario else 0.10
        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0

        # 1. BƯỚC MẤU CHỐT: Đảm bảo đã chọn hạt giống trên Hotbar bên phải
        self.ensure_active_seed_tool(hwnd, slot_index=1, crop_name=crop_name, speed_mult=speed_mult)

        # Fallback click thêm giỏ hạt nếu có cấu hình tọa độ giỏ hạt riêng
        if seed_box_coord and (seed_box_coord[0] != 400 or seed_box_coord[1] != 560):
            seed_sx, seed_sy = WindowHelper.to_screen_coords(hwnd, seed_box_coord[0], seed_box_coord[1])
            print(f"[CropManager] Click phụ trợ giỏ hạt tại ({seed_sx}, {seed_sy})...")
            HumanMouse.click(seed_sx, seed_sy, random_offset=4)
            HumanMouse.human_sleep(0.3 * speed_mult, 0.6 * speed_mult)

        # 2. Gieo vào từng ô đất
        plots = list(plot_coords)
        random.shuffle(plots)

        trigger_distract_at = random.randint(2, max(2, len(plots) - 1)) if (random.random() < distract_prob) else -1

        print(f"[CropManager] Đang gieo hạt vào {len(plots)} ô đất (Tốc độ: {speed_mult:.2f}x)...")
        for idx, (rel_x, rel_y) in enumerate(plots, 1):
            screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, rel_x, rel_y)

            if random.random() < miss_prob:
                HumanMouse.fumble_click(screen_x, screen_y, miss_offset=18)
            else:
                HumanMouse.click(screen_x, screen_y, random_offset=5)

            if idx == trigger_distract_at:
                HumanMouse.simulate_distraction(min_sec=8.0, max_sec=25.0)

            HumanMouse.human_sleep(self.sync_delay[0] * speed_mult, self.sync_delay[1] * speed_mult)

        # 3. Ghi nhớ chu kỳ cây vào FarmMemory
        self.memory.record_planting(profile_id, crop_name, grow_seconds, profile_name=profile_name)
        print(f"[CropManager] Gieo xong toàn bộ {len(plots)} ô đất và đã hẹn giờ thành công!")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 5A: Crop Manager ---")
    mem = FarmMemory("test_memory_crop.json")
    cm = CropManager(mem)
    print("Crop Manager khoi tao thanh cong!")
    if os.path.exists("test_memory_crop.json"):
        os.remove("test_memory_crop.json")

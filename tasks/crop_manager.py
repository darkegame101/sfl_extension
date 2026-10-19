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
    ) -> dict:
        """
        Thu hoạch danh sách các ô đất chín:
        - Chuyển đổi tọa độ tương đối sang tọa độ màn hình thực tế.
        - Phát lệnh click thu hoạch cho từng ô đất.
        - Trả về báo cáo trạng thái phát lệnh (COMMANDS_ISSUED).
        """
        if not plot_coords:
            return {
                "plots_targeted": 0,
                "commands_attempted": 0,
                "commands_issued": 0,
                "status": "NOOP",
                "verified": False
            }

        if not hwnd or hwnd <= 0:
            return {
                "plots_targeted": len(plot_coords),
                "commands_attempted": 0,
                "commands_issued": 0,
                "status": "INVALID_HWND",
                "verified": False
            }

        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0

        plots = list(plot_coords)
        random.shuffle(plots)

        print(f"[CropManager] Bắt đầu thu hoạch {len(plots)} ô đất (Tốc độ: {speed_mult:.2f}x)...")
        commands_attempted = 0
        commands_issued = 0
        loop_error = None

        try:
            for idx, (rel_x, rel_y) in enumerate(plots, 1):
                screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, rel_x, rel_y)

                commands_attempted += 1
                HumanMouse.click(screen_x, screen_y, random_offset=5)
                commands_issued += 1

                # Nhịp thở chờ game gửi POST và cập nhật state (Sync Delay) có nhân hệ số tốc độ Persona
                HumanMouse.human_sleep(self.sync_delay[0] * speed_mult, self.sync_delay[1] * speed_mult)
        except Exception as e:
            loop_error = str(e)
            print(f"[CropManager Exception] Lỗi gián đoạn khi thu hoạch ô {commands_attempted}/{len(plots)}: {e}")

        if loop_error:
            status = "PARTIALLY_EXECUTED" if commands_issued > 0 else "FAILED"
        else:
            status = "COMMANDS_ISSUED"

        print(f"[CropManager] Kết quả phát lệnh thu hoạch: {commands_issued}/{len(plots)} ô (Status: {status})")
        return {
            "plots_targeted": len(plots),
            "commands_attempted": commands_attempted,
            "commands_issued": commands_issued,
            "status": status,
            "error": loop_error,
            "verified": False
        }

    def ensure_active_seed_tool(
        self,
        hwnd: int,
        slot_index: int = 1,
        crop_name: str = "Sunflower",
        speed_mult: float = 1.0
    ) -> dict:
        """
        KÍCH HOẠT HẠT GIỐNG TRÊN THANH HOTBAR BÊN PHẢI (ACTIVE TOOL SELECTOR):
        - Nếu người chơi đang cầm Rìu (Axe) hoặc Hạt hoa, click vào đất trống sẽ không thể trồng cây.
        - Hàm này di chuyển chuột sang mép phải màn hình (Slot 1 của Hotbar) để click chọn hạt giống.
        """
        if not hwnd or hwnd <= 0:
            return {"success": False, "reason": "INVALID_HWND"}

        cx, cy, cw, ch = WindowHelper.get_client_rect_on_screen(hwnd)
        if cw <= 0 or ch <= 0:
            return {"success": False, "reason": "INVALID_CLIENT_RECT"}

        rel_x, rel_y = LocalVisionEngine.get_hotbar_seed_coords(cw, ch, slot_index=slot_index)
        hotbar_sx = cx + rel_x
        hotbar_sy = cy + rel_y

        print(f"[CropManager Hotbar] Kích hoạt hạt giống '{crop_name}' (Slot {slot_index}) tại ({hotbar_sx}, {hotbar_sy})...")
        # Rê chuột tò mò rồi click chọn
        HumanMouse.curiosity_hover(hotbar_sx, hotbar_sy, hover_sec=0.35 * speed_mult)
        HumanMouse.click(hotbar_sx, hotbar_sy, random_offset=3)
        # Nghỉ nhẹ để game phản hồi và kích hoạt item trên tay
        HumanMouse.human_sleep(0.35 * speed_mult, 0.65 * speed_mult)
        return {
            "success": True,
            "target": (hotbar_sx, hotbar_sy),
            "status": "COMMANDS_ISSUED"
        }

    def plant_plots(
        self,
        hwnd: int,
        seed_box_coord: Tuple[int, int],
        plot_coords: List[Tuple[int, int]],
        profile_id: str,
        crop_name: str = "Sunflower",
        grow_seconds: int = 60,
        scenario: dict = None,
        profile_name: str = "",
        record_memory: bool = True
    ) -> dict:
        """
        Gieo hạt vào danh sách các ô đất trống:
        1. Kích hoạt hạt giống trên thanh Hotbar bên phải (đảm bảo không bị kẹt Rìu).
           Nếu kích hoạt tool thất bại, DỪNG LẠI NGAY LẬP TỨC để tránh click sai.
        2. Click lần lượt vào từng ô đất trống kèm cơ chế bắt lỗi giữa vòng lặp.
        3. Ghi nhớ vào FarmMemory để hẹn giờ cho phiên sau (chỉ khi có ít nhất 1 lệnh được phát thành công).
        """
        if not plot_coords:
            return {
                "plots_targeted": 0,
                "commands_attempted": 0,
                "commands_issued": 0,
                "status": "NOOP",
                "verified": False
            }

        if not hwnd or hwnd <= 0:
            return {
                "plots_targeted": len(plot_coords),
                "commands_attempted": 0,
                "commands_issued": 0,
                "status": "INVALID_HWND",
                "verified": False
            }

        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0

        # 1. BƯỚC MẤU CHỐT: Đảm bảo đã chọn hạt giống trên Hotbar bên phải
        tool_res = self.ensure_active_seed_tool(hwnd, slot_index=1, crop_name=crop_name, speed_mult=speed_mult)
        if not tool_res.get("success", False):
            print(f"[CropManager Error] Chọn hạt giống '{crop_name}' thất bại ({tool_res.get('reason')}). HỦY thao tác gieo hạt.")
            return {
                "plots_targeted": len(plot_coords),
                "commands_attempted": 0,
                "commands_issued": 0,
                "tool_selected": tool_res,
                "status": "TOOL_SELECTION_FAILED",
                "error": tool_res.get("reason", "Failed to select seed tool"),
                "verified": False
            }

        # Fallback click thêm giỏ hạt nếu có cấu hình tọa độ giỏ hạt riêng
        if seed_box_coord and (seed_box_coord[0] != 400 or seed_box_coord[1] != 560):
            seed_sx, seed_sy = WindowHelper.to_screen_coords(hwnd, seed_box_coord[0], seed_box_coord[1])
            print(f"[CropManager] Click phụ trợ giỏ hạt tại ({seed_sx}, {seed_sy})...")
            HumanMouse.click(seed_sx, seed_sy, random_offset=4)
            HumanMouse.human_sleep(0.3 * speed_mult, 0.6 * speed_mult)

        # 2. Gieo vào từng ô đất kèm bảo vệ ngoại lệ giữa chừng
        plots = list(plot_coords)
        random.shuffle(plots)

        commands_attempted = 0
        commands_issued = 0
        loop_error = None

        print(f"[CropManager] Đang gieo hạt vào {len(plots)} ô đất (Tốc độ: {speed_mult:.2f}x)...")
        try:
            for idx, (rel_x, rel_y) in enumerate(plots, 1):
                screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, rel_x, rel_y)

                commands_attempted += 1
                HumanMouse.click(screen_x, screen_y, random_offset=5)
                commands_issued += 1

                HumanMouse.human_sleep(self.sync_delay[0] * speed_mult, self.sync_delay[1] * speed_mult)
        except Exception as e:
            loop_error = str(e)
            print(f"[CropManager Exception] Lỗi gián đoạn khi gieo ô {commands_attempted}/{len(plots)}: {e}")

        if loop_error:
            status = "PARTIALLY_EXECUTED" if commands_issued > 0 else "FAILED"
        else:
            status = "COMMANDS_ISSUED"

        # 3. Ghi nhớ chu kỳ cây vào FarmMemory (chỉ khi có lệnh được phát và không lỗi hoàn toàn)
        if record_memory and commands_issued > 0 and not loop_error:
            self.memory.record_planting(profile_id, crop_name, grow_seconds, profile_name=profile_name)
            print(f"[CropManager] Gieo xong toàn bộ {len(plots)} ô đất và đã hẹn giờ thành công!")
        elif loop_error and commands_issued > 0 and record_memory:
            # Gieo một phần: vẫn ghi nhận nhưng cảnh báo chưa hoàn tất
            self.memory.record_planting(profile_id, crop_name, grow_seconds, profile_name=profile_name)
            print(f"[CropManager Warning] Đã gieo được {commands_issued}/{len(plots)} ô đất trước khi bị lỗi gián đoạn.")

        return {
            "plots_targeted": len(plots),
            "commands_attempted": commands_attempted,
            "commands_issued": commands_issued,
            "tool_selected": tool_res,
            "status": status,
            "error": loop_error,
            "verified": False
        }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 5A: Crop Manager ---")
    mem = FarmMemory("test_memory_crop.json")
    cm = CropManager(mem)
    print("Crop Manager khoi tao thanh cong!")
    if os.path.exists("test_memory_crop.json"):
        os.remove("test_memory_crop.json")

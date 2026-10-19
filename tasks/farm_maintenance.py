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
    def _calculate_strikes_for_tree(scenario: Dict[str, Any] = None, base_hits: int = 3) -> int:
        """
        Tính số nhát click cho 1 gốc cây:
        - Tối thiểu base_hits = 3 (đảm bảo cây ngã theo luật game Sunflower Land).
        - Tính chất người thật: Đôi khi nhấp 4 cái (quán tính tay / bấm dứt khoát cho chắc)
          hoặc 5 cái (khi vội vã, sốt ruột, spam click).
        """
        mood = str(scenario.get("current_mood", "")).lower() if scenario else ""
        if any(m in mood for m in ["vội", "căng", "rush", "deadline", "urgency"]):
            # Người vội vã/căng thẳng: 48% nhấp 3 cái, 40% nhấp 4 cái, 12% nhấp 5 cái
            return random.choices([base_hits, base_hits + 1, base_hits + 2], weights=[0.48, 0.40, 0.12])[0]
        else:
            # Người bình thường/thong thả: 65% nhấp 3 cái, 28% nhấp 4 cái, 7% nhấp 5 cái
            return random.choices([base_hits, base_hits + 1, base_hits + 2], weights=[0.65, 0.28, 0.07])[0]

    @staticmethod
    def _get_inter_strike_delay(hit_index: int, total_hits: int, speed_mult: float) -> float:
        """
        Tính khoảng thời gian chờ giữa các nhát click (Inter-Strike Interval):
        - Không bao giờ cố định như máy đếm nhịp (Metronome).
        - Nhát 1 -> Nhát 2: Nhịp gõ liên tiếp ban đầu (360ms - 540ms).
        - Nhát 2 -> Nhát 3: Người chơi khựng lại 1 nhịp ngắn nhìn cây rung / thanh HP (480ms - 720ms).
        - Nhát 3 -> Nhát 4+ (nếu có click dư): Nhát vung theo đà rất nhanh (220ms - 400ms).
        - Điều chỉnh linh hoạt theo tốc độ thực tế (speed_mult) và rung lắc vi mô (±10%).
        """
        if hit_index == 1:
            base = random.uniform(0.36, 0.54)
        elif hit_index == 2:
            base = random.uniform(0.48, 0.72)
        else:
            base = random.uniform(0.22, 0.40)

        jitter = random.uniform(0.90, 1.10)
        return max(0.18, base * speed_mult * jitter)

    @staticmethod
    def chop_trees(
        hwnd: int,
        tree_coords: List[Tuple[int, int]],
        scenario: Dict[str, Any] = None,
        hits_per_tree: int = 3
    ) -> Dict[str, Any]:
        """
        Chặt cây lấy gỗ theo danh sách tọa độ:
        - Di chuyển chuột tới từng gốc cây (move_to 1 lần duy nhất trên mỗi cây).
        - Thực hiện các nhát đốn liên tiếp tại chỗ qua click_in_place(), loại bỏ chi phí tính quỹ đạo Bézier lặp lại.
        - Phát lệnh đốn gỗ (COMMAND_ISSUED). Lưu ý: Việc phát lệnh không cấu thành bằng chứng cây đã đốn ngã thành công.
        """
        if not tree_coords or not hwnd:
            return {"trees_targeted": 0, "commands_issued": 0, "status": "NOOP", "verified": False}

        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0

        print(f"[FarmMaintenance] Bắt đầu đốn hạ {len(tree_coords)} cây trên đảo (Chuẩn tối thiểu {hits_per_tree} nhát/cây, Tốc độ: {speed_mult:.2f}x)...")

        total_commands_issued = 0

        for idx, (rel_x, rel_y) in enumerate(tree_coords, 1):
            screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, rel_x, rel_y)

            # 1. Định vị con trỏ chuột tới thân cây (Duy nhất 1 lần cho cây này)
            HumanMouse.move_to(screen_x, screen_y)

            # 2. Số nhát click mục tiêu theo cấu hình
            target_hits = FarmMaintenance._calculate_strikes_for_tree(scenario, base_hits=hits_per_tree) if scenario else hits_per_tree
            print(f" -> Đang chặt cây thứ {idx}/{len(tree_coords)} tại ({screen_x}, {screen_y}) | Kế hoạch: {target_hits} nhát...")

            for hit_idx in range(1, target_hits + 1):
                click_res = HumanMouse.click_in_place(button='left')
                if not click_res:
                    print(f"    [FarmMaintenance] Cảnh báo: Lệnh click_in_place #{hit_idx} thất bại: {click_res.error}")
                else:
                    total_commands_issued += 1
                    strike_label = f"#{hit_idx}/{target_hits}"
                    print(f"    * Nhát đốn gỗ {strike_label} đã phát lệnh...")

                if hit_idx < target_hits:
                    delay = FarmMaintenance._get_inter_strike_delay(hit_idx, target_hits, speed_mult)
                    time.sleep(delay)

            # Nghỉ nhịp thở giữa 2 cây liên tiếp
            inter_tree_rest = random.uniform(0.75, 1.45) * speed_mult
            time.sleep(inter_tree_rest)

        print(f"[FarmMaintenance] Đã phát xong lệnh đốn hạ {len(tree_coords)} cây theo kế hoạch phiên!")
        return {
            "trees_targeted": len(tree_coords),
            "commands_issued": total_commands_issued,
            "status": "COMMANDS_ISSUED",
            "verified": False
        }

    @staticmethod
    def harvest_honey(hwnd: int, beehive_coords: List[Tuple[int, int]], scenario: Dict[str, Any] = None) -> Dict[str, Any]:
        """Thu hoạch mật ong từ các tổ ong chín."""
        if not beehive_coords or not hwnd:
            return {"beehives_targeted": 0, "commands_issued": 0, "status": "NOOP", "verified": False}

        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0
        print(f"[FarmMaintenance] Đang thu hoạch {len(beehive_coords)} tổ ong mật (Tốc độ: {speed_mult:.2f}x)...")
        commands_issued = 0
        loop_error = None

        try:
            for idx, (rel_x, rel_y) in enumerate(beehive_coords, 1):
                screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, rel_x, rel_y)
                print(f" -> Thu mật tại tổ {idx} ({screen_x}, {screen_y})...")
                HumanMouse.click(screen_x, screen_y, random_offset=3)
                commands_issued += 1
                HumanMouse.human_sleep(0.6 * speed_mult, 1.2 * speed_mult)
        except Exception as e:
            loop_error = str(e)
            print(f"[FarmMaintenance Exception] Lỗi khi thu hoạch mật ong: {e}")

        status = "PARTIALLY_EXECUTED" if loop_error and commands_issued > 0 else ("FAILED" if loop_error else "COMMANDS_ISSUED")
        print(f"[FarmMaintenance] Đã thu hoạch xong mật ong (Status: {status}, Issued: {commands_issued}/{len(beehive_coords)})!")
        return {
            "beehives_targeted": len(beehive_coords),
            "commands_issued": commands_issued,
            "status": status,
            "error": loop_error,
            "verified": False
        }

    @staticmethod
    def manage_composter(hwnd: int, composter_coord: Tuple[int, int], scenario: Dict[str, Any] = None) -> Dict[str, Any]:
        """Bấm nạp phế phẩm hữu cơ vào thùng ủ phân Composter."""
        if not composter_coord or not hwnd:
            return {"composter_targeted": 0, "commands_issued": 0, "status": "NOOP", "verified": False}

        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0
        commands_issued = 0
        error = None

        try:
            screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, composter_coord[0], composter_coord[1])
            print(f"[FarmMaintenance] Đang kiểm tra và nạp phế phẩm vào thùng Composter tại ({screen_x}, {screen_y}) (Tốc độ: {speed_mult:.2f}x)...")
            HumanMouse.click(screen_x, screen_y, random_offset=4)
            commands_issued = 1
            HumanMouse.human_sleep(0.8 * speed_mult, 1.5 * speed_mult)
            status = "COMMANDS_ISSUED"
            print("[FarmMaintenance] Đã nạp Composter thành công!")
        except Exception as e:
            error = str(e)
            status = "FAILED"
            print(f"[FarmMaintenance Exception] Lỗi khi nạp Composter: {e}")

        return {
            "composter_targeted": 1,
            "commands_issued": commands_issued,
            "status": status,
            "error": error,
            "verified": False
        }

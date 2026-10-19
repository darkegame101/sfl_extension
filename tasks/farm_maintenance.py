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
    ):
        """
        Chặt cây lấy gỗ theo danh sách tọa độ:
        - Quy chuẩn Sunflower Land: Mỗi cây cần đúng tối thiểu 3 nhát click thành công để đốn hạ.
        - Mô phỏng hành vi người thật:
          + Số nhát click có tính bất định: Thường là 3 nhát, nhưng 35% trường hợp nhấp 4-5 nhát do quán tính ngón tay.
          + Thời gian giữa các nhát click có độ chênh lệch sinh học rõ rệt (Inter-Strike Jitter), không đều chằn chặn.
          + Tự phục hồi sau click trượt (fumble_click): Bù thêm nhát để đảm bảo cây luôn được đốn ngã.
          + Nghỉ nhịp thở tự nhiên giữa 2 gốc cây (0.75s - 1.45s * speed_mult).
        """
        if not tree_coords or not hwnd:
            return

        miss_prob = scenario.get("effective_miss_click_prob", scenario.get("miss_click_prob", 0.05)) if scenario else 0.05
        speed_mult = scenario.get("speed_mult", scenario.get("effective_speed_multiplier", 1.0)) if scenario else 1.0
        jitter_px = scenario.get("jitter_px", 4) if scenario else 4

        print(f"[FarmMaintenance] Bắt đầu đốn hạ {len(tree_coords)} cây trên đảo (Chuẩn tối thiểu {hits_per_tree} nhát/cây, Tốc độ: {speed_mult:.2f}x)...")

        for idx, (rel_x, rel_y) in enumerate(tree_coords, 1):
            screen_x, screen_y = WindowHelper.to_screen_coords(hwnd, rel_x, rel_y)

            # Số nhát click thực tế cho cây này (đôi khi 4 hoặc 5 do quán tính ngón tay)
            target_hits = FarmMaintenance._calculate_strikes_for_tree(scenario, base_hits=hits_per_tree)
            is_overclick = (target_hits > hits_per_tree)
            overclick_note = f" (Người chơi nhấp thêm {target_hits - hits_per_tree} nhát theo quán tính)" if is_overclick else ""
            print(f" -> Đang chặt cây thứ {idx}/{len(tree_coords)} tại ({screen_x}, {screen_y}) | Kế hoạch: {target_hits} nhát{overclick_note}...")

            successful_hits = 0
            max_attempts = target_hits + 5
            attempts = 0

            while successful_hits < target_hits and attempts < max_attempts:
                attempts += 1
                if random.random() < miss_prob:
                    HumanMouse.fumble_click(screen_x, screen_y, miss_offset=10)
                    HumanMouse.human_sleep(0.28 * speed_mult, 0.48 * speed_mult)
                    # Click trượt rìa ngoài -> không tính nhát chém trúng đích
                    continue

                successful_hits += 1
                strike_label = f"#{successful_hits}/{target_hits}"
                if successful_hits > hits_per_tree:
                    strike_label += " [Quán tính tay]"

                HumanMouse.click(screen_x, screen_y, random_offset=min(jitter_px, 4))
                print(f"    * Nhát đốn gỗ {strike_label} trúng đích...")

                if successful_hits < target_hits:
                    delay = FarmMaintenance._get_inter_strike_delay(successful_hits, target_hits, speed_mult)
                    time.sleep(delay)

            # Nghỉ nhịp thở giữa 2 cây liên tiếp
            inter_tree_rest = random.uniform(0.75, 1.45) * speed_mult
            time.sleep(inter_tree_rest)

        print(f"[FarmMaintenance] Đã đốn hạ xong {len(tree_coords)} cây theo kế hoạch phiên!")

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

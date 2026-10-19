"""
HỆ THỐNG 4B: ĐIỀU PHỐI HÀNG ĐỢI & LỊCH TRÌNH SINH HỌC (QUEUE & CIRCADIAN MANAGER)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Mô phỏng lịch trình người thật (Ngủ đêm, Giải lao, Trễ ngẫu nhiên)
"""

import datetime
import os
import random
import sys
import time
from typing import List, Dict, Optional

# Đảm bảo đường dẫn import tương thích khi chạy độc lập
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scheduler.farm_memory import FarmMemory


class QueueManager:
    """
    Bộ điều phối lịch trình sinh học:
    - Quản lý giờ ngủ đêm (Sleep Window): Không bao giờ cày đêm liên tục.
    - Quản lý khoảng nghỉ giải lao (Coffee breaks): Cứ sau 4-6 acc thì nghỉ vài phút.
    - Chọn profile tiếp theo từ danh sách đã sẵn sàng.
    """

    def __init__(
        self,
        farm_memory: FarmMemory,
        sleep_start_hour: float = 0.5,    # 00:30 đêm bắt đầu ngủ
        sleep_end_hour: float = 6.5,      # 06:30 sáng thức dậy
        inter_profile_delay: tuple = (25, 50),
        break_every_n_profiles: int = 5
    ):
        self.memory = farm_memory
        self.sleep_start_hour = sleep_start_hour
        self.sleep_end_hour = sleep_end_hour
        self.inter_profile_delay = inter_profile_delay
        self.break_every_n = break_every_n_profiles
        self.processed_count = 0
        # Độ lệch giờ ngủ/thức mỗi ngày (Jitter: -30p đến +45p)
        self.today_sleep_offset = random.uniform(-0.5, 0.75)
        self.today_wake_offset = random.uniform(-0.4, 0.6)

    def is_sleep_time(self) -> bool:
        """Kiểm tra khung giờ ngủ đêm sinh học có tính đến độ lệch ngày (Sleep Jitter)."""
        now = datetime.datetime.now()
        cur_hour = now.hour + now.minute / 60.0
        effective_sleep = (self.sleep_start_hour + self.today_sleep_offset) % 24
        effective_wake = (self.sleep_end_hour + self.today_wake_offset) % 24

        if effective_sleep > effective_wake:
            return cur_hour >= effective_sleep or cur_hour < effective_wake
        else:
            return effective_sleep <= cur_hour < effective_wake

    def is_meal_time(self) -> bool:
        """
        Kiểm tra khung giờ ăn trưa (11:45 - 12:45) và ăn tối (18:30 - 19:30).
        Người thật trong khung giờ này sinh hoạt cá nhân, tần suất chơi giảm mạnh.
        """
        now = datetime.datetime.now()
        cur_hour = now.hour + now.minute / 60.0
        # Ăn trưa: 11.75 -> 12.75
        if 11.75 <= cur_hour <= 12.75:
            return True
        # Ăn tối: 18.5 -> 19.5
        if 18.5 <= cur_hour <= 19.5:
            return True
        return False

    def wait_inter_profile_delay(self):
        """Khoảng nghỉ ngẫu nhiên giữa 2 profile (Cool-down: 25 - 50 giây)."""
        self.processed_count += 1

        # Cứ sau mỗi N profile thì nghỉ giải lao dài (Coffee Break)
        if self.processed_count % self.break_every_n == 0:
            long_break = random.uniform(180, 420)  # 3 - 7 phút
            print(f"[QueueManager] Da chay lien tuc {self.break_every_n} profile. Dang nghi giai lao (Coffee Break): {int(long_break)} giay...")
            time.sleep(long_break)
        else:
            short_delay = random.uniform(self.inter_profile_delay[0], self.inter_profile_delay[1])
            print(f"[QueueManager] Nghi ngau nhien giua 2 profile: {short_delay:.1f} giay...")
            time.sleep(short_delay)

    def select_next_profile(self, all_profiles: List[Dict]) -> Optional[Dict]:
        """
        Lọc danh sách các profile và chọn ra profile đã đến giờ thu hoạch:
        - Phải thỏa mãn cả 3 điều kiện: Chưa cap phiên + Đã chín/trễ quên + Đang trong Khung giờ sinh hoạt hợp lệ!
        """
        ready_profiles = []
        for p in all_profiles:
            pid = p.get("id")
            pname = p.get("name", "")
            if pid and self.memory.is_ready_for_session(pid, pname):
                ready_profiles.append(p)

        if ready_profiles:
            # Xáo trộn ngẫu nhiên thứ tự (không chạy rập khuôn 1->2->3)
            return random.choice(ready_profiles)

        return None

    def get_min_wait_time(self, all_profiles: List[Dict]) -> float:
        """Tính thời gian phải chờ ngắn nhất nếu tất cả profile đều chưa đến giờ."""
        wait_times = []
        for p in all_profiles:
            pid = p.get("id")
            pname = p.get("name", "")
            if pid:
                wait_times.append(self.memory.get_time_until_next_ready(pid, pname))
        return min(wait_times) if wait_times else 60.0

    def print_status_summary(self, all_profiles: List[Dict]):
        """In bảng tóm tắt trạng thái sinh học của toàn bộ các con người sống động để người dùng nắm rõ."""
        print("\n" + "=" * 80)
        print(" [BÁO CÁO ĐỜI SỐNG & TRẠNG THÁI SINH HOẠT CỦA CÁC PROFILE]")
        for p in all_profiles[:8]:  # Hiển thị tối đa 8 profile đại diện
            pid = p.get("id")
            pname = p.get("name", pid)
            persona = self.memory.persona_mgr.get_or_create_persona(pid, pname)
            ident = persona.get("human_identity", {})
            sc = self.memory.scenario_engine.get_or_generate_scenario(pid, pname, ident)
            in_slot, reason, wait_sec = self.memory.scenario_engine.is_in_active_time_slot(pid, pname)
            count = self.memory.data.get(pid, {}).get("session_count_today", 0)
            cap = sc.get("daily_session_cap", 0)

            status_tag = "[SẴN SÀNG]" if in_slot else "[ĐANG BẬN]"
            human_label = f"{sc['real_name']} ({sc['age']}t - {sc['job'][:12]})"
            print(f" * {human_label:28} | Phiên: {count}/{cap:2} | Tâm trạng: {sc['today_mood'][:15]:15} | {status_tag} {reason}")
        if len(all_profiles) > 8:
            print(f" ... và {len(all_profiles) - 8} người chơi khác đang trong nhịp sinh học.")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 4B: Queue & Circadian Manager ---")
    mem = FarmMemory("test_memory2.json")
    qm = QueueManager(mem)
    print(f"Hien tai co phai gio ngu khong? {qm.is_sleep_time()}")
    test_profiles = [{"id": "p1", "name": "Acc 1"}, {"id": "p2", "name": "Acc 2"}]
    selected = qm.select_next_profile(test_profiles)
    print(f"Profile duoc chon chay tiep theo: {selected.get('name') if selected else 'None'}")

import contextlib
import datetime
import json
import os
import random
import sys
import time
from typing import Dict, Optional, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scheduler.persona_manager import PersonaManager
from scheduler.scenario_engine import ScenarioEngine


class FarmMemory:
    """
    Quản lý bộ nhớ trạng thái của từng Profile:
    - Gắn với PersonaManager để lấy ADN sinh học cố định (tốc độ, jitter).
    - Gắn với ScenarioEngine để lấy Bối cảnh Đời sống hôm nay (Session Cap 0 - 22, trễ quên, AFK).
    - Tự động reset bộ đếm phiên khi sang ngày mới.
    - Hỗ trợ khóa file tiến trình (Inter-Process File Locking) chống hỏng dữ liệu khi chạy song song.
    """

    def __init__(
        self,
        memory_file: str = "farm_memory.json",
        personas_file: str = "personas.json",
        scenarios_file: str = "daily_scenarios.json",
        ai_client=None
    ):
        self.memory_file = memory_file
        self.persona_mgr = PersonaManager(personas_file)
        self.scenario_engine = ScenarioEngine(scenarios_file, ai_client=ai_client)
        self.data = self._load()

    @contextlib.contextmanager
    def _process_lock(self, timeout: float = 4.0):
        """Khóa tiến trình chéo (Inter-process File Lock) dùng cờ O_CREAT | O_EXCL của hệ điều hành."""
        lock_file = f"{self.memory_file}.lock"
        start = time.time()
        fd = None
        while time.time() - start < timeout:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
            except FileExistsError:
                # Nếu lock file quá cũ (> 10s), có thể tiến trình trước bị crash -> tự thu hồi
                try:
                    if os.path.exists(lock_file) and (time.time() - os.path.getmtime(lock_file) > 10.0):
                        os.remove(lock_file)
                except Exception:
                    pass
                time.sleep(0.04)
        if fd is None:
            raise TimeoutError(f"[FarmMemory Lock] Không thể chiếm quyền ghi file {lock_file} sau {timeout}s (Bị khóa bởi tiến trình khác)!")

        try:
            yield
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass
                try:
                    if os.path.exists(lock_file):
                        os.remove(lock_file)
                except Exception:
                    pass

    def _load(self) -> Dict:
        """Đọc file bộ nhớ với cơ chế phòng thủ: nếu file chính hỏng, nạp từ file backup."""
        for path in [self.memory_file, f"{self.memory_file}.bak"]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[FarmMemory Warning] Lỗi đọc {path}: {e}")
        return {}

    def _save(self):
        """Ghi file an toàn nguyên tử (Atomic Write) kết hợp Process Lock tránh xung đột đa tiến trình."""
        tmp_file = f"{self.memory_file}.tmp"
        bak_file = f"{self.memory_file}.bak"
        with self._process_lock():
            try:
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                if os.path.exists(self.memory_file):
                    try:
                        if os.path.exists(bak_file):
                            os.remove(bak_file)
                        os.replace(self.memory_file, bak_file)
                    except Exception:
                        pass

                os.replace(tmp_file, self.memory_file)
            except Exception as e:
                print(f"[FarmMemory Error] Không thể lưu data an toàn: {e}")
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                    except Exception:
                        pass

    def _check_and_reset_daily(self, profile_id: str):
        """Reset số phiên nếu đã bước sang ngày mới (sau 00:00)."""
        today_str = datetime.date.today().isoformat()
        prof_data = self.data.setdefault(profile_id, {})
        last_date = prof_data.get("last_date")
        if last_date != today_str:
            prof_data["last_date"] = today_str
            prof_data["session_count_today"] = 0

    def record_planting(self, profile_id: str, crop_name: str, grow_seconds: int, profile_name: str = ""):
        """
        Ghi nhận vừa gieo một loại cây mới:
        - Tính thời điểm chín = Hiện tại + grow_seconds
        - Next run time = Thời điểm chín + (Độ trễ quên từ Persona * Hệ số bối cảnh ngày từ Scenario)
        """
        now = time.time()
        ready_time = now + grow_seconds
        self._check_and_reset_daily(profile_id)

        # Lấy ADN và danh tính con người của profile
        persona = self.persona_mgr.get_or_create_persona(profile_id, profile_name)
        scenario = self.scenario_engine.get_or_generate_scenario(profile_id, profile_name, persona.get("human_identity"))
        forgetting_scale = scenario.get("forgetting_scale", 1.0)

        # Tính độ trễ quên tự nhiên từ Persona nhân với hệ số bối cảnh
        base_forgetting = self.persona_mgr.calculate_forgetting_delay(profile_id, grow_seconds)
        forgetting_delay = base_forgetting * forgetting_scale
        next_run = ready_time + forgetting_delay

        prof_data = self.data[profile_id]
        prof_data["crop_name"] = crop_name
        prof_data["planted_at"] = now
        prof_data["ready_at"] = ready_time
        prof_data["next_run_at"] = next_run
        prof_data["last_session_at"] = now
        prof_data["session_count_today"] = prof_data.get("session_count_today", 0) + 1

        self._save()
        cap = scenario.get("daily_session_cap", 6)
        count = prof_data["session_count_today"]
        print(f"[FarmMemory] {scenario['real_name']} ({scenario['job']}): Vừa gieo '{crop_name}' (Chín lúc {time.strftime('%H:%M:%S', time.localtime(ready_time))})")
        print(f" -> Tâm trạng: [{scenario['today_mood']}] | Trễ quên: +{forgetting_delay/60:.1f} phút -> Mở lại lúc: {time.strftime('%H:%M:%S', time.localtime(next_run))}")
        print(f" -> Tiến độ hôm nay: {count}/{cap} phiên")

    def is_session_capped_today(self, profile_id: str, profile_name: str = "") -> bool:
        """Kiểm tra profile này đã đạt giới hạn phiên theo kịch bản hôm nay chưa."""
        self._check_and_reset_daily(profile_id)
        persona = self.persona_mgr.get_or_create_persona(profile_id, profile_name)
        scenario = self.scenario_engine.get_or_generate_scenario(profile_id, profile_name, persona.get("human_identity"))
        cap = scenario.get("daily_session_cap", 6)
        count = self.data.get(profile_id, {}).get("session_count_today", 0)
        return count >= cap

    def is_ready_for_session(self, profile_id: str, profile_name: str = "") -> bool:
        """
        Profile chỉ sẵn sàng mở khi thỏa mãn CẢ 3 ĐIỀU KIỆN SINH HỌC:
        1. Chưa chạm giới hạn phiên hôm nay (Session Cap).
        2. Đã đến hoặc vượt qua next_run_at (Cây chín + Trễ quên tự nhiên).
        3. Đang nằm trong Khung giờ sinh hoạt hợp lệ (Active Time-Slot) của kịch bản hôm nay!
        """
        if self.is_session_capped_today(profile_id, profile_name):
            return False

        if profile_id in self.data:
            next_run = self.data[profile_id].get("next_run_at", 0)
            if time.time() < next_run:
                return False

        # Kiểm tra cụm giờ sinh hoạt (Time-Slot Clustering)
        persona = self.persona_mgr.get_or_create_persona(profile_id, profile_name)
        in_slot, reason, wait_sec = self.scenario_engine.is_in_active_time_slot(profile_id, profile_name)
        if not in_slot:
            return False

        return True

    def is_crop_ready_for_harvest(self, profile_id: str) -> bool:
        """Kiểm tra cây của profile này đã đến hoặc qua thời điểm chín chưa."""
        if profile_id not in self.data:
            return True  # Lần đầu chạy, giả định cần thu hoạch dọn ruộng cũ
        ready_at = self.data[profile_id].get("ready_at", 0)
        return time.time() >= ready_at

    def get_time_until_next_ready(self, profile_id: str, profile_name: str = "") -> float:
        """
        Số giây còn lại cho đến khi profile này sẵn sàng:
        Lấy Max giữa (Thời gian chờ cây chín + trễ quên) và (Thời gian chờ đến cụm giờ sinh hoạt tiếp theo).
        """
        crop_wait = 0.0
        if profile_id in self.data:
            diff = self.data[profile_id].get("next_run_at", 0) - time.time()
            crop_wait = max(0.0, diff)

        in_slot, reason, slot_wait = self.scenario_engine.is_in_active_time_slot(profile_id, profile_name)
        return max(crop_wait, slot_wait)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 4A: Farm State Memory ---")
    mem = FarmMemory("test_memory.json")
    mem.record_planting("test-profile-1", "Sunflower", 60)
    print(f"San sang mo ngay? {mem.is_ready_for_session('test-profile-1')}")
    if os.path.exists("test_memory.json"):
        os.remove("test_memory.json")
    print("Test thanh cong!")

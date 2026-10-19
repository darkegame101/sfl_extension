"""
HỆ THỐNG 4D: CÔNG CỤ KỊCH BẢN ĐỜI SỐNG SỐNG ĐỘNG (LIVING LIFE SCENARIO & NARRATIVE ENGINE)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Biến mỗi Profile thành một CON NGƯỜI SỐNG ĐỘNG CÓ HỈ NỘ ÁI Ố VÀ NHẬT KÝ ĐỜI THỰC HÀNG NGÀY
"""

import contextlib
import datetime
import json
import os
import random
import sys
import time
from typing import Dict, Any, Optional, List

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

try:
    from core.ai_vision import AIVision
except ImportError:
    AIVision = None


class ScenarioEngine:
    """
    Công cụ Kịch bản Đời sống Sống động:
    - Không chỉ là mã code: Mỗi profile là một con người với câu chuyện đời thực phong phú.
    - Mỗi ngày sinh một Cuốn Nhật Ký Ngày (Daily Life Narrative) kết hợp danh tính & nghề nghiệp.
    - Tâm trạng hôm nay (Mood) tác động trực tiếp lên:
      + Tốc độ chuột & Độ rung tay (Rushed = nhanh ẩu, Tired = chậm chạp).
      + Xác suất click trượt (Fumble click).
      + Các sự cố xao nhãng đời thực (AFK Distraction Events: shipper gọi, con khóc, sếp dí, lướt tin nhắn...).
    """

    DAILY_LIFE_SITUATIONS = [
        {
            "category": "WFH_RAINY_DAY",
            "name": "Làm việc tại nhà vì trời mưa ngập (WFH Grinder)",
            "archetype": "Marathon Grind",
            "weight": 8,
            "min_sessions": 14,
            "max_sessions": 22,
            "forgetting_scale": 0.45,
            "mood": "Thư thái & Hào hứng",
            "speed_mult": 1.05,
            "fumble_rate": 0.04,
            "distract_rate": 0.09,
            "story_template": "Trời mưa to ngập đường nên được sếp cho làm việc tại nhà (WFH). Ngồi cả ngày bên máy tính, vừa làm việc vừa mở tab game canh thu hoạch liên tục từ sáng tới khuya.",
            "base_slots": [
                {"name": "Vừa mở máy làm việc", "start": 7.5, "end": 11.5, "reason": "Sáng WFH thong thả"},
                {"name": "Chiều làm việc tại nhà", "start": 13.0, "end": 17.5, "reason": "Tranh thủ lúc code xong tính năng"},
                {"name": "Tối cày sự kiện game", "start": 19.0, "end": 23.8, "reason": "Tối rảnh rỗi ôm máy cày bù"}
            ]
        },
        {
            "category": "OFFICE_STANDARD",
            "name": "Ngày đi làm công sở tiêu chuẩn (Office Routine)",
            "archetype": "Standard Workday",
            "weight": 45,
            "min_sessions": 4,
            "max_sessions": 7,
            "forgetting_scale": 1.0,
            "mood": "Điềm đạm & Giữ nhịp",
            "speed_mult": 1.0,
            "fumble_rate": 0.05,
            "distract_rate": 0.12,
            "story_template": "Ngày làm việc 8 tiếng bình thường tại văn phòng. Sáng tranh thủ ăn sáng mở 1 lượt, trưa ăn cơm xong nghỉ ngơi mở 1 lượt, tối về nhà sau khi ăn cơm tắm rửa mới ngồi chơi thong thả.",
            "base_slots": [
                {"name": "Sáng ăn sáng trước khi đi làm", "start": 6.75, "end": 8.0, "reason": "Vừa ăn sáng uống cà phê vừa ngó farm"},
                {"name": "Nghỉ trưa tại văn phòng", "start": 11.75, "end": 13.25, "reason": "Ăn cơm trưa xong có 45 phút nghỉ ngơi"},
                {"name": "Tan tầm vừa về tới nhà", "start": 17.5, "end": 18.75, "reason": "Đi làm về nghỉ chân uống nước"},
                {"name": "Buổi tối thư giãn Prime Time", "start": 20.0, "end": 23.0, "reason": "Tối rảnh rỗi lướt web chơi game"}
            ]
        },
        {
            "category": "DEADLINE_OVERTIME",
            "name": "Chạy Deadline tăng ca sấp mặt (Overtime Rush)",
            "archetype": "Busy & Overtime",
            "weight": 25,
            "min_sessions": 2,
            "max_sessions": 3,
            "forgetting_scale": 2.2,
            "mood": "Căng thẳng & Vội vã",
            "speed_mult": 0.88,  # di chuyển nhanh vội
            "fumble_rate": 0.09,  # dễ bấm nhầm
            "distract_rate": 0.20,
            "story_template": "Công ty vào đợt thanh tra / chạy nước rút dự án. Cả ngày họp hành liên miên, đầu óc căng như dây đàn. Chỉ vào chớp nhoáng sáng sớm và tận khuya tăng ca về mới mở máy.",
            "base_slots": [
                {"name": "Sáng sớm vội vã", "start": 6.25, "end": 7.25, "reason": "Vội vã trước khi lao xe ra đường"},
                {"name": "Nửa đêm tăng ca về", "start": 22.0, "end": 23.75, "reason": "Tăng ca về phòng trọ mệt mỏi"}
            ]
        },
        {
            "category": "FAMILY_TRIP_DETOX",
            "name": "Đi du lịch / Đi ăn cưới ngoại tỉnh (Digital Detox)",
            "archetype": "Digital Detox",
            "weight": 10,
            "min_sessions": 0,
            "max_sessions": 1,
            "forgetting_scale": 4.0,
            "mood": "Mất tập trung / Vui chơi bên ngoài",
            "speed_mult": 1.1,
            "fumble_rate": 0.08,
            "distract_rate": 0.30,
            "story_template": "Cuối tuần đi du lịch cùng gia đình hoặc về quê ăn cưới họ hàng. Cả ngày bận lái xe và giao lưu gặp gỡ, hoàn toàn quên bẵng game, chỉ tối muộn về khách sạn mới nhớ ra kiểm tra qua loa.",
            "base_slots": [
                {"name": "Sực nhớ ra lúc nửa đêm", "start": 21.75, "end": 22.75, "reason": "Về phòng khách sạn nằm nghỉ mới sực nhớ"}
            ]
        },
        {
            "category": "LAZY_RAINY_AFTERNOON",
            "name": "Ngày mất hứng lười biếng (Lazy Sunday)",
            "archetype": "Lazy Slacker",
            "weight": 7,
            "min_sessions": 1,
            "max_sessions": 2,
            "forgetting_scale": 2.5,
            "mood": "Uể oải & Chán chường",
            "speed_mult": 1.25,  # di chuyển lề mề
            "fumble_rate": 0.06,
            "distract_rate": 0.22,
            "story_template": "Hôm nay tâm trạng hơi chán nản, ngủ nướng tới trưa. Vào game ngắm nghía luống đất một lát, gieo mấy cây dài hạn rồi đóng máy đi ngủ tiếp.",
            "base_slots": [
                {"name": "Ghé qua lúc đầu giờ chiều", "start": 13.5, "end": 15.0, "reason": "Ngủ trưa dậy lướt web uể oải"}
            ]
        },
        {
            "category": "WEEKEND_CAFE",
            "name": "Cà phê cuối tuần cùng bạn bè (Weekend Chill)",
            "archetype": "Standard Workday",
            "weight": 5,
            "min_sessions": 6,
            "max_sessions": 9,
            "forgetting_scale": 0.8,
            "mood": "Phấn khởi & Hài hước",
            "speed_mult": 0.98,
            "fumble_rate": 0.05,
            "distract_rate": 0.16,
            "story_template": "Sáng chủ nhật xách laptop ra quán cà phê với hội bạn. Vừa tán gẫu vừa chơi game, thỉnh thoảng đang bấm dở thì mải chém gió cười đùa nên dừng tay.",
            "base_slots": [
                {"name": "Cà phê sáng cùng bạn bè", "start": 8.5, "end": 11.75, "reason": "Ngồi quán cà phê mát mẻ"},
                {"name": "Buổi chiều tại nhà", "start": 14.5, "end": 17.5, "reason": "Đi chơi về nghỉ ngơi"},
                {"name": "Tối cuối tuần", "start": 20.0, "end": 23.5, "reason": "Thư giãn trước khi sang tuần mới"}
            ]
        }
    ]

    REAL_LIFE_AFK_REASONS = [
        "Shipper gọi điện xuống lấy đồ Shopee đặt hôm trước",
        "Có chuông cửa người giao nước ngọt / giao bình gas",
        "Có tin nhắn Zalo/Telegram công việc từ đồng nghiệp cần trả lời gấp",
        "Mẹ ở quê gọi điện thoại hỏi thăm sức khỏe cuối tuần",
        "Đi đứng dậy rót cốc nước ấm và với lấy đồ ăn vặt",
        "Vô tình trượt tay lướt xem thông báo Facebook/TikTok trên điện thoại",
        "Chó mèo cưng chạy vào phòng cào chân đòi vuốt ve",
        "Mải nghe đoạn cao trào trong bài hát đang phát trên tai nghe"
    ]

    def __init__(self, storage_file: str = "daily_scenarios.json", ai_client: Optional[Any] = None):
        self.storage_file = storage_file
        self.ai = ai_client
        self.scenarios = self._load()
        try:
            from core.markov_trainer import MarkovScenarioModel
            self.markov_model = MarkovScenarioModel()
        except Exception as e:
            print(f"[ScenarioEngine Warning] Không thể khởi tạo MarkovScenarioModel: {e}")
            self.markov_model = None

    def _load(self) -> Dict[str, Any]:
        """Đọc scenarios đã lưu với cơ chế dự phòng file backup."""
        for path in [self.storage_file, f"{self.storage_file}.bak"]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[ScenarioEngine Warning] Lỗi đọc {path}: {e}")
        return {}

    @contextlib.contextmanager
    def _process_lock(self, timeout: float = 4.0):
        """Khóa tiến trình chéo (Inter-process File Lock) dùng cờ O_CREAT | O_EXCL của hệ điều hành."""
        lock_file = f"{self.storage_file}.lock"
        start = time.time()
        fd = None
        while time.time() - start < timeout:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
            except FileExistsError:
                try:
                    if os.path.exists(lock_file) and (time.time() - os.path.getmtime(lock_file) > 10.0):
                        os.remove(lock_file)
                except Exception:
                    pass
        if fd is None:
            raise TimeoutError(f"[ScenarioEngine Lock] Không thể chiếm quyền ghi file {lock_file} sau {timeout}s (Bị khóa bởi tiến trình khác)!")

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

    def _save(self):
        """Ghi file an toàn nguyên tử (Atomic Write) kết hợp Process Lock tránh xung đột đa tiến trình."""
        tmp_file = f"{self.storage_file}.tmp"
        bak_file = f"{self.storage_file}.bak"
        with self._process_lock():
            try:
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(self.scenarios, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                if os.path.exists(self.storage_file):
                    try:
                        if os.path.exists(bak_file):
                            os.remove(bak_file)
                        os.replace(self.storage_file, bak_file)
                    except Exception:
                        pass

                os.replace(tmp_file, self.storage_file)
            except Exception as e:
                print(f"[ScenarioEngine Error] Không thể lưu scenarios an toàn: {e}")
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                    except Exception:
                        pass

    def get_today_str(self) -> str:
        return datetime.date.today().isoformat()

    @staticmethod
    def format_hour(hour_float: float) -> str:
        hour_float = hour_float % 24
        h = int(hour_float)
        m = int(round((hour_float - h) * 60))
        if m >= 60:
            h = (h + 1) % 24
            m = 0
        return f"{h:02d}:{m:02d}"

    def get_or_generate_scenario(self, profile_id: str, profile_name: str = "", persona_identity: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Lấy hoặc sinh Kịch bản Đời sống Sống động hôm nay cho Profile:
        Kết hợp chặt chẽ Danh tính người thật (Tuổi, Nghề, Tính cách) với Tình huống đời sống hàng ngày.
        """
        today = self.get_today_str()
        prof_record = self.scenarios.setdefault(profile_id, {})

        if prof_record.get("date") == today and "scenario" in prof_record:
            return prof_record["scenario"]

        # Sinh kịch bản bối cảnh sống động hôm nay
        scenario = self._generate_living_scenario(profile_id, profile_name, persona_identity)

        prof_record["date"] = today
        prof_record["profile_name"] = profile_name
        prof_record["scenario"] = scenario
        self._save()

        # In nhật ký đời sống tuyệt đẹp ra màn hình
        self._print_living_diary_entry(scenario, profile_name or profile_id)

        return scenario

    def _calculate_dynamic_archetype_weights(self, profile_id: str, identity: Optional[Dict]) -> List[float]:
        """
        Suy luận bối cảnh động (Dynamic Context Inference Engine):
        1. Theo ngày trong tuần thực tế (Weekday vs Weekend).
        2. Theo tính chất nghề nghiệp & thói quen sinh hoạt (Persona Job Alignment).
        3. Theo chuỗi chuyển trạng thái Markov & mệt mỏi tích lũy từ hôm trước (Historical Fatigue & Carryover).
        """
        now = datetime.date.today()
        weekday = now.weekday()  # 0: Mon, 1: Tue, ..., 4: Fri, 5: Sat, 6: Sun
        is_weekend = (weekday >= 5)

        # Lấy bối cảnh gần nhất của profile này trong lịch sử để tính chuyển trạng thái Markov
        yesterday_record = self.scenarios.get(profile_id, {})
        yesterday_scenario = yesterday_record.get("scenario", {})
        yesterday_cat = yesterday_scenario.get("category", "")

        job = (identity.get("occupation", "") if identity else "").lower()

        dynamic_weights = []
        for sit in self.DAILY_LIFE_SITUATIONS:
            cat = sit["category"]
            base_w = float(sit["weight"])

            # 1. Điều chỉnh theo ngày trong tuần (Real Calendar Alignment)
            if is_weekend:
                if cat == "WEEKEND_CAFE":
                    base_w *= 7.0  # Cuối tuần đi cafe sáng với bạn bè
                elif cat == "FAMILY_TRIP_DETOX":
                    base_w *= 3.5  # Cuối tuần đi du lịch / ăn cưới họ hàng
                elif cat == "LAZY_RAINY_AFTERNOON":
                    base_w *= 3.0  # Cuối tuần ngủ nướng thong thả
                elif cat == "OFFICE_STANDARD":
                    base_w *= 0.1  # Cuối tuần rất hiếm khi làm giờ công sở
                elif cat == "DEADLINE_OVERTIME":
                    base_w *= 0.3  # Trừ khi bị ép OT cuối tuần
            else:
                # Ngày trong tuần (Thứ 2 - Thứ 6)
                if cat == "OFFICE_STANDARD":
                    base_w *= 1.8
                elif cat == "DEADLINE_OVERTIME":
                    base_w *= 1.4
                elif cat == "WEEKEND_CAFE":
                    base_w *= 0.05  # Trong tuần không ai đi cafe sáng lê la
                elif cat == "FAMILY_TRIP_DETOX":
                    base_w *= 0.1

            # 2. Điều chỉnh theo Nghề nghiệp (Persona Job Alignment)
            if any(k in job for k in ["lập trình", "phần mềm", "developer", "cntt", "freelance"]):
                if cat == "WFH_RAINY_DAY":
                    base_w *= 2.8
                elif cat == "DEADLINE_OVERTIME":
                    base_w *= 1.5
            elif any(k in job for k in ["kế toán", "ngân hàng", "giao dịch", "hành chính", "công sở"]):
                if cat == "OFFICE_STANDARD":
                    base_w *= 2.0
                elif cat == "WFH_RAINY_DAY":
                    base_w *= 0.2  # Kế toán/ngân hàng ít khi được WFH
            elif any(k in job for k in ["sinh viên", "học sinh"]):
                if cat == "LAZY_RAINY_AFTERNOON":
                    base_w *= 2.2
                elif cat == "WEEKEND_CAFE":
                    base_w *= 1.8

            # 3. Chuyển trạng thái Markov chính tắc từ mô hình đã huấn luyện (Trained DTMC Transition Matrix)
            if self.markov_model and yesterday_cat:
                markov_probs = self.markov_model.get_transition_probabilities(yesterday_cat)
                if cat in markov_probs:
                    markov_factor = markov_probs[cat] * len(self.DAILY_LIFE_SITUATIONS)
                    base_w *= max(0.2, markov_factor)
            else:
                # Fallback nếu chưa tải được mô hình
                if yesterday_cat == "DEADLINE_OVERTIME":
                    if cat == "LAZY_RAINY_AFTERNOON":
                        base_w *= 2.5
                    elif cat == "DEADLINE_OVERTIME":
                        base_w *= 0.4
                elif yesterday_cat == "FAMILY_TRIP_DETOX":
                    if cat == "OFFICE_STANDARD":
                        base_w *= 1.5

            dynamic_weights.append(max(0.1, base_w))

        return dynamic_weights

    def _generate_living_scenario(self, profile_id: str, profile_name: str, identity: Optional[Dict]) -> Dict[str, Any]:
        """Tạo sinh cuốn nhật ký sống động dựa trên suy luận bối cảnh thực tế."""
        dynamic_weights = self._calculate_dynamic_archetype_weights(profile_id, identity)
        sit = random.choices(self.DAILY_LIFE_SITUATIONS, weights=dynamic_weights, k=1)[0]

        session_cap = random.randint(sit["min_sessions"], sit["max_sessions"])

        # Jitter cá nhân hóa cho từng cụm giờ
        today_slots = []
        for slot in sit["base_slots"]:
            jitter = random.uniform(-0.35, 0.35)
            s_start = max(5.5, min(23.5, slot["start"] + jitter))
            s_end = max(s_start + 0.5, min(23.95, slot["end"] + jitter + random.uniform(0.0, 0.25)))
            today_slots.append({
                "name": slot["name"],
                "start": round(s_start, 2),
                "end": round(s_end, 2),
                "reason": slot.get("reason", "Khung giờ rảnh rỗi")
            })

        # Xây dựng câu chuyện đời thực
        real_name = identity.get("real_name", profile_name or "Người chơi") if identity else (profile_name or "Người chơi")
        job = identity.get("occupation", "Nhân viên văn phòng") if identity else "Nhân viên văn phòng"
        age = identity.get("age", 25) if identity else 25

        narrative = f"{real_name} ({age} tuổi, {job}): {sit['story_template']}"

        # Nếu có AI Vision / LLM API Key, yêu cầu Claude Haiku viết 1 câu chuyện đời thực cực kỳ sống động
        if self.ai and getattr(self.ai, "api_key", None) and hasattr(self.ai, "generate_narrative"):
            try:
                ai_prompt = (
                    f"Bạn là đạo diễn mô phỏng đời sống con người thật. Hãy viết 2 câu nhật ký ngắn gọn, rất đời thường và tự nhiên "
                    f"cho nhân vật: '{real_name}' ({age} tuổi, làm nghề '{job}') trong ngày hôm nay. "
                    f"Bối cảnh ngày hôm nay: '{sit['name']}'. Tâm trạng: '{sit['mood']}'. "
                    f"Kể về việc hôm nay họ làm gì, tại sao rảnh hoặc bận, và lúc nào họ vào ngó nông trại Sunflower Land."
                )
                ai_text = self.ai.generate_narrative(ai_prompt)
                if ai_text:
                    narrative = f"{real_name} ({age}t, {job}) - {ai_text}"
            except Exception as e:
                print(f"[ScenarioEngine Warning] Không thể tạo narrative qua LLM: {e}")

        # Chọn sự cố xao nhãng đời thực hôm nay
        daily_distractions = random.sample(self.REAL_LIFE_AFK_REASONS, k=2)

        scenario = {
            "archetype_name": sit["name"],
            "category": sit["category"],
            "real_name": real_name,
            "job": job,
            "age": age,
            "today_mood": sit["mood"],
            "daily_narrative": narrative,
            "daily_session_cap": session_cap,
            "today_slots": today_slots,
            "forgetting_scale": sit["forgetting_scale"],
            "speed_multiplier": sit["speed_mult"],
            "fumble_rate": sit["fumble_rate"],
            "miss_click_prob": sit["fumble_rate"],  # Alias tương thích hoàn toàn với CropManager
            "distraction_prob": sit["distract_rate"],
            "distract_rate": sit["distract_rate"],  # Alias tương thích
            "daily_distractions": daily_distractions,
            "created_at": time.time(),
            # Kiến trúc Tác nhân Mô phỏng (Park et al. 2023 Generative Agents & DeepMind Concordia 2024):
            "episodic_stream": [],
            "intra_day_state": {
                "sessions_completed": 0,
                "accumulated_fatigue": 0.0,
                "vigilance_level": 1.0,
                "last_event_time": time.time(),
                "current_mood": sit["mood"]
            }
        }
        return scenario

    def _print_living_diary_entry(self, scenario: Dict[str, Any], display_name: str):
        """In cuốn nhật ký đời sống sống động của profile ra Console."""
        print("\n" + "=" * 75)
        print(f" 📖 NHẬT KÝ ĐỜI SỐNG HÔM NAY: {scenario['real_name']} ({scenario['age']}t - {scenario['job']})")
        print(f" -> Danh xưng Profile: '{display_name}'")
        print(f" -> Tình huống hôm nay: {scenario['archetype_name']}")
        print(f" -> Tâm trạng: [{scenario['today_mood'].upper()}]")
        print(f" -> Nhật ký ngày: \"{scenario['daily_narrative']}\"")
        print(f" -> Mục tiêu chơi hôm nay: {scenario['daily_session_cap']} phiên")
        slot_strs = [f"{s['name']} ({self.format_hour(s['start'])}-{self.format_hour(s['end'])})" for s in scenario['today_slots']]
        print(f" -> Cụm giờ rảnh: {' | '.join(slot_strs)}")
        print(f" -> Sự cố có thể gặp: \"{scenario['daily_distractions'][0]}\"")
        print("=" * 75 + "\n")

    def is_in_active_time_slot(self, profile_id: str, profile_name: str = "") -> tuple:
        """Kiểm tra thời điểm hiện tại có đang nằm trong Khung giờ sinh hoạt hợp lệ hay không."""
        scenario = self.get_or_generate_scenario(profile_id, profile_name)
        slots = scenario.get("today_slots", [])

        if scenario.get("daily_session_cap", 0) <= 0 or not slots:
            return False, f"{scenario['real_name']} hôm nay đi chơi/nghỉ hoàn toàn (Digital Detox), không online.", 86400.0

        now = datetime.datetime.now()
        cur_hour = now.hour + now.minute / 60.0

        # Kiểm tra slot hiện tại
        for s in slots:
            if s["start"] <= cur_hour <= s["end"]:
                return True, f"{scenario['real_name']} đang trong khung giờ '{s['name']}' ({self.format_hour(s['start'])} - {self.format_hour(s['end'])}) - Lý do: {s.get('reason')}", 0.0

        # Đang ngoài khung giờ -> Tìm slot kế tiếp
        next_slot = None
        min_hour_diff = 999.0
        for s in slots:
            if s["start"] > cur_hour:
                diff = s["start"] - cur_hour
                if diff < min_hour_diff:
                    min_hour_diff = diff
                    next_slot = s

        if next_slot:
            wait_sec = min_hour_diff * 3600.0
            return False, f"{scenario['real_name']} đang bận công việc/sinh hoạt. Khung rảnh tiếp theo: '{next_slot['name']}' lúc {self.format_hour(next_slot['start'])}", wait_sec
        else:
            first_slot = slots[0]
            hours_until_midnight = 24.0 - cur_hour
            wait_sec = (hours_until_midnight + first_slot["start"]) * 3600.0
            return False, f"{scenario['real_name']} đã hết các khung giờ chơi hôm nay. Sẽ mở lại sáng mai lúc {self.format_hour(first_slot['start'])}", wait_sec

    def get_fatigue_multiplier(self) -> float:
        now = datetime.datetime.now()
        hour = now.hour + now.minute / 60.0
        if 7.0 <= hour < 11.5:
            return 1.0
        elif 12.5 <= hour < 15.0:
            return 1.15
        elif 18.0 <= hour < 22.0:
            return 1.05
        elif hour >= 22.0 or hour < 2.0:
            return 1.35
        else:
            return 1.10

    def register_event_feedback(self, profile_id: str, event_type: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Closed-loop Feedback & Episodic Stream (Grounded in Park et al. 2023 & DeepMind Concordia 2024):
        Ghi nhận sự kiện trong ngày và cập nhật trạng thái làm việc động (Intra-day Working Memory State).
        - 'CAPTCHA_ALERT': Kích hoạt cảnh giác cao (+0.35 vigilance), giảm tốc độ chuột để cẩn trọng.
        - 'CAPTCHA_RESOLVED': Xác nhận an toàn sau giải, duy trì sự thận trọng hợp lý.
        - 'AFK_DISTRACTION': Ghi nhận sự cố gián đoạn đời thực, tăng độ mệt mỏi nhẹ (+0.03).
        - 'SESSION_COMPLETED': Tăng số phiên hoàn thành, tích lũy mệt mỏi (+0.08).
        """
        record = self.scenarios.get(profile_id, {})
        scenario = record.get("scenario")
        if not scenario:
            scenario = self.get_or_generate_scenario(profile_id)
            record = self.scenarios.get(profile_id, {})

        stream = scenario.setdefault("episodic_stream", [])
        state = scenario.setdefault("intra_day_state", {
            "sessions_completed": 0,
            "accumulated_fatigue": 0.0,
            "vigilance_level": 1.0,
            "last_event_time": time.time(),
            "current_mood": scenario.get("today_mood", "Bình thường")
        })

        now_ts = time.time()
        event_entry = {
            "timestamp": now_ts,
            "iso_time": datetime.datetime.now().strftime("%H:%M:%S"),
            "event_type": event_type,
            "details": details or {}
        }
        stream.append(event_entry)
        state["last_event_time"] = now_ts

        if event_type == "CAPTCHA_ALERT":
            state["vigilance_level"] = min(2.5, state.get("vigilance_level", 1.0) + 0.40)
            state["current_mood"] = "Căng thẳng & Cảnh giác cao độ"
            print(f"[Episodic Stream] Profile '{profile_id}' ghi nhận CAPTCHA_ALERT -> Cảnh giác tăng lên {state['vigilance_level']:.2f}")

        elif event_type == "CAPTCHA_RESOLVED":
            state["vigilance_level"] = max(1.15, state.get("vigilance_level", 1.0) - 0.20)
            state["current_mood"] = "Cẩn trọng & Hồi phục"
            print(f"[Episodic Stream] Profile '{profile_id}' giải Captcha thành công -> Cảnh giác ổn định ở {state['vigilance_level']:.2f}")

        elif event_type == "AFK_DISTRACTION":
            state["accumulated_fatigue"] = min(1.0, state.get("accumulated_fatigue", 0.0) + 0.03)
            print(f"[Episodic Stream] Profile '{profile_id}' vừa bị gián đoạn AFK: {details.get('reason', '') if details else ''}")

        elif event_type == "SESSION_COMPLETED":
            state["sessions_completed"] = state.get("sessions_completed", 0) + 1
            state["accumulated_fatigue"] = min(1.0, state.get("accumulated_fatigue", 0.0) + 0.08)
            if state["accumulated_fatigue"] >= 0.45:
                state["current_mood"] = "Oải & Giảm tập trung"
            print(f"[Episodic Stream] Profile '{profile_id}' hoàn thành phiên #{state['sessions_completed']} -> Mệt mỏi tích lũy: {state['accumulated_fatigue']:.2f}")

        self._save()
        return state

    def get_effective_behavioral_params(self, profile_id: str, profile_name: str = "") -> Dict[str, Any]:
        """
        Tính toán tham số hành vi hiệu dụng tức thời kết hợp giữa Kịch bản gốc và Trạng thái động (Intra-day State).
        - Khi mệt mỏi tăng: tốc độ chuột chậm hơn, xác suất click trượt và quên tăng nhẹ.
        - Khi cảnh giác cao (sau Captcha): thao tác nắn nót hơn (fumble giảm 30%), tốc độ chậm lại để cẩn trọng.
        """
        scenario = self.get_or_generate_scenario(profile_id, profile_name)
        state = scenario.setdefault("intra_day_state", {
            "sessions_completed": 0,
            "accumulated_fatigue": 0.0,
            "vigilance_level": 1.0,
            "last_event_time": time.time(),
            "current_mood": scenario.get("today_mood", "Bình thường")
        })

        base_speed = scenario.get("speed_multiplier", 1.0)
        base_fumble = scenario.get("fumble_rate", 0.05)
        base_distract = scenario.get("distraction_prob", 0.12)
        fatigue = state.get("accumulated_fatigue", 0.0)
        vigilance = state.get("vigilance_level", 1.0)

        # Điều chế tốc độ chuột: Mệt mỏi làm chậm chạp (speed mult tăng thời gian di chuyển)
        eff_speed = base_speed * (1.0 + fatigue * 0.25)
        if vigilance > 1.2:
            eff_speed *= 1.15  # Thao tác cẩn trọng hơn sau khi gặp Captcha

        # Điều chế xác suất click trượt (fumble rate)
        eff_fumble = base_fumble * (1.0 + fatigue * 0.40)
        if vigilance > 1.2:
            eff_fumble *= 0.65  # Tập trung cao độ nên ít click trượt hơn

        eff_distract = base_distract * (1.0 + fatigue * 0.30)
        if vigilance > 1.2:
            eff_distract *= 0.50  # Đang bị chú ý nên không lơ là AFK

        return {
            "effective_speed_multiplier": round(eff_speed, 3),
            "effective_fumble_rate": round(eff_fumble, 4),
            "effective_miss_click_prob": round(eff_fumble, 4),
            "effective_distraction_prob": round(eff_distract, 4),
            "effective_distract_rate": round(eff_distract, 4),
            "vigilance_level": round(vigilance, 2),
            "accumulated_fatigue": round(fatigue, 3),
            "current_mood": state.get("current_mood", scenario.get("today_mood")),
            "sessions_completed": state.get("sessions_completed", 0)
        }


"""
HỆ THỐNG 4C: QUẢN LÝ 33 CON NGƯỜI SỐNG ĐỘNG (LIVING PERSONA IDENTITY ENGINE)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Tạo và lưu trữ cố định DANH TÍNH, NGHỀ NGHIỆP, TÍNH CÁCH VÀ THÓI QUEN ĐỜI THỰC cho từng Profile
"""

import json
import os
import random
import sys
import time
from typing import Dict, Any, List

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


class PersonaManager:
    """
    Quản lý 33 Bản thể người thật hoàn chỉnh:
    - Mỗi Profile là một CON NGƯỜI CÓ DANH TÍNH CỐ ĐỊNH:
      + Họ tên, Giới tính, Độ tuổi (19 - 48 tuổi).
      + Nghề nghiệp đời thực cụ thể (Lập trình viên, Mẹ bỉm sữa, Sinh viên, Giáo viên, Nhân viên văn phòng, v.v.).
      + Tính cách & Phong cách thao tác (Cẩn thận, Vội vã, Đãng trí, Thức khuya, Thư thái).
      + Phần cứng giả định (Chuột gaming DPI cao, Chuột văn phòng hơi trơn, Touchpad laptop...).
    """

    VIETNAMESE_NAMES_MALE = [
        "Nguyễn Hoàng Nam", "Trần Tuấn Anh", "Lê Minh Đức", "Phạm Quốc Huy", "Vũ Hải Đăng",
        "Đặng Gia Bảo", "Bùi Thành Long", "Đỗ Quang Minh", "Ngô Đình Trọng", "Dương Tấn Phát",
        "Hoàng Khắc Tiệp", "Trịnh Hữu Thắng", "Mai Xuân Hùng", "Lý Thanh Tùng", "Đoàn Văn Hậu"
    ]

    VIETNAMESE_NAMES_FEMALE = [
        "Trần Thị Mai Lan", "Nguyễn Thùy Dung", "Lê Ngọc Bích", "Phạm Thu Trang", "Đặng Thảo Vy",
        "Bùi Phương Anh", "Đỗ Hải Yến", "Vũ Kim Ngân", "Hoàng Như Quỳnh", "Ngô Bảo Châu",
        "Dương Thùy Linh", "Lý Mỹ Duyên", "Mai Thu Hằng", "Phan Thanh Trúc", "Đinh Bích Phương"
    ]

    OCCUPATIONS = [
        {
            "job": "Kỹ sư phần mềm (Backend Developer)",
            "workplace": "Công ty công nghệ",
            "habits": "Thức khuya, hay tranh thủ vào game lúc build code hoặc fix bug, click chuột nhanh và dứt khoát.",
            "preferred_hours": [7, 8, 12, 13, 19, 20, 21, 22, 23, 0]
        },
        {
            "job": "Kế toán viên doanh nghiệp",
            "workplace": "Văn phòng tài chính",
            "habits": "Rất cẩn thận, click chậm rãi nắn nót, giờ giấc công sở nghiêm ngặt, chỉ vào đúng giờ trưa và sau 18h.",
            "preferred_hours": [6, 7, 11, 12, 18, 19, 20, 21]
        },
        {
            "job": "Sinh viên năm cuối ngành Kinh tế",
            "workplace": "Ký túc xá / Phòng trọ",
            "habits": "Thời gian linh hoạt, hay vừa nghe nhạc vừa chơi, thỉnh thoảng đang chơi thì mải tám chuyện nên AFK.",
            "preferred_hours": [8, 9, 10, 14, 15, 16, 20, 21, 22, 23, 1]
        },
        {
            "job": "Mẹ bỉm sữa kinh doanh Online",
            "workplace": "Tại nhà",
            "habits": "Ở nhà cả ngày nhưng bận con nhỏ, vào game nhiều lượt ngắn, đang gieo hạt hay bị ngắt quãng vì con khóc.",
            "preferred_hours": [7, 9, 11, 13, 15, 17, 20, 22]
        },
        {
            "job": "Designer tự do (Freelancer)",
            "workplace": "Quán cà phê / Nhà riêng",
            "habits": "Gu thẩm mỹ cao, hay rê chuột ngắm nấm ngắm hoa, giờ ngủ thất thường, có hôm cày suốt đêm.",
            "preferred_hours": [10, 11, 14, 15, 16, 21, 22, 23, 1, 2]
        },
        {
            "job": "Nhân viên Ngân hàng (Giao dịch viên)",
            "workplace": "Chi nhánh ngân hàng",
            "habits": "Ban ngày bận tiếp khách không thể đụng vào máy tính, chỉ chơi sáng sớm và tối sau 19h30.",
            "preferred_hours": [6, 7, 12, 19, 20, 21, 22]
        },
        {
            "job": "Giáo viên cấp 3",
            "workplace": "Trường THPT",
            "habits": "Chỉ rảnh lúc giữa các tiết học hoặc buổi tối sau khi chấm bài xong, thao tác điềm đạm.",
            "preferred_hours": [6, 11, 12, 17, 18, 20, 21]
        },
        {
            "job": "Chủ tiệm tạp hóa / Quản lý cửa hàng",
            "workplace": "Cửa hàng gia đình",
            "habits": "Vừa bán hàng vừa trông máy tính, thỉnh thoảng có khách vào mua đồ là dừng chuột 20 - 40 giây.",
            "preferred_hours": [7, 8, 9, 10, 14, 15, 16, 19, 20, 21]
        }
    ]

    TEMPERAMENTS = [
        {
            "type": "Cẩn thận & Tỉ mỉ",
            "speed_range": (1.05, 1.30),
            "jitter_range": (2, 4),
            "click_hold_range": (85, 130),
            "fumble_rate": 0.03,
            "afk_rate": 0.08,
            "quirk": "Luôn di chuột chậm rãi, ít khi bấm trượt, thích kiểm tra kỹ từng ô đất."
        },
        {
            "type": "Vội vã & Nóng tính",
            "speed_range": (0.75, 0.95),
            "jitter_range": (4, 7),
            "click_hold_range": (60, 95),
            "fumble_rate": 0.09,
            "afk_rate": 0.12,
            "quirk": "Click rất nhanh và giật cục, thỉnh thoảng click trượt ra rìa luống đất rồi mới bấm lại."
        },
        {
            "type": "Đãng trí & Mơ mộng",
            "speed_range": (0.95, 1.20),
            "jitter_range": (3, 6),
            "click_hold_range": (75, 115),
            "fumble_rate": 0.06,
            "afk_rate": 0.22,
            "quirk": "Hay ngẩn người dừng chuột ngắm cảnh, quên bẵng đi việc đang làm, thường xuyên AFK giữa chừng."
        },
        {
            "type": "Thư thái & Cân bằng",
            "speed_range": (0.90, 1.10),
            "jitter_range": (3, 5),
            "click_hold_range": (70, 110),
            "fumble_rate": 0.05,
            "afk_rate": 0.10,
            "quirk": "Nhịp thở thao tác đều đặn, thi thoảng rê chuột lướt nhẹ qua xem nông trại."
        }
    ]

    def __init__(self, personas_file: str = "personas.json"):
        self.personas_file = personas_file
        self.personas = self._load()

    def _load(self) -> Dict:
        """Đọc danh sách personas với cơ chế phòng ngừa file hỏng."""
        for path in [self.personas_file, f"{self.personas_file}.bak"]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[PersonaManager Warning] Lỗi đọc {path}: {e}")
        return {}

    def _save(self):
        """Ghi file an toàn nguyên tử (Atomic Write)."""
        tmp_file = f"{self.personas_file}.tmp"
        bak_file = f"{self.personas_file}.bak"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.personas, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            if os.path.exists(self.personas_file):
                try:
                    if os.path.exists(bak_file):
                        os.remove(bak_file)
                    os.replace(self.personas_file, bak_file)
                except Exception:
                    pass

            os.replace(tmp_file, self.personas_file)
        except Exception as e:
            print(f"[PersonaManager Error] Không thể lưu personas an toàn: {e}")
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass

    def get_or_create_persona(self, profile_id: str, profile_name: str = "") -> Dict[str, Any]:
        """
        Lấy hoặc khởi tạo DANH TÍNH CON NGƯỜI ĐỜI THỰC cho Profile:
        Nếu profile đã có ADN từ trước, bổ sung thông tin nhân khẩu học sống động nếu còn thiếu.
        """
        if profile_id in self.personas and "human_identity" in self.personas[profile_id]:
            return self.personas[profile_id]

        # 1. Chọn giới tính và tên người Việt
        is_male = random.random() < 0.5
        human_name = random.choice(self.VIETNAMESE_NAMES_MALE if is_male else self.VIETNAMESE_NAMES_FEMALE)
        age = random.randint(20, 42)

        # 2. Chọn nghề nghiệp và nơi làm việc
        occ = random.choice(self.OCCUPATIONS)

        # 3. Chọn tính khí thao tác chuột
        temperament = random.choice(self.TEMPERAMENTS)

        speed_factor = round(random.uniform(*temperament["speed_range"]), 2)
        jitter_px = random.randint(*temperament["jitter_range"])
        click_hold_base = random.randint(*temperament["click_hold_range"])

        human_identity = {
            "real_name": human_name,
            "gender": "Nam" if is_male else "Nữ",
            "age": age,
            "occupation": occ["job"],
            "workplace": occ["workplace"],
            "lifestyle_habits": occ["habits"],
            "temperament": temperament["type"],
            "behavioral_quirk": temperament["quirk"],
            "base_fumble_rate": temperament["fumble_rate"],
            "base_afk_rate": temperament["afk_rate"]
        }

        persona = {
            "profile_id": profile_id,
            "profile_name": profile_name or human_name,
            "human_identity": human_identity,
            "personality_type": temperament["type"],
            "mouse_speed_factor": speed_factor,
            "jitter_px": jitter_px,
            "click_hold_base_ms": click_hold_base,
            "preferred_hours": occ["preferred_hours"],
            "created_at": time.time()
        }

        self.personas[profile_id] = persona
        self._save()

        print(f"\n[PersonaManager] +++ KHỞI TẠO DANH TÍNH CON NGƯỜI MỚI CHO '{profile_name}':")
        print(f" -> Tên: {human_name} ({age} tuổi, {human_identity['gender']})")
        print(f" -> Nghề nghiệp: {occ['job']} tại {occ['workplace']}")
        print(f" -> Tính khí: {temperament['type']} | Đặc điểm: {temperament['quirk']}\n")

        return persona

    def calculate_forgetting_delay(self, profile_id: str, crop_duration_seconds: int) -> float:
        """
        Tính độ trễ quên tự nhiên theo thời gian sinh học:
        - 80%: Quên bình thường theo phân phối chuẩn.
        - 15%: Bận việc đời thực (15 - 35 phút).
        - 5%: Đột biến quên bẵng (1 - 2.5 tiếng).
        """
        rand_val = random.random()

        if rand_val < 0.05:
            outlier_seconds = random.uniform(3600, 9000)
            return outlier_seconds

        if rand_val < 0.20:
            return random.uniform(900, 2100)

        if crop_duration_seconds <= 300:
            return random.uniform(45, 180)
        elif crop_duration_seconds <= 7200:
            return random.uniform(180, 600)
        else:
            return random.uniform(900, 2700)


if __name__ == "__main__":
    pm = PersonaManager("test_p.json")
    p = pm.get_or_create_persona("test-01", "GPM-Acc-1")
    print("Test persona:", p["human_identity"]["real_name"])
    if os.path.exists("test_p.json"):
        os.remove("test_p.json")

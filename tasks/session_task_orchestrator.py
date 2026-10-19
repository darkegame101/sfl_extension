"""
HỆ THỐNG 5B: ĐIỀU PHỐI ĐA NHIỆM & XÁC SUẤT BỎ SÓT SINH HỌC (SESSION TASK ORCHESTRATOR)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Mô phỏng thang bậc chú ý thị giác con người và xác suất phân loại phiên (Vội vã, Tiêu chuẩn, Toàn diện)
"""

import datetime
import random
from typing import Dict, Any, List, Tuple


class SessionTaskOrchestrator:
    """
    Điều phối danh sách công việc trong từng phiên dựa trên Xác suất Sinh học:
    1. Xác suất Phân loại Phiên (Session Type Probabilities):
       - QUICK_RUSH (Phiên chớp nhoáng 1.5 - 2 phút): Chỉ làm ruộng. Bỏ qua hoàn toàn nấm, mật ong, chặt cây, composter.
       - STANDARD (Phiên tiêu chuẩn 2.5 - 4 phút): Làm ruộng + Chặt cây to + (50% Composter). Thường quên nấm / mật ong.
       - FULL_MAINTENANCE (Phiên toàn diện 4 - 7 phút): Làm sạch sẽ toàn bộ nông trại (Ruộng, Cây, Ong, Nấm, Composter, NPC).
    2. Xác suất Bỏ sót / Lãng quên theo Thang bậc Thị giác (Visual Saliency):
       - Ruộng đất: 100% không sót (Mắt đập ngay vào tâm).
       - Chặt cây: 85% làm (Cây to dễ thấy).
       - Composter: 55% làm (Nằm góc vườn, 45% quên nạp).
       - Thu mật ong: 50% làm (50% quên thu hoạch, để phiên sau).
       - Nhặt nấm: 40% làm (60% bỏ sót vì mọc ở rìa cỏ ngoài tầm mắt).
    3. Tỷ lệ phân bổ biến thiên linh hoạt theo Khung Giờ Trong Ngày & Tâm Trạng.
    """

    @classmethod
    def determine_session_plan(
        cls,
        scenario: Dict[str, Any],
        persona: Dict[str, Any],
        current_hour: float,
        session_index_today: int
    ) -> Dict[str, Any]:
        """
        Quyết định kế hoạch hành vi và danh sách công việc cho phiên này:
        Trả về: {
            "session_type": "QUICK_RUSH" | "STANDARD" | "FULL_MAINTENANCE",
            "type_label": Mô tả tiếng Việt,
            "tasks_to_execute": List các task ["CROPS", "TREES", ...],
            "omitted_tasks": List các task bị bỏ sót kèm lý do,
            "estimated_duration_sec": Thời gian ước tính của phiên
        }
        """
        temperament = persona.get("human_identity", {}).get("temperament", "Cẩn thận & Tỉ mỉ")
        category = scenario.get("category", "OFFICE_STANDARD")
        real_name = scenario.get("real_name", "Người chơi")

        # 1. TÍNH XÁC SUẤT LOẠI PHIÊN DỰA TRÊN KHUNG GIỜ VÀ KỊCH BẢN
        # Tỷ lệ mặc định: (Quick Rush, Standard, Full Maintenance)
        if category == "DEADLINE_OVERTIME":
            # Ngày tăng ca chạy deadline -> 85% chỉ vào chớp nhoáng
            weights = [85, 15, 0]
        elif category == "FAMILY_TRIP_DETOX":
            # Đi du lịch/ăn cưới -> 90% chớp nhoáng ngó qua rồi đóng
            weights = [90, 10, 0]
        elif category == "LAZY_RAINY_AFTERNOON":
            # Ngày uể oải lười biếng -> Ưu tiên vừa phải
            weights = [60, 35, 5]
        elif category == "WFH_RAINY_DAY":
            # Làm việc tại nhà -> Vào thường xuyên, đều đặn
            weights = [50, 40, 10]
        elif category == "WEEKEND_CAFE":
            # Cà phê cuối tuần cùng bạn bè -> Thư thái, tỷ lệ chăm sóc nông trại toàn diện cao
            weights = [20, 50, 30]
        elif category == "OFFICE_STANDARD":
            # Phân bổ linh hoạt theo chu kỳ làm việc công sở
            if 6.0 <= current_hour < 8.5:
                weights = [75, 25, 0]
            elif 11.5 <= current_hour < 13.5:
                weights = [35, 55, 10]
            elif 17.5 <= current_hour < 19.5:
                weights = [45, 45, 10]
            elif 19.5 <= current_hour < 23.0:
                weights = [15, 45, 40]
            else:
                weights = [65, 30, 5]
        else:
            weights = [40, 40, 20]

        # Điều chỉnh nhẹ theo tính khí
        if "Vội vã" in temperament:
            weights[0] += 15  # thiên về Quick Rush
            weights[2] = max(0, weights[2] - 10)
        elif "Cẩn thận" in temperament:
            weights[1] += 10
            weights[2] += 10
            weights[0] = max(5, weights[0] - 20)

        # Tung xúc xắc chọn loại phiên
        session_types = ["QUICK_RUSH", "STANDARD", "FULL_MAINTENANCE"]
        chosen_type = random.choices(session_types, weights=weights, k=1)[0]

        # 2. XÁC ĐỊNH DANH SÁCH TASK CỤ THỂ THEO XÁC SUẤT BỎ SÓT THỊ GIÁC
        tasks = []
        omitted = []

        # A. RUỘNG ĐẤT: 100% người chơi luôn luôn làm ruộng (không bao giờ bỏ sót)
        tasks.append("CROPS")

        if chosen_type == "QUICK_RUSH":
            type_label = "⚡ Phiên Chớp Nhoáng (Vội việc đời thực)"
            duration_est = random.uniform(85, 125)  # 1.5 - 2 phút
            omitted.append(("TREES", "Vội vàng nên không chặt cây"))
            omitted.append(("HONEY", "Không kịp ngó hộp mật ong ở góc vườn"))
            omitted.append(("MUSHROOMS", "Không để ý nấm mọc ở bãi cỏ rìa ngoài"))
            omitted.append(("COMPOSTER", "Để phân ủ sang phiên tối mới nạp"))

        elif chosen_type == "STANDARD":
            type_label = "🏢 Phiên Tiêu Chuẩn (Nông nghiệp thường nhật)"
            duration_est = random.uniform(150, 240) # 2.5 - 4 phút

            # Cây gỗ to đập vào mắt (85% chặt)
            if random.random() < 0.85:
                tasks.append("TREES")
            else:
                omitted.append(("TREES", "Để dành cây gỗ chưa chặt vội"))

            # Thùng ủ phân Composter (60% nhớ ra)
            if random.random() < 0.60:
                tasks.append("COMPOSTER")
            else:
                omitted.append(("COMPOSTER", "Quên không kiểm tra thùng ủ phân Composter"))

            # Tổ ong Beehive (45% nhớ ra)
            if random.random() < 0.45:
                tasks.append("HONEY")
            else:
                omitted.append(("HONEY", "Quên không ngó tổ ong ở góc vườn"))

            # Nấm hoang dã mọc rìa ngoài (35% nhìn thấy)
            if random.random() < 0.35:
                tasks.append("MUSHROOMS")
            else:
                omitted.append(("MUSHROOMS", "Nấm mọc ở rìa cỏ xa tầm mắt, người chơi không nhìn thấy"))

        else: # FULL_MAINTENANCE
            type_label = "☕ Phiên Dọn Dẹp Toàn Diện (Thư thái cuối ngày)"
            duration_est = random.uniform(250, 400) # 4 - 6.5 phút
            tasks.extend(["TREES", "HONEY", "COMPOSTER", "MUSHROOMS", "DINERS"])

        plan = {
            "session_type": chosen_type,
            "type_label": type_label,
            "tasks_to_execute": tasks,
            "omitted_tasks": omitted,
            "estimated_duration_sec": round(duration_est, 1)
        }
        return plan


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    sc = {"real_name": "Nam", "category": "OFFICE_STANDARD"}
    p = {"human_identity": {"temperament": "Vội vã & Nóng tính"}}
    plan = SessionTaskOrchestrator.determine_session_plan(sc, p, 7.5, 1)
    print("Test Plan sáng sớm (7h30):", plan["type_label"])
    print("Tasks:", plan["tasks_to_execute"])
    print("Bỏ sót:", plan["omitted_tasks"])

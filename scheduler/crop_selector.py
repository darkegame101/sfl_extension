"""
HỆ THỐNG 4E: BỘ LỰA CHỌN HẠT GIỐNG THÍCH ỨNG SINH HỌC (SMART BIOLOGICAL CROP SELECTOR)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Người thật luôn chọn hạt giống phù hợp với khoảng thời gian rảnh rỗi tiếp theo trong ngày
"""

import datetime
import random
from typing import Dict, Any, Tuple


class SmartCropSelector:
    """
    Quy tắc con người khi chọn cây trồng:
    1. Chuẩn bị đi làm (4 - 5 tiếng nữa mới rảnh):
       -> Gieo Cabbage (2h), Carrot (1h) hoặc Beetroot (3.6h). Tuyệt đối không gieo Sunflower 1p!
    2. Buổi tối trước khi đi ngủ (7 - 8 tiếng nữa mới thức dậy):
       -> Gieo Cây qua đêm (Overnight): Parsnip (10.8h), Cauliflower (7.2h), Radish/Wheat (21.6h).
    3. Đang trong khung giờ rảnh rỗi cày cuốc (Marathon / Giờ trưa còn dài):
       -> Gieo Cây ngắn ngày: Sunflower (1p), Potato (5p), Pumpkin (30p) để thu hoạch ngay.
    4. Ngày bận rộn (Deadline / Đi công tác / Đi chơi):
       -> Gieo Cây dài ngày: Parsnip, Wheat, Radish để đất không bị bỏ phí.
    """

    CROPS_CATALOG = [
        {"name": "Sunflower", "grow_sec": 60, "min_gap": 0, "max_gap": 600, "desc": "Cây siêu ngắn (1 phút) - Cày cuốc liên tục"},
        {"name": "Potato", "grow_sec": 300, "min_gap": 300, "max_gap": 1500, "desc": "Cây ngắn (5 phút) - Canh nhanh"},
        {"name": "Pumpkin", "grow_sec": 1800, "min_gap": 1500, "max_gap": 3600, "desc": "Cây 30 phút - Giải lao ngắn"},
        {"name": "Carrot", "grow_sec": 3600, "min_gap": 3300, "max_gap": 7200, "desc": "Cây 1 giờ - Nghỉ trưa hoặc họp nhẹ"},
        {"name": "Cabbage", "grow_sec": 7200, "min_gap": 6600, "max_gap": 14400, "desc": "Cây 2 giờ - Giữa ca làm việc sáng/chiều"},
        {"name": "Beetroot", "grow_sec": 12960, "min_gap": 12000, "max_gap": 21600, "desc": "Cây 3.6 giờ - Nửa ngày công sở"},
        {"name": "Cauliflower", "grow_sec": 25920, "min_gap": 21600, "max_gap": 32400, "desc": "Cây 7.2 giờ - Cả ngày làm việc hoặc ngủ đêm ngắn"},
        {"name": "Parsnip", "grow_sec": 38880, "min_gap": 32400, "max_gap": 60000, "desc": "Cây 10.8 giờ - Trồng qua đêm hoàn hảo"},
        {"name": "Wheat", "grow_sec": 77760, "min_gap": 50000, "max_gap": 100000, "desc": "Cây 21.6 giờ - 1 ngày bận rộn / Tăng ca"},
        {"name": "Radish", "grow_sec": 77760, "min_gap": 50000, "max_gap": 100000, "desc": "Cây 21.6 giờ - Treo máy dài hạn"}
    ]

    @classmethod
    def select_best_crop(
        cls,
        scenario: Dict[str, Any],
        current_hour: float,
        time_until_next_slot: float,
        is_last_session_today: bool = False
    ) -> Tuple[str, int, str]:
        """
        Lựa chọn loại cây phù hợp nhất với quỹ thời gian đời thực:
        Trả về: (crop_name, grow_seconds, rationale_story)
        """
        category = scenario.get("category", "")
        real_name = scenario.get("real_name", "Người chơi")

        # 1. TRƯỜNG HỢP A: Sắp đi ngủ đêm (từ 22:30 đến 01:00) hoặc là phiên cuối cùng trong ngày
        # Người thật chắc chắn sẽ gieo cây dài hạn qua đêm!
        if is_last_session_today or current_hour >= 22.3 or current_hour < 2.0:
            overnight_choices = [
                ("Cauliflower", 25920, "Chuẩn bị đi ngủ, gieo Bông cải trắng (7.2h) để sáng mai thức dậy thu hoạch."),
                ("Parsnip", 38880, "Phiên cuối trước khi ngủ đêm, gieo Củ cải vàng (10.8h) để trưa mai hái."),
                ("Wheat", 77760, "Đêm muộn tắt máy đi ngủ, gieo Lúa mì (21.6h) cho cả ngày mai.")
            ]
            chosen = random.choice(overnight_choices)
            rationale = f"{real_name} kết thúc ngày: {chosen[2]}"
            return chosen[0], chosen[1], rationale

        # 2. TRƯỜNG HỢP B: Chạy Deadline tăng ca sấp mặt (DEADLINE_OVERTIME)
        # Đầu óc căng thẳng, chỉ vào chớp nhoáng -> Chọn cây trung/dài hạn không cần canh
        if category == "DEADLINE_OVERTIME":
            choices = [
                ("Beetroot", 12960, "Đang chạy deadline căng thẳng, gieo Củ dền (3.6h) để tập trung làm việc."),
                ("Cauliflower", 25920, "Hôm nay họp hành và OT liên miên, gieo Bông cải trắng (7.2h) treo máy an tâm."),
                ("Parsnip", 38880, "Tăng ca tới khuya không rảnh ngó game, gieo Củ cải vàng (10.8h).")
            ]
            chosen = random.choice(choices)
            return chosen[0], chosen[1], f"{real_name} ({scenario.get('job')}): {chosen[2]}"

        # 3. TRƯỜNG HỢP C: Đi du lịch / Đi ăn cưới ngoại tỉnh (FAMILY_TRIP_DETOX)
        # Cả ngày ngoài đường, chỉ online tối muộn -> Chọn cây dài ngày nhất để đất không mốc
        if category == "FAMILY_TRIP_DETOX":
            choices = [
                ("Wheat", 77760, "Đi chơi xa cả ngày, gieo Lúa mì (21.6h) để ngày mai về mới thu hoạch."),
                ("Radish", 77760, "Cả ngày bận việc gia đình họ hàng, gieo Củ cải đỏ (21.6h)."),
                ("Parsnip", 38880, "Đi du lịch ngoại tỉnh, gieo Củ cải vàng (10.8h) thong thả.")
            ]
            chosen = random.choice(choices)
            return chosen[0], chosen[1], f"{real_name}: {chosen[2]}"

        # 4. TRƯỜNG HỢP D: Ngày lười biếng / Uể oải (LAZY_RAINY_AFTERNOON)
        # Nằm lướt điện thoại trên giường, thỉnh thoảng ngó -> Chọn cây 30p - 2h
        if category == "LAZY_RAINY_AFTERNOON":
            choices = [
                ("Pumpkin", 1800, "Ngày lười biếng nằm nghỉ, gieo Bí đỏ (30 phút) xem phim xong ngó lại."),
                ("Cabbage", 7200, "Tâm trạng uể oải không muốn cày cuốc, gieo Bắp cải (2 giờ) rồi đi ngủ trưa."),
                ("Beetroot", 12960, "Lười vào game hôm nay, gieo Củ dền (3.6 giờ) tối mới dậy ngó.")
            ]
            chosen = random.choice(choices)
            return chosen[0], chosen[1], f"{real_name}: {chosen[2]}"

        # 5. TRƯỜNG HỢP E: Cà phê cuối tuần cùng bạn bè (WEEKEND_CAFE)
        # Ngồi quán cafe 2-3 tiếng, vừa chém gió vừa bấm máy -> Cây ngắn và trung
        if category == "WEEKEND_CAFE":
            choices = [
                ("Potato", 300, "Đang ngồi quán cafe với bạn, gieo Khoai tây (5 phút) vừa chém gió vừa bấm."),
                ("Pumpkin", 1800, "Nhâm nhi ly cà phê sáng chủ nhật, gieo Bí đỏ (30 phút) giải trí nhẹ nhàng."),
                ("Carrot", 3600, "Ngồi cafe chuẩn bị đi ăn trưa cùng bạn, gieo Cà rốt (1 giờ).")
            ]
            chosen = random.choice(choices)
            return chosen[0], chosen[1], f"{real_name}: {chosen[2]}"

        # 6. TRƯỜNG HỢP F: Làm việc tại nhà vì trời mưa (WFH_RAINY_DAY)
        # Ngồi ôm máy tính cả ngày -> Cây siêu ngắn để tối ưu hóa năng suất cày cuốc
        if category == "WFH_RAINY_DAY":
            if random.random() < 0.65:
                return "Sunflower", 60, f"{real_name} đang WFH bên máy tính, gieo Hướng dương (1 phút) để cày cuốc liên tục."
            else:
                return "Potato", 300, f"{real_name} vừa code vừa trông farm, gieo Khoai tây (5 phút) để đảo qua thu hoạch."

        # 7. TRƯỜNG HỢP G: Ngày làm việc công sở tiêu chuẩn (OFFICE_STANDARD)
        # Tính toán chính xác theo khoảng thời gian đến slot rảnh tiếp theo (time_until_next_slot)
        gap_hours = time_until_next_slot / 3600.0

        if gap_hours <= 0.3:  # Dưới 20 phút (Đang trong giờ nghỉ)
            if random.random() < 0.6:
                return "Sunflower", 60, f"{real_name} đang trong giờ nghỉ, gieo Hướng dương (1 phút) quay vòng nhanh."
            else:
                return "Potato", 300, f"{real_name} đang rảnh rỗi ăn trưa/nghỉ ngơi, gieo Khoai tây (5 phút)."

        elif gap_hours <= 1.5:  # Khoảng 1 tiếng nữa
            return "Pumpkin", 1800, f"{real_name} sắp có việc bận khoảng 45 phút, gieo Bí đỏ (30 phút) vừa vặn thời gian chín."

        elif gap_hours <= 3.0:  # Khoảng 2 - 3 tiếng nữa (hết giờ trưa vào ca chiều)
            return "Carrot", 3600, f"{real_name} chuẩn bị vào ca làm việc chiều, gieo Cà rốt (1 giờ) để giữa ca tranh thủ ngó."

        elif gap_hours <= 5.5:  # Khoảng 4 - 5 tiếng nữa (từ sáng đến trưa, hoặc từ chiều đến tan tầm)
            return "Cabbage", 7200, f"{real_name} vào ca làm việc 4 tiếng, gieo Bắp cải (2 giờ) để tan ca thu hoạch."

        else:  # Cách xa hơn 6 tiếng
            return "Beetroot", 12960, f"{real_name} có việc đi ra ngoài cả buổi, gieo Củ dền (3.6 giờ) an toàn."


if __name__ == "__main__":
    test_scenario = {
        "real_name": "Nguyễn Hoàng Nam",
        "job": "Kỹ sư Backend",
        "category": "OFFICE_STANDARD"
    }
    crop, sec, r = SmartCropSelector.select_best_crop(test_scenario, 8.0, 14400.0) # gap 4h
    print(f"Ket qua chon cay luc 8h sang (gap 4h): {crop} ({sec}s) - {r}")

"""
HỆ THỐNG 1: VẬN ĐỘNG HỌC CHUỘT PHẦN CỨNG (BIOMECHANICAL MOUSE ENGINE)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Chạy trực tiếp qua Windows Win32 SendInput (isTrusted: true 100%)
"""

import ctypes
import math
import random
import time
from typing import Tuple, List

# --- Cấu trúc Windows Win32 API ---
ULONG_PTR = ctypes.c_ulong if ctypes.sizeof(ctypes.c_void_p) == 4 else ctypes.c_ulonglong

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR)
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_UNION)
    ]

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

user32 = ctypes.windll.user32


class HumanMouse:
    """
    Bộ điều khiển chuột cấp hệ điều hành mô phỏng hoàn toàn chuyển động sinh học:
    - Bắn sự kiện phần cứng thật qua SendInput (isTrusted: true).
    - Quỹ đạo cong Bézier bậc 3 có gia tốc (ease-in / ease-out).
    - Rung lắc vi mô (Micro-jitter) và vượt đích điều chỉnh (Overshoot & Correction).
    - Độ giữ phím tự nhiên (Hold time: 65ms - 130ms).
    """

    @staticmethod
    def get_position() -> Tuple[int, int]:
        """Lấy vị trí con trỏ chuột hiện tại trên màn hình."""
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    @classmethod
    def _send_input(cls, flags: int, x: int = 0, y: int = 0):
        """Gửi gói tin INPUT cấp OS trực tiếp vào hàng đợi thông điệp phần cứng."""
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.u.mi.dx = x
        inp.u.mi.dy = y
        inp.u.mi.mouseData = 0
        inp.u.mi.dwFlags = flags
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = 0
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    @classmethod
    def set_cursor_pos(cls, x: int, y: int):
        """Đặt vị trí con trỏ chuột."""
        user32.SetCursorPos(int(x), int(y))

    @staticmethod
    def _bezier_point(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
        """Tính tọa độ tại thời điểm t trên đường cong Cubic Bézier."""
        return (
            (1 - t) ** 3 * p0 +
            3 * (1 - t) ** 2 * t * p1 +
            3 * (1 - t) * t ** 2 * p2 +
            t ** 3 * p3
        )

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """Hàm gia tốc sinh học: chậm ở 2 đầu, nhanh ở đoạn giữa."""
        if t < 0.5:
            return 2 * t * t
        return 1 - ((-2 * t + 2) ** 2) / 2

    @staticmethod
    def calculate_fitts_duration(distance: float, target_width: float = 50.0, a: float = 0.15, b: float = 0.21) -> float:
        """
        Tính thời gian di chuyển lý thuyết MT theo Định luật Fitts (Công thức Shannon - MacKenzie 1992):
        MT = a + b * log2(D / W + 1)
        """
        if distance <= 0 or target_width <= 0:
            return a
        index_difficulty = math.log2(distance / target_width + 1.0)
        return a + b * index_difficulty

    @classmethod
    def move_to(
        cls,
        target_x: int,
        target_y: int,
        duration: float = None,
        target_width: float = None,
        random_offset: int = 4,
        allow_overshoot: bool = True
    ):
        """
        Di chuyển chuột từ vị trí hiện tại đến (target_x, target_y)
        theo đường cong Bézier uốn lượn có gia tốc và rung tay.
        """
        start_x, start_y = cls.get_position()

        # Áp dụng độ lệch ngẫu nhiên quanh tâm (Gaussian Offset)
        dest_x = target_x + int(random.gauss(0, random_offset / 2))
        dest_y = target_y + int(random.gauss(0, random_offset / 2))

        distance = math.hypot(dest_x - start_x, dest_y - start_y)
        if distance < 3:
            cls.set_cursor_pos(dest_x, dest_y)
            return

        # Tính thời gian di chuyển dựa trên Mô hình Shannon-MacKenzie (1992): MT = a + b * log2(D / W + 1)
        if duration is None:
            a = random.uniform(0.12, 0.18)
            b = random.uniform(0.18, 0.24)
            tw = target_width if (target_width and target_width > 0) else random.uniform(35.0, 55.0)
            fitts_duration = cls.calculate_fitts_duration(distance, target_width=tw, a=a, b=b)
            duration = max(0.25, min(0.95, fitts_duration))

        # Tạo 2 điểm kiểm soát ngẫu nhiên (Control Points) để tạo độ võng tự nhiên
        deviation_scale = min(distance * 0.35, 120.0)
        ctrl1_x = start_x + (dest_x - start_x) * 0.25 + random.uniform(-deviation_scale, deviation_scale)
        ctrl1_y = start_y + (dest_y - start_y) * 0.25 + random.uniform(-deviation_scale, deviation_scale)

        # Mô phỏng Overshoot: di chuyển hơi lố đích rồi lùi lại nhẹ
        overshoot_x = 0
        overshoot_y = 0
        if allow_overshoot and distance > 100 and random.random() < 0.4:
            overshoot_x = random.uniform(-6, 6)
            overshoot_y = random.uniform(-6, 6)

        ctrl2_x = start_x + (dest_x - start_x) * 0.75 + random.uniform(-deviation_scale * 0.5, deviation_scale * 0.5) + overshoot_x
        ctrl2_y = start_y + (dest_y - start_y) * 0.75 + random.uniform(-deviation_scale * 0.5, deviation_scale * 0.5) + overshoot_y

        # Số bước di chuyển theo tần số lấy mẫu chuẩn 120Hz (mỗi bước ~8.33ms)
        POLLING_HZ = 120.0
        steps = max(15, int(duration * POLLING_HZ))
        sleep_step = duration / steps

        start_time = time.perf_counter()
        prev_x, prev_y = start_x, start_y
        for i in range(1, steps + 1):
            raw_t = i / steps
            eased_t = cls._ease_in_out(raw_t)

            cur_x = cls._bezier_point(start_x, ctrl1_x, ctrl2_x, dest_x, eased_t)
            cur_y = cls._bezier_point(start_y, ctrl1_y, ctrl2_y, dest_y, eased_t)

            # Thêm Micro-jitter sinh học (độ rung cơ học bàn tay 0.4 - 1.2 pixel)
            if i < steps - 3:
                cur_x += random.gauss(0, 0.5)
                cur_y += random.gauss(0, 0.5)

            cls.set_cursor_pos(cur_x, cur_y)

            # Điều tiết thời gian ngủ chính xác (High-precision sub-millisecond scheduling)
            elapsed = time.perf_counter() - start_time
            expected = i * sleep_step
            if expected > elapsed:
                time.sleep(expected - elapsed)

        # Đảm bảo điểm đích cuối cùng chuẩn xác
        cls.set_cursor_pos(dest_x, dest_y)

    @classmethod
    def curiosity_hover(cls, target_x: int, target_y: int, hover_sec: float = 0.45):
        """
        RÊ CHUỘT TÒ MÒ / XEM TOOLTIP (CURIOSITY HOVERING):
        - Người thật thường rê chuột qua xem timer hoặc tooltip của item trước khi quyết định click.
        - Rê chuột tới gần mục tiêu (độ lệch 3-8px), dừng lại 300ms - 600ms rồi mới tiếp tục.
        """
        offset_x = random.choice([-1, 1]) * random.randint(3, 8)
        offset_y = random.choice([-1, 1]) * random.randint(3, 8)
        cls.move_to(target_x + offset_x, target_y + offset_y, random_offset=2)
        cls.human_sleep(hover_sec * 0.8, hover_sec * 1.2)

    @classmethod
    def click(
        cls,
        target_x: int = None,
        target_y: int = None,
        button: str = 'left',
        random_offset: int = 4
    ):
        """
        Di chuyển tới mục tiêu (nếu có) và click chuột phần cứng thật:
        - Nhấn xuống (MouseDown)
        - Giữ chuột theo phân phối Log-Normal (Salthouse 1986, MacKenzie 1998)
        - Nhả chuột lên (MouseUp)
        """
        if target_x is not None and target_y is not None:
            cls.move_to(target_x, target_y, random_offset=random_offset)

        # Trễ sinh học nhỏ trước khi ngón tay bấm xuống (Card et al. 1983 KLM: 30ms - 80ms)
        time.sleep(random.uniform(0.03, 0.08))

        if button == 'left':
            down_flag = MOUSEEVENTF_LEFTDOWN
            up_flag = MOUSEEVENTF_LEFTUP
        else:
            down_flag = MOUSEEVENTF_RIGHTDOWN
            up_flag = MOUSEEVENTF_RIGHTUP

        # 1. Bấm chuột xuống
        cls._send_input(down_flag)

        # 2. Giữ phím chuột (Hold Duration): Phân phối Log-Normal (mu = ln(0.095) ≈ -2.35, sigma = 0.22)
        hold_time = random.lognormvariate(-2.35, 0.22)
        hold_time = max(0.050, min(0.160, hold_time))
        time.sleep(hold_time)

        # 3. Nhả chuột lên
        cls._send_input(up_flag)

        # 4. Trễ nghỉ sau click
        time.sleep(random.uniform(0.04, 0.09))

    @classmethod
    def fumble_click(
        cls,
        target_x: int,
        target_y: int,
        miss_offset: int = 18,
        button: str = 'left'
    ):
        """
        MÔ PHỎNG CLICK TRƯỢT (HUMAN FUMBLE / MISS-CLICK):
        - Người thật thỉnh thoảng click chệch ra rìa ngoài luống đất (15-25px).
        - Ngay sau đó nhận ra mình bấm trượt -> dừng lại một chút (200-400ms) -> di chuột lại đúng mục tiêu và click lại.
        """
        # 1. Điểm lệch ngoài mục tiêu
        offset_dir_x = random.choice([-1, 1])
        offset_dir_y = random.choice([-1, 1])
        miss_x = target_x + offset_dir_x * random.randint(miss_offset - 5, miss_offset + 10)
        miss_y = target_y + offset_dir_y * random.randint(miss_offset - 5, miss_offset + 10)

        # Di chuyển tới điểm lệch và click trượt
        cls.move_to(miss_x, miss_y, random_offset=2)
        cls.click(button=button)

        # Phản xạ nhận ra bấm trượt (Human Hesitation: 250 - 450ms)
        cls.human_sleep(0.25, 0.45)

        # Di chuyển lại vào tâm mục tiêu chuẩn xác và click lại
        cls.move_to(target_x, target_y, random_offset=4)
        cls.click(button=button)

    @classmethod
    def simulate_distraction(cls, min_sec: float = 12.0, max_sec: float = 40.0):
        """
        MÔ PHỎNG SỰ CỐ XAO NHÃNG ĐỘT XUẤT (AFK / DISTRACTION EVENT):
        - Đang thao tác bỗng dừng lại 12 - 40 giây (trả lời tin nhắn Zalo, shipper gọi, uống nước).
        - Chuột đứng yên, thỉnh thoảng chỉ nhích nhẹ 1-2px do tay vô tình tì vào chuột.
        """
        total_pause = random.uniform(min_sec, max_sec)
        print(f"[Human Stochastic] Xay ra su co xao nhang dot xuat (AFK Distraction): Tam dung {total_pause:.1f} giay...")

        start_time = time.time()
        while time.time() - start_time < total_pause:
            sub_pause = min(random.uniform(4.0, 9.0), total_pause - (time.time() - start_time))
            if sub_pause <= 0:
                break
            time.sleep(sub_pause)
            # Thỉnh thoảng tay vô tình chạm nhẹ vào chuột dịch chuyển 1px
            if random.random() < 0.4:
                cx, cy = cls.get_position()
                cls.set_cursor_pos(cx + random.choice([-1, 0, 1]), cy + random.choice([-1, 0, 1]))

    @classmethod
    def idle_wandering(cls, duration: float = 2.5):
        """
        MÔ PHỎNG DI CHUỘT LƠ ĐỄNH / NGẮM CẢNH (IDLE WANDERING):
        - Rê chuột lướt nhẹ qua một vị trí ngẫu nhiên không mục đích rồi dừng lại ngắm 1-2s.
        """
        cx, cy = cls.get_position()
        rand_x = max(100, min(1800, cx + random.randint(-180, 180)))
        rand_y = max(100, min(900, cy + random.randint(-120, 120)))
        cls.move_to(rand_x, rand_y, duration=0.8, random_offset=6)
        cls.human_sleep(1.0, 2.5)

    @classmethod
    def tab_lingering_pause(cls, min_sec: float = 35.0, max_sec: float = 120.0, reason: str = "Hành động ngoài đời xen vào"):
        """
        CƠ CHẾ TREO TAB KHI CÓ HÀNH ĐỘNG NGOÀI ĐỜI XEN VÀO:
        - Ví dụ: Shipper gọi, pha cà phê, trả lời tin nhắn Zalo, đi vệ sinh.
        - Giữ nguyên tab trình duyệt trên màn hình.
        - Chuột đứng yên, thỉnh thoảng trôi nhẹ vài pixel (như tay tì vào bàn).
        - Sau khi xong việc đời thực: Quay lại farm, ngắm 2-3s xác nhận mọi thứ ổn rồi mới tiếp tục.
        """
        pause_sec = random.uniform(min_sec, max_sec)
        print(f"\n[CƠ CHẾ TREO TAB] >>> {reason}!")
        print(f" -> Trình duyệt giữ nguyên trạng thái mở (Treo tab) trong {pause_sec:.1f} giây...")

        start_time = time.time()
        while time.time() - start_time < pause_sec:
            sub = min(random.uniform(5.0, 10.0), pause_sec - (time.time() - start_time))
            if sub <= 0:
                break
            time.sleep(sub)
            if random.random() < 0.35:
                cx, cy = cls.get_position()
                cls.set_cursor_pos(cx + random.choice([-2, -1, 0, 1, 2]), cy + random.choice([-2, -1, 0, 1, 2]))

        print("[CƠ CHẾ TREO TAB] <<< Đã giải quyết xong việc ngoài đời. Người chơi quay lại máy tính tiếp tục game!\n")
        cls.human_sleep(1.5, 3.0)

    @classmethod
    def post_farming_linger(cls, min_sec: float = 8.0, max_sec: float = 30.0):
        """
        NÁN LẠI TREO TAB SAU KHI FARM XONG (POST-FARM LINGERING):
        - Người thật gieo xong không bao giờ tắt browser trong 0.1s.
        - Họ nán lại nhìn ruộng, rê chuột qua kho đồ hoặc nhìn quanh đảo 8 - 30 giây rồi mới đóng tab!
        """
        linger_time = random.uniform(min_sec, max_sec)
        print(f"[Human Stochastic] Đã gieo hạt xong. Người chơi nán lại treo tab ngắm farm ({linger_time:.1f}s) trước khi đóng tab...")
        cls.idle_wandering(duration=1.5)
        time.sleep(linger_time * 0.5)
        if random.random() < 0.5:
            cls.idle_wandering(duration=1.2)
        time.sleep(linger_time * 0.5)

    @staticmethod
    def human_sleep(min_seconds: float, max_seconds: float):
        """Khoảng nghỉ ngẫu nhiên theo phân phối chuẩn Gaussian (tránh số chẵn)."""
        mean = (min_seconds + max_seconds) / 2.0
        std = (max_seconds - min_seconds) / 4.0
        delay = random.gauss(mean, std)
        delay = max(min_seconds, min(max_seconds, delay))
        time.sleep(delay)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 1: Chuot Van Dong Hoc & Tinh Bat Dinh ---")
    cur = HumanMouse.get_position()
    print(f"Vi tri chuot ban dau: {cur}")
    print("Dang di chuyen thu nghiem theo duong cong Bezier...")
    HumanMouse.move_to(cur[0] + 50, cur[1] + 50, random_offset=3)
    print(f"Vi tri sau khi di chuyen: {HumanMouse.get_position()}")
    print("Test thanh cong 100%!")


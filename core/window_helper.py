"""
HỆ THỐNG 2B: QUẢN LÝ CỬA SỔ & TỌA ĐỘ TƯƠNG ĐỐI (WIN32 WINDOW HELPER)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Chạy trực tiếp qua Windows Win32 API (user32.dll)
"""

import ctypes
from typing import Optional, Tuple, List

user32 = ctypes.windll.user32

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

SW_RESTORE = 9
SW_MAXIMIZE = 3


class WindowHelper:
    """
    Quản lý cửa sổ trình duyệt GPM-Login trên Windows:
    - Tìm cửa sổ theo Tiêu đề (Window Title) hoặc Process.
    - Đưa cửa sổ lên trên cùng (SetForegroundWindow) để nhận sự kiện chuột.
    - Tính toán tọa độ tương đối (Relative Coordinates) để cửa sổ nằm ở đâu cũng click trúng 100%.
    """

    @staticmethod
    def ensure_interactive_desktop():
        """
        Đảm bảo thread hiện tại đính kèm vào desktop tương tác 'default' của Windows (WinSta0\\default).
        Cần thiết khi chạy từ terminal con, IDE sandbox hoặc background service.
        """
        try:
            hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
                return hdesk
        except Exception:
            pass
        return None

    @classmethod
    def find_windows_by_keyword(cls, keyword: str) -> List[int]:
        """Tìm danh sách HWND các cửa sổ có tiêu đề chứa keyword."""
        hdesk = cls.ensure_interactive_desktop()
        hwnds = []

        from ctypes import wintypes

        def enum_proc(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if keyword.lower() in buff.value.lower():
                        hwnds.append(hwnd)
            return True

        ENUM_FUNC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        if hdesk:
            user32.EnumDesktopWindows.argtypes = [wintypes.HANDLE, ENUM_FUNC, wintypes.LPARAM]
            user32.EnumDesktopWindows.restype = wintypes.BOOL
            user32.EnumDesktopWindows(hdesk, ENUM_FUNC(enum_proc), 0)
        else:
            user32.EnumWindows.argtypes = [ENUM_FUNC, wintypes.LPARAM]
            user32.EnumWindows.restype = wintypes.BOOL
            user32.EnumWindows(ENUM_FUNC(enum_proc), 0)
        return hwnds

    @classmethod
    def find_windows_by_pid(cls, target_pid: int) -> List[int]:
        """Tìm HWND các cửa sổ hiển thị thuộc Process ID cụ thể."""
        if not target_pid:
            return []
        hdesk = cls.ensure_interactive_desktop()
        hwnds = []
        from ctypes import wintypes

        def enum_proc(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                proc_id = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                if proc_id.value == target_pid:
                    rect = RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    # Lọc bỏ các cửa sổ phụ/vô hình (kích thước quá nhỏ)
                    if w > 100 and h > 100:
                        hwnds.append(hwnd)
            return True

        ENUM_FUNC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        if hdesk:
            user32.EnumDesktopWindows.argtypes = [wintypes.HANDLE, ENUM_FUNC, wintypes.LPARAM]
            user32.EnumDesktopWindows.restype = wintypes.BOOL
            user32.EnumDesktopWindows(hdesk, ENUM_FUNC(enum_proc), 0)
        else:
            user32.EnumWindows.argtypes = [ENUM_FUNC, wintypes.LPARAM]
            user32.EnumWindows.restype = wintypes.BOOL
            user32.EnumWindows(ENUM_FUNC(enum_proc), 0)
        return hwnds

    @classmethod
    def find_game_window(cls, preferred_title: str = "", target_pid: Optional[int] = None) -> Optional[int]:
        """
        Tìm cửa sổ đang chạy Sunflower Land hoặc trình duyệt GPM Chromium:
        - Ưu tiên 0: Tìm theo target_pid chính xác của tiến trình Chromium (nếu có).
        - Ưu tiên 1: Cửa sổ chứa preferred_title (Tên Profile GPM cụ thể).
        - Ưu tiên 2: Cửa sổ có tiêu đề 'Sunflower Land' / 'sunflower-land'.
        - Ưu tiên 3: Cửa sổ GPM Chromium.
        - Tránh nhận nhầm Chrome cá nhân thông thường.
        """
        if target_pid:
            pid_hwnds = cls.find_windows_by_pid(target_pid)
            if pid_hwnds:
                return pid_hwnds[0]

        if preferred_title:
            hwnds = cls.find_windows_by_keyword(preferred_title)
            if hwnds:
                return hwnds[0]

        # Tìm các cửa sổ chuyên biệt của game
        for kw in ["Sunflower Land", "sunflower-land", "SunflowerLand"]:
            hwnds = cls.find_windows_by_keyword(kw)
            if hwnds:
                return hwnds[0]

        # Tìm cửa sổ GPM Browser
        for kw in ["GPM-Browser", "GPM Browser", "GPM", "gpm_browser"]:
            hwnds = cls.find_windows_by_keyword(kw)
            if hwnds:
                return hwnds[0]

        # Cuối cùng mới fallback tìm Chrome
        chrome_hwnds = cls.find_windows_by_keyword("Chrome")
        if chrome_hwnds:
            return chrome_hwnds[0]

        return None

    @staticmethod
    def get_window_title(hwnd: int) -> str:
        """Lấy tiêu đề của cửa sổ."""
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value
        return ""

    @classmethod
    def bring_to_foreground(cls, hwnd: int) -> bool:
        """Đưa cửa sổ lên trước màn hình, focus và xác thực Windows đã thực sự focus."""
        if not hwnd or not user32.IsWindow(hwnd):
            return False

        cls.ensure_interactive_desktop()
        import time

        # Nếu cửa sổ đang bị thu nhỏ (minimized), khôi phục lại
        user32.ShowWindow(hwnd, SW_RESTORE)

        # Mẹo bypass giới hạn SetForegroundWindow của Windows bằng cách đính thread input
        cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        fore_hwnd = user32.GetForegroundWindow()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, 0)

        for attempt in range(3):
            if cur_thread != fore_thread:
                user32.AttachThreadInput(cur_thread, fore_thread, True)
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                user32.AttachThreadInput(cur_thread, fore_thread, False)
            else:
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)

            time.sleep(0.04)
            # Xác thực cửa sổ hiện tại đã đúng là hwnd cần focus
            if user32.GetForegroundWindow() == hwnd:
                return True

        return user32.IsWindowVisible(hwnd) != 0

    @classmethod
    def get_client_rect_on_screen(cls, hwnd: int) -> Tuple[int, int, int, int]:
        """
        Lấy tọa độ vùng hiển thị nội dung web (Client Area) trên màn hình:
        Trả về (client_x, client_y, client_width, client_height).
        """
        cls.ensure_interactive_desktop()
        rect = RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))

        # Đổi điểm gốc (0, 0) của Client sang tọa độ màn hình thực tế (Screen Coords)
        pt = POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))

        width = rect.right - rect.left
        height = rect.bottom - rect.top
        return pt.x, pt.y, width, height

    @classmethod
    def to_screen_coords(cls, hwnd: int, rel_x: int, rel_y: int) -> Tuple[int, int]:
        """
        Chuyển đổi tọa độ tương đối trong khung game thành tọa độ màn hình thực:
        Screen_X = Client_X + rel_x
        Screen_Y = Client_Y + rel_y
        """
        cx, cy, _, _ = cls.get_client_rect_on_screen(hwnd)
        return cx + rel_x, cy + rel_y


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 2B: Quan ly Cua so Win32 ---")
    hwnd = WindowHelper.find_game_window()
    if hwnd:
        title = WindowHelper.get_window_title(hwnd)
        print(f"Phat hien cua so phu hop: HWND={hwnd}, Title='{title}'")
        cx, cy, cw, ch = WindowHelper.get_client_rect_on_screen(hwnd)
        print(f"Toa do vung hien thi (Client Area): x={cx}, y={cy}, width={cw}, height={ch}")
        test_screen_pos = WindowHelper.to_screen_coords(hwnd, 100, 100)
        print(f"Toa do tuong doi (100, 100) -> Toa do man hinh thuc te: {test_screen_pos}")
    else:
        print("Chua phat hien cua so game dang mo tren man hinh.")

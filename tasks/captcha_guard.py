"""
HỆ THỐNG 3B: LÁ CHẮN CAPTCHA & ĐÓNG BĂNG KHẨN CẤP (CAPTCHA GUARD)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Đóng băng chuột trong 0.01s nếu phát hiện kiểm tra bot
"""

import sys
import time

class CaptchaGuard:
    """
    Giám sát và bảo vệ tài khoản khi gặp thử thách Captcha:
    - Nếu AI hoặc bộ quét phát hiện chữ "Verify", "Captcha", "Proof of Humanity":
      1. Đóng băng chuột tức thì (Mouse Freeze).
      2. Kích hoạt còi báo động qua loa máy tính (winsound).
      3. Tạm dừng tiến trình và giữ nguyên trạng thái để người dùng vào xử lý tay.
    """

    @staticmethod
    def trigger_emergency_freeze(reason: str = "Phat hien Captcha / Bot Check!"):
        """
        Kích hoạt trạng thái tạm dừng khẩn cấp:
        LƯU Ý: Khái niệm 'Đóng băng' ở đây là DỪNG TOÀN BỘ TIẾN TRÌNH RPA của bot (không gửi thêm bất kỳ
        sự kiện chuột nào nữa) để giải phóng con trỏ chuột cho người dùng thật can thiệp giải captcha.
        Tool không can thiệp khóa phần cứng chuột ở tầng Windows Driver.
        """
        print("\n" + "=" * 65)
        print(f" [!!! CẢNH BÁO KHẨN CẤP !!!] {reason}")
        print(" -> TOÀN BỘ THAO TÁC CỦA BOT ĐÃ BỊ TẠM DỪNG (BLOCKING PAUSE).")
        print(" -> BẠN HÃY DÙNG CHUỘT THẬT TRÊN MÀN HÌNH ĐỂ GIẢI CAPTCHA THỦ CÔNG.")
        print("=" * 65 + "\n")

        # Phát âm thanh cảnh báo trên loa máy tính Windows (3 tiếng bíp dồn dập)
        try:
            import winsound
            for _ in range(3):
                winsound.Beep(1200, 300)
                time.sleep(0.1)
        except Exception:
            pass

    @classmethod
    def check_and_guard(cls, ai_analysis: dict, fail_safe: bool = True) -> bool:
        """
        Kiểm tra kết quả phân tích từ AI:
        - Nếu phát hiện Captcha: Báo động và trả về True (cần dừng bot).
        - Nếu AI bị lỗi (timeout, mất mạng, key sai):
            + Với nguyên tắc phòng thủ Fail-Safe: Cảnh báo nguy cơ, không để bot bấm mù trên màn hình.
            + Báo động nhẹ và yêu cầu người dùng xác nhận hoặc tạm dừng phiên.
        - Nếu màn hình an toàn: Trả về False.
        """
        if not ai_analysis:
            if fail_safe:
                print("[CaptchaGuard Warning] Không nhận được kết quả phân tích AI. Kích hoạt chế độ phòng ngừa an toàn.")
                return True
            return False

        if not ai_analysis.get("success"):
            err_msg = ai_analysis.get("error", "Lỗi không xác định")
            print(f"[CaptchaGuard Alert] AI Vision gặp sự cố: {err_msg}")
            if fail_safe:
                cls.trigger_emergency_freeze(f"AI Vision mất kết nối - Kích hoạt phòng vệ an toàn ({err_msg})")
                return True
            return False

        if ai_analysis.get("has_captcha"):
            details = ai_analysis.get("captcha_details") or "Thử thách xác minh bot"
            cls.trigger_emergency_freeze(f"Phát hiện Captcha: {details}")
            return True

        return False

    @classmethod
    def recheck_screen_after_solve(cls, ai_instance) -> bool:
        """
        Kiểm tra lại màn hình sau khi người dùng xác nhận đã giải xong Captcha.
        Trả về True nếu ĐÃ SẠCH CAPTCHA (an toàn để tiếp tục).
        Trả về False nếu VẪN CÒN CAPTCHA (cần hủy phiên hoặc chờ tiếp).
        """
        if not ai_instance or not getattr(ai_instance, "api_key", None):
            print("[CaptchaGuard] AI Vision không bật, không thể tự động thẩm định lại màn hình.")
            confirm = input("Bạn có chắc chắn 100% đã giải xong và màn hình đã vào lại game? (y/n): ")
            return confirm.strip().lower() == "y"

        print("[CaptchaGuard] Đang chụp màn hình kiểm chứng lại tình trạng Captcha...")
        screenshot = ai_instance.capture_screenshot()
        if not screenshot:
            print("[CaptchaGuard Warning] Không thể chụp màn hình kiểm chứng. Hủy phiên để an toàn.")
            return False

        re_analysis = ai_instance.analyze_screen(screenshot)
        if not re_analysis or not re_analysis.get("success"):
            err = re_analysis.get("error", "Lỗi phân tích AI") if isinstance(re_analysis, dict) else "Phân tích không phản hồi"
            print(f"[CaptchaGuard Warning] Phân tích lại màn hình thất bại ({err}). Không thể chứng thực màn hình đã sạch Captcha -> Hủy phiên để an toàn!")
            return False

        if re_analysis.get("has_captcha"):
            print(f"[CaptchaGuard Alert] Màn hình VẪN CÒN CAPTCHA: {re_analysis.get('captcha_details')}")
            return False

        print("[CaptchaGuard] Xác nhận màn hình ĐÃ SẠCH CAPTCHA. An toàn tiếp tục vận hành!")
        return True


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 3B: Captcha Guard ---")
    mock_captcha = {"success": True, "has_captcha": True, "captcha_details": "Goblin Chest Puzzle"}
    CaptchaGuard.check_and_guard(mock_captcha)
    print("Test thanh cong!")

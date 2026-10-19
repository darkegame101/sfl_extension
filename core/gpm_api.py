"""
HỆ THỐNG 2A: GIAO TIẾP GPM-LOGIN LOCAL API (GPM API CONNECTOR)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Kết nối trực tiếp GPM-Login v2 tại http://127.0.0.1:19995
"""

import requests
import time
from typing import List, Dict, Optional


class GpmAPI:
    """
    Quản lý kết nối và điều phối Profile GPM-Login qua Local REST API.
    Đảm bảo mỗi thời điểm chỉ có 1 profile hoạt động để giữ proxy sạch và tiết kiệm tài nguyên.
    """

    def __init__(self, api_base_url: str = "http://127.0.0.1:19995"):
        self.base_url = api_base_url.rstrip("/")
        self.session = requests.Session()

    def check_connection(self) -> bool:
        """Kiểm tra GPM-Login có đang bật trên máy không."""
        try:
            r = self.session.get(f"{self.base_url}/v2/profiles", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def get_profiles(self, group_filter: Optional[str] = None) -> List[Dict]:
        """
        Lấy danh sách toàn bộ profile từ GPM-Login.
        Hỗ trợ lọc theo tên nhóm (group_name).
        """
        try:
            r = self.session.get(f"{self.base_url}/v2/profiles", timeout=5)
            if r.status_code == 200:
                data = r.json()
                profiles = data if isinstance(data, list) else data.get("data", [])
                if group_filter:
                    profiles = [p for p in profiles if p.get("group_name", "").lower() == group_filter.lower()]
                return profiles
            return []
        except Exception as e:
            print(f"[GpmAPI Error] Khong the lay danh sach profile: {e}")
            return []

    def start_profile(self, profile_id: str, max_retries: int = 3) -> Dict:
        """
        Khởi động 1 profile GPM-Login qua API.
        Trả về dictionary chứa: success, remote_debug_address, process_id...
        """
        url = f"{self.base_url}/v2/start"
        params = {"profile_id": profile_id}
        for attempt in range(1, max_retries + 1):
            try:
                print(f"[GpmAPI] Dang khoi dong Profile ID: {profile_id} (Lan thu {attempt})...")
                r = self.session.get(url, params=params, timeout=25)
                if r.status_code == 200:
                    res = r.json()
                    # Cấu trúc trả về chuẩn của GPM v2
                    if res.get("success") is True or res.get("status") == "success":
                        print(f"[GpmAPI] Khoi dong Profile {profile_id} thanh cong!")
                        return res
                    elif "data" in res and res["data"]:
                        print(f"[GpmAPI] Khoi dong Profile {profile_id} thanh cong!")
                        return res
                time.sleep(2)
            except Exception as e:
                print(f"[GpmAPI Warning] Khoi dong that bai lan {attempt}: {e}")
                time.sleep(2)
        return {"success": False, "message": "Timeout hoac loi ket noi GPM API"}

    def stop_profile(self, profile_id: str) -> bool:
        """Đóng profile một cách sạch sẽ và giải phóng tài nguyên."""
        url = f"{self.base_url}/v2/stop"
        params = {"profile_id": profile_id}
        try:
            print(f"[GpmAPI] Dang dong Profile ID: {profile_id}...")
            r = self.session.get(url, params=params, timeout=10)
            return r.status_code == 200
        except Exception as e:
            print(f"[GpmAPI Error] Khong the dong profile {profile_id}: {e}")
            return False


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Test He thong 2A: Ket noi GPM-Login API ---")
    gpm = GpmAPI()
    is_alive = gpm.check_connection()
    print(f"Trang thai ket noi GPM-Login: {'Ket noi tot' if is_alive else 'Khong ket noi duoc'}")
    if is_alive:
        profiles = gpm.get_profiles()
        print(f"Phat hien {len(profiles)} profile trong he thong GPM-Login.")
        if profiles:
            first = profiles[0]
            print(f"Vi du Profile dau tien: ID='{first.get('id')}', Name='{first.get('name')}', Group='{first.get('group_name')}'")

"""
HỆ THỐNG 2A: GIAO TIẾP GPM-LOGIN LOCAL API (GPM API CONNECTOR)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Kết nối trực tiếp GPM-Login v2/v3 theo chuẩn tài liệu chính thức GPM Login.
"""

import os
import sys
import time
import json
from typing import List, Dict, Optional, Any
import requests

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class GpmAPI:
    """
    Quản lý kết nối và điều phối Profile GPM-Login qua Local REST API theo tài liệu chuẩn.
    Hỗ trợ đầy đủ: Start, Stop, Create, Update, Update-Proxy, Update-Note, Profiles, Delete,
    và điều khiển trình duyệt qua Chrome DevTools Protocol (CDP).
    """

    DEFAULT_PORT = 19995

    def __init__(self, api_base_url: str = "http://127.0.0.1:19995"):
        self.base_url = api_base_url.rstrip("/")
        self.session = requests.Session()

    @classmethod
    def auto_detect_api_url(cls) -> str:
        """Tự động tìm kiếm API URL từ file cấu hình của GPM Login trên Windows."""
        candidate_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\GPMLogin\api_port.dat"),
            r"C:\Users\ADMIN\AppData\Local\Programs\GPMLogin\api_port.dat",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\GPMLogin\local_port.dat"),
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        raw = f.read().strip()
                        if raw.isdigit():
                            return f"http://127.0.0.1:{raw}"
                        elif raw.startswith("{"):
                            data = json.loads(raw)
                            port = data.get("http_port")
                            if port:
                                return f"http://127.0.0.1:{port}"
                except Exception:
                    pass
        return f"http://127.0.0.1:{cls.DEFAULT_PORT}"

    def check_connection(self) -> bool:
        """Kiểm tra GPM-Login có đang bật trên máy không."""
        try:
            r = self.session.get(f"{self.base_url}/v2/profiles", timeout=3)
            return r.status_code == 200
        except Exception:
            # Thử tự động phát hiện cổng nếu cổng hiện tại không phản hồi
            detected = self.auto_detect_api_url()
            if detected != self.base_url:
                try:
                    r = self.session.get(f"{detected}/v2/profiles", timeout=3)
                    if r.status_code == 200:
                        self.base_url = detected
                        return True
                except Exception:
                    pass
            return False

    def get_profiles(self, page: int = 1, per_page: int = 10000, group_filter: Optional[str] = None, search: Optional[str] = None) -> List[Dict]:
        """
        Lấy danh sách profiles từ GPM-Login theo tài liệu /v2/profiles.
        Hỗ trợ lọc theo group, tìm kiếm theo tên hoặc proxy.
        """
        try:
            params = {}
            if page > 1:
                params["page"] = page
            if per_page != 10000:
                params["per_page"] = per_page

            r = self.session.get(f"{self.base_url}/v2/profiles", params=params, timeout=6)
            if r.status_code == 200:
                data = r.json()
                profiles = data if isinstance(data, list) else data.get("data", [])
                if group_filter:
                    profiles = [p for p in profiles if str(p.get("group_name", "")).lower() == group_filter.lower()]
                if search:
                    q = search.lower()
                    profiles = [p for p in profiles if q in str(p.get("name", "")).lower() or q in str(p.get("proxy", "")).lower() or q in str(p.get("id", "")).lower()]
                return profiles
            return []
        except Exception as e:
            print(f"[GpmAPI Error] Khong the lay danh sach profile: {e}")
            return []

    def start_profile(
        self,
        profile_id: str,
        remote_debugging_port: Optional[int] = None,
        window_size: Optional[str] = None,
        window_pos: Optional[str] = None,
        window_scale: Optional[float] = None,
        skip_proxy_check: Optional[bool] = None,
        addition_args: Optional[str] = None,
        max_retries: int = 2
    ) -> Dict:
        """
        Khởi động 1 profile GPM-Login qua API /v2/start.
        Trả về dictionary chuẩn hóa chứa:
        - success: bool
        - status: bool
        - profile_id: str
        - selenium_remote_debug_address: str (ví dụ "127.0.0.1:60007")
        - remote_debug_port: int
        - process_id: int (nếu dò được)
        - browser_location: str
        - selenium_driver_location: str
        """
        url = f"{self.base_url}/v2/start"
        params = {"profile_id": profile_id}
        if remote_debugging_port:
            params["remote_debug_port"] = str(remote_debugging_port)
            params["remote_debugging_port"] = str(remote_debugging_port)

        args = []
        args.append("--remote-allow-origins=*")
        if addition_args:
            args.append(addition_args)
        if window_size:
            args.append(f"--window-size={window_size.replace('x', ',')}")
        if window_pos:
            args.append(f"--window-position={window_pos.replace('x', ',')}")
        if window_scale is not None:
            args.append(f"--force-device-scale-factor={window_scale}")

        combined_args = " ".join(args)
        params["addination_args"] = combined_args  # Docs GPM dùng addination_args
        params["addition_args"] = combined_args

        if window_size:
            params["window_size"] = str(window_size)
        if window_pos:
            params["window_pos"] = str(window_pos)
        if window_scale is not None:
            params["window_scale"] = str(window_scale)
        if skip_proxy_check is not None:
            params["skip_proxy_check"] = "true" if skip_proxy_check else "false"

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[GpmAPI] Đang khởi động Profile ID: {profile_id} (Lần {attempt})...")
                r = self.session.get(url, params=params, timeout=25)
                if r.status_code == 200:
                    res = r.json()
                    is_ok = bool(res.get("status") is True or res.get("success") is True or res.get("selenium_remote_debug_address"))
                    res["success"] = is_ok
                    debug_addr = res.get("selenium_remote_debug_address") or res.get("data", {}).get("remote_debugging_address")
                    if debug_addr:
                        res["selenium_remote_debug_address"] = debug_addr
                        try:
                            port = int(debug_addr.split(":")[-1])
                            res["remote_debug_port"] = port
                            proc_id = self.find_pid_by_port(port)
                            if proc_id:
                                res["process_id"] = proc_id
                        except Exception:
                            pass
                    return res
                time.sleep(1.5)
            except Exception as e:
                print(f"[GpmAPI Warning] Khởi động thất bại lần {attempt}: {e}")
                time.sleep(1.5)
        return {"success": False, "status": False, "message": "Timeout hoặc lỗi kết nối GPM API"}

    def stop_profile(self, profile_id: str) -> bool:
        """Đóng profile qua API /v2/stop theo tài liệu GPM."""
        url = f"{self.base_url}/v2/stop"
        params = {"profile_id": profile_id}
        try:
            print(f"[GpmAPI] Đang đóng Profile ID: {profile_id}...")
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return True
            return False
        except Exception as e:
            print(f"[GpmAPI Error] Không thể đóng profile {profile_id}: {e}")
            return False

    def find_profile_by_name(self, profile_name: str, exact_match: bool = False) -> Optional[Dict]:
        """
        Tìm Profile theo tên hiển thị (tránh việc phải nhớ hoặc tìm thủ công Profile ID).
        - exact_match = True: Khớp tuyệt đối tên.
        - exact_match = False: Khớp tương đối (case-insensitive substring).
        """
        profiles = self.get_profiles()
        target = profile_name.strip().lower()
        if exact_match:
            for p in profiles:
                if str(p.get("name", "")).strip().lower() == target:
                    return p
        else:
            # Ưu tiên khớp chính xác trước
            for p in profiles:
                if str(p.get("name", "")).strip().lower() == target:
                    return p
            # Khớp một phần
            for p in profiles:
                if target in str(p.get("name", "")).strip().lower():
                    return p
        return None

    def start_profile_by_name(self, profile_name: str, exact_match: bool = False, **kwargs) -> Dict:
        """
        Tự động ánh xạ Tên Profile -> Profile ID và khởi động Profile.
        Giúp giải quyết triệt để vấn đề: Tên Profile khác với Profile ID.
        """
        prof = self.find_profile_by_name(profile_name, exact_match=exact_match)
        if not prof:
            return {"success": False, "status": False, "message": f"Không tìm thấy profile có tên: '{profile_name}'"}
        
        pid = prof.get("id")
        print(f"[GpmAPI] Đã ánh xạ Tên '{prof.get('name')}' -> Profile ID: {pid}")
        res = self.start_profile(profile_id=pid, **kwargs)
        res["matched_profile"] = prof
        return res

    def stop_profile_by_name(self, profile_name: str, exact_match: bool = False) -> bool:
        """Tự động ánh xạ Tên Profile -> Profile ID và đóng Profile."""
        prof = self.find_profile_by_name(profile_name, exact_match=exact_match)
        if not prof:
            print(f"[GpmAPI Error] Không tìm thấy profile có tên: '{profile_name}'")
            return False
        pid = prof.get("id")
        return self.stop_profile(profile_id=pid)

    def create_profile(
        self,
        name: str,
        group: str = "All",
        proxy: str = "",
        canvas: str = "off",
        font: str = "on",
        webrtc: str = "on",
        user_agent: Optional[str] = None,
        save_type: str = "local"
    ) -> Dict:
        """
        Tạo profile mới theo tài liệu /v2/create:
        - name: Bắt buộc
        - proxy: IP:Port hoặc socks5://...
        - group: Nhóm (mặc định All)
        - canvas: on/off
        - font: on/off
        - webrtc: on/off
        - user_agent: UA tùy chỉnh hoặc rỗng
        - save_type: local hoặc s3
        """
        url = f"{self.base_url}/v2/create"
        params = {
            "name": name,
            "group": group,
            "proxy": proxy,
            "canvas": canvas,
            "font": font,
            "webrtc": webrtc,
            "save_type": save_type
        }
        if user_agent:
            params["user_agent"] = user_agent
        try:
            r = self.session.get(url, params=params, timeout=15)
            if r.status_code == 200:
                res = r.json()
                res["success"] = bool(res.get("status") is True or res.get("profile_id"))
                return res
            return {"success": False, "error": f"HTTP {r.status_code}: {r.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_profile(
        self,
        profile_id: str,
        name: Optional[str] = None,
        proxy: Optional[str] = None,
        note: Optional[str] = None
    ) -> bool:
        """Cập nhật thông tin profile theo tài liệu /v2/update."""
        url = f"{self.base_url}/v2/update"
        params = {"id": profile_id}
        if name is not None:
            params["name"] = name
        if proxy is not None:
            params["proxy"] = proxy
        if note is not None:
            params["note"] = note
        try:
            r = self.session.get(url, params=params, timeout=10)
            return r.status_code == 200 and "true" in r.text.lower()
        except Exception as e:
            print(f"[GpmAPI Error] Không thể update profile: {e}")
            return False

    def update_proxy(self, profile_id: str, proxy: str) -> bool:
        """Cập nhật proxy riêng cho profile theo tài liệu /v2/update-proxy."""
        url = f"{self.base_url}/v2/update-proxy"
        params = {"id": profile_id, "proxy": proxy}
        try:
            r = self.session.get(url, params=params, timeout=10)
            return r.status_code == 200 and "true" in r.text.lower()
        except Exception as e:
            print(f"[GpmAPI Error] Không thể update proxy: {e}")
            return False

    def update_note(self, profile_id: str, note: str) -> bool:
        """Cập nhật ghi chú riêng cho profile theo tài liệu /v2/update-note."""
        url = f"{self.base_url}/v2/update-note"
        params = {"id": profile_id, "note": note}
        try:
            r = self.session.get(url, params=params, timeout=10)
            return r.status_code == 200 and "true" in r.text.lower()
        except Exception as e:
            print(f"[GpmAPI Error] Không thể update note: {e}")
            return False

    def delete_profile(self, profile_id: str, mode: int = 2) -> bool:
        """
        Xóa profile theo tài liệu /v2/delete:
        - mode: 1 (Chỉ xóa trên app), 2 (Xóa cả thư mục profile)
        """
        url = f"{self.base_url}/v2/delete"
        params = {"profile_id": profile_id, "mode": mode}
        try:
            r = self.session.get(url, params=params, timeout=10)
            return r.status_code == 200 and "ok" in r.text.lower()
        except Exception as e:
            print(f"[GpmAPI Error] Không thể xóa profile: {e}")
            return False

    # ==========================================
    # CÁC TÍNH NĂNG ĐIỀU KHIỂN CHROME DEVTOOLS PROTOCOL (CDP)
    # ==========================================

    def get_cdp_version(self, debug_address: str) -> Dict:
        """Lấy thông tin browser version từ debug address (ví dụ '127.0.0.1:60007')."""
        try:
            r = requests.get(f"http://{debug_address}/json/version", timeout=3)
            return r.json() if r.status_code == 200 else {}
        except Exception:
            return {}

    def get_cdp_tabs(self, debug_address: str) -> List[Dict]:
        """Lấy danh sách các tabs/pages đang mở trong browser."""
        try:
            r = requests.get(f"http://{debug_address}/json/list", timeout=3)
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []

    def open_cdp_tab(self, debug_address: str, url: str = "about:blank") -> Dict:
        """Mở tab mới trong browser."""
        try:
            r = requests.get(f"http://{debug_address}/json/new?{url}", timeout=4)
            return r.json() if r.status_code == 200 else {}
        except Exception:
            return {}

    def close_cdp_tab(self, debug_address: str, target_id: str) -> bool:
        """Đóng tab theo target ID."""
        try:
            r = requests.get(f"http://{debug_address}/json/close/{target_id}", timeout=4)
            return r.status_code == 200
        except Exception:
            return False

    def cdp_send_command(self, ws_url: str, method: str, params: Optional[Dict] = None, timeout: float = 6.0) -> Dict:
        """Gửi lệnh Chrome DevTools Protocol trực tiếp qua WebSocket."""
        try:
            import websocket
            ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
            msg_id = int(time.time() * 1000) % 1000000
            payload = {"id": msg_id, "method": method, "params": params or {}}
            ws.send(json.dumps(payload))

            start_t = time.time()
            while time.time() - start_t < timeout:
                raw = ws.recv()
                data = json.loads(raw)
                if data.get("id") == msg_id:
                    ws.close()
                    return data
            ws.close()
            return {"error": "Timeout waiting for CDP response"}
        except Exception as e:
            return {"error": str(e)}

    def cdp_evaluate(self, debug_address: str, script: str) -> Dict:
        """Thực thi mã JavaScript trên tab đang active."""
        tabs = self.get_cdp_tabs(debug_address)
        page_tabs = [t for t in tabs if t.get("type") == "page"]
        if not page_tabs:
            return {"success": False, "error": "Không tìm thấy tab trang web hợp lệ"}
        ws_url = page_tabs[0].get("webSocketDebuggerUrl")
        if not ws_url:
            return {"success": False, "error": "Không có WebSocket URL cho tab"}

        res = self.cdp_send_command(ws_url, "Runtime.evaluate", {
            "expression": script,
            "returnByValue": True,
            "awaitPromise": True
        })
        if "result" in res and "result" in res["result"]:
            val = res["result"]["result"].get("value")
            return {"success": True, "value": val, "raw": res["result"]["result"]}
        elif "error" in res:
            return {"success": False, "error": res["error"]}
        return {"success": False, "error": "Unknown error in CDP execution", "raw": res}

    def cdp_navigate(self, debug_address: str, url: str) -> Dict:
        """Điều hướng tab active tới một URL bất kỳ."""
        tabs = self.get_cdp_tabs(debug_address)
        page_tabs = [t for t in tabs if t.get("type") == "page"]
        if not page_tabs:
            return {"success": False, "error": "Không tìm thấy tab trang web"}
        ws_url = page_tabs[0].get("webSocketDebuggerUrl")
        if not ws_url:
            return {"success": False, "error": "Không có WebSocket URL"}
        res = self.cdp_send_command(ws_url, "Page.navigate", {"url": url})
        return {"success": "result" in res, "response": res}

    def cdp_capture_screenshot(self, debug_address: str, quality: int = 70) -> Dict:
        """Chụp ảnh màn hình trực tiếp từ lõi trình duyệt Chromium qua CDP."""
        tabs = self.get_cdp_tabs(debug_address)
        page_tabs = [t for t in tabs if t.get("type") == "page"]
        if not page_tabs:
            return {"success": False, "error": "Không tìm thấy tab trang web"}
        ws_url = page_tabs[0].get("webSocketDebuggerUrl")
        if not ws_url:
            return {"success": False, "error": "Không có WebSocket URL"}

        res = self.cdp_send_command(ws_url, "Page.captureScreenshot", {
            "format": "jpeg",
            "quality": quality
        }, timeout=8.0)

        if "result" in res and "data" in res["result"]:
            return {
                "success": True,
                "image_b64": f"data:image/jpeg;base64,{res['result']['data']}",
                "tab_title": page_tabs[0].get("title", ""),
                "tab_url": page_tabs[0].get("url", "")
            }
        return {"success": False, "error": res.get("error") or "Không thể chụp ảnh màn hình"}

    # ==========================================
    # TIỆN ÍCH HỆ THỐNG WINDOWS
    # ==========================================

    @staticmethod
    def find_pid_by_port(port: int) -> Optional[int]:
        """Tìm Process ID của trình duyệt đang lắng nghe trên cổng debug port."""
        if not port:
            return None
        try:
            import psutil
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr and conn.laddr.port == port and conn.status == "LISTEN":
                    return conn.pid
        except Exception:
            pass
        return None

    @staticmethod
    def force_kill_process(process_id: int) -> bool:
        """Cưỡng chế đóng tiến trình Chrome/Chromium bằng lệnh taskkill trên Windows."""
        if not process_id:
            return False
        try:
            ret = os.system(f"taskkill /F /PID {int(process_id)} >nul 2>&1")
            return ret == 0
        except Exception:
            return False

    @staticmethod
    def is_process_alive(process_id: int) -> bool:
        """Kiểm tra xem process ID có đang thực sự chạy trên Windows không."""
        if not process_id:
            return False
        import subprocess
        try:
            out = subprocess.check_output(f'tasklist /FI "PID eq {int(process_id)}"', shell=True, text=True)
            return str(process_id) in out
        except Exception:
            return False

    def raw_request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Dict:
        """Thực thi request tùy biến đến GPM Local API phục vụ kiểm thử tương tác theo chuẩn docs."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        start_t = time.time()
        try:
            if method.upper() == "POST":
                resp = self.session.post(url, params=params, json=json_data, timeout=15)
            else:
                resp = self.session.get(url, params=params, timeout=15)
            latency = round((time.time() - start_t) * 1000, 1)
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            return {
                "success": resp.status_code in (200, 201),
                "status_code": resp.status_code,
                "latency_ms": latency,
                "data": body,
                "url": resp.url
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": 0,
                "latency_ms": round((time.time() - start_t) * 1000, 1),
                "error": str(e),
                "url": url
            }

    def run_automated_diagnostic(self) -> Dict[str, Any]:
        """
        Quy trình kiểm thử tự động toàn diện (Automation Diagnostic Test):
        1. Kiểm tra kết nối Local API (/v2/profiles)
        2. Tạo profile tạm thời (__DIAGNOSTIC_TEST__)
        3. Cập nhật note cho profile tạm
        4. Khởi động profile tạm (/v2/start)
        5. Kết nối CDP kiểm tra WebSocket & JS evaluation
        6. Chụp ảnh màn hình CDP Page.captureScreenshot
        7. Đóng profile tạm (/v2/stop)
        8. Xóa profile tạm sạch sẽ (/v2/delete)
        Trả về kết quả chi tiết từng bước phục vụ báo cáo UI.
        """
        results = []
        overall_success = True
        test_pid = None
        debug_addr = None

        # Bước 1: Check Connection
        t0 = time.time()
        connected = self.check_connection()
        lat1 = round((time.time() - t0) * 1000, 1)
        results.append({
            "step": 1,
            "name": "Kiểm tra kết nối GPM-Login Local API",
            "endpoint": "GET /v2/profiles",
            "success": connected,
            "latency_ms": lat1,
            "details": f"Base URL: {self.base_url}"
        })
        if not connected:
            return {"overall_success": False, "steps": results}

        # Bước 2: Create Test Profile
        t0 = time.time()
        c_res = self.create_profile(name="__DIAGNOSTIC_TEST__", group="TestBench")
        lat2 = round((time.time() - t0) * 1000, 1)
        test_pid = c_res.get("profile_id")
        step2_ok = bool(test_pid)
        results.append({
            "step": 2,
            "name": "Tạo Profile kiểm thử tạm thời",
            "endpoint": "GET /v2/create",
            "success": step2_ok,
            "latency_ms": lat2,
            "details": f"Created Profile ID: {test_pid}" if step2_ok else f"Lỗi: {c_res}"
        })
        if not step2_ok:
            return {"overall_success": False, "steps": results}

        try:
            # Bước 3: Update Note
            t0 = time.time()
            u_ok = self.update_note(test_pid, f"Diagnostic Test at {time.strftime('%H:%M:%S')}")
            lat3 = round((time.time() - t0) * 1000, 1)
            results.append({
                "step": 3,
                "name": "Cập nhật ghi chú (Update Note)",
                "endpoint": "GET /v2/update-note",
                "success": u_ok,
                "latency_ms": lat3,
                "details": f"Note updated: {u_ok}"
            })

            # Bước 4: Start Profile
            t0 = time.time()
            s_res = self.start_profile(test_pid)
            lat4 = round((time.time() - t0) * 1000, 1)
            debug_addr = s_res.get("selenium_remote_debug_address")
            step4_ok = bool(s_res.get("success") and debug_addr)
            results.append({
                "step": 4,
                "name": "Khởi động Browser Profile",
                "endpoint": "GET /v2/start",
                "success": step4_ok,
                "latency_ms": lat4,
                "details": f"Debug Address: {debug_addr}" if step4_ok else f"Lỗi: {s_res}"
            })

            if step4_ok:
                time.sleep(1.5)
                # Bước 5: CDP JS Evaluation
                t0 = time.time()
                eval_res = self.cdp_evaluate(debug_addr, "navigator.userAgent")
                lat5 = round((time.time() - t0) * 1000, 1)
                step5_ok = eval_res.get("success") is True
                results.append({
                    "step": 5,
                    "name": "Giao tiếp Chrome DevTools (CDP Evaluate)",
                    "endpoint": "WebSocket Runtime.evaluate",
                    "success": step5_ok,
                    "latency_ms": lat5,
                    "details": f"UserAgent: {str(eval_res.get('value'))[:50]}..." if step5_ok else f"Lỗi: {eval_res.get('error')}"
                })

                # Bước 6: CDP Screenshot
                t0 = time.time()
                shot_res = self.cdp_capture_screenshot(debug_addr, quality=40)
                lat6 = round((time.time() - t0) * 1000, 1)
                step6_ok = shot_res.get("success") is True
                results.append({
                    "step": 6,
                    "name": "Chụp ảnh màn hình từ Browser Core (CDP Screenshot)",
                    "endpoint": "WebSocket Page.captureScreenshot",
                    "success": step6_ok,
                    "latency_ms": lat6,
                    "details": "Chụp ảnh thành công qua CDP stream" if step6_ok else f"Lỗi: {shot_res.get('error')}"
                })

            # Bước 7: Stop Profile
            t0 = time.time()
            stop_ok = self.stop_profile(test_pid)
            lat7 = round((time.time() - t0) * 1000, 1)
            results.append({
                "step": 7,
                "name": "Đóng Browser Profile",
                "endpoint": "GET /v2/stop",
                "success": stop_ok,
                "latency_ms": lat7,
                "details": f"Closed cleanly: {stop_ok}"
            })
            time.sleep(1)

        finally:
            # Bước 8: Clean up delete
            if test_pid:
                t0 = time.time()
                del_ok = self.delete_profile(test_pid, mode=2)
                lat8 = round((time.time() - t0) * 1000, 1)
                results.append({
                    "step": 8,
                    "name": "Dọn dẹp xóa Profile kiểm thử",
                    "endpoint": "GET /v2/delete",
                    "success": del_ok,
                    "latency_ms": lat8,
                    "details": f"Cleaned up profile {test_pid}: {del_ok}"
                })

        overall_success = all(s.get("success") for s in results)
        return {
            "overall_success": overall_success,
            "steps": results,
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("=== KIỂM THỬ GPM-LOGIN API V2 CONNECTOR ===")
    gpm = GpmAPI()
    diag = gpm.run_automated_diagnostic()
    print(f"Tổng kết kiểm định: {'THÀNH CÔNG RỰC RỠ 100%' if diag['overall_success'] else 'CÓ BƯỚC THẤT BẠI'}")
    for step in diag["steps"]:
        status_mark = "✔" if step["success"] else "✖"
        print(f"[{status_mark}] Bước {step['step']}: {step['name']} ({step['latency_ms']}ms) -> {step['details']}")

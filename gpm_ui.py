"""
GPM-LOGIN CONTROLLER & TESTING UI
Tác giả: SFL Desktop Automation Suite
Mô tả: Web UI trực quan, hiện đại điều khiển và kiểm thử toàn diện các chức năng của GPM-Login theo tài liệu API chuẩn.
Khởi chạy: python gpm_ui.py -> Tự động mở trình duyệt tại http://127.0.0.1:18888
"""

import base64
import datetime
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from typing import Dict, Any, Optional

# Thêm đường dẫn thư viện gốc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.gpm_api import GpmAPI
from core.window_helper import WindowHelper

# Quản lý trạng thái phiên chạy của các profile
active_profiles_tracker: Dict[str, Dict[str, Any]] = {}
audit_logs = []


def add_audit_log(action: str, profile_id: str, status: str, details: Any = None):
    entry = {
        "id": len(audit_logs) + 1,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "profile_id": profile_id,
        "status": status,
        "details": details or {}
    }
    audit_logs.insert(0, entry)
    if len(audit_logs) > 100:
        audit_logs.pop()


# Khởi tạo GpmAPI client mặc định
gpm_client = GpmAPI(api_base_url="http://127.0.0.1:19995")


class GpmUIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_content: str):
        body = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send_html(HTML_TEMPLATE)
            return

        if path == "/api/status":
            is_alive = gpm_client.check_connection()
            start_t = time.time()
            latency = 0.0
            if is_alive:
                try:
                    r = gpm_client.session.get(f"{gpm_client.base_url}/v2/profiles", timeout=2)
                    latency = round((time.time() - start_t) * 1000, 1)
                except Exception:
                    latency = -1
            self._send_json({
                "connected": is_alive,
                "base_url": gpm_client.base_url,
                "latency_ms": latency,
                "active_count": len([p for p, data in active_profiles_tracker.items() if data.get("running")]),
                "total_profiles_tracked": len(active_profiles_tracker)
            })
            return

        if path == "/api/profiles":
            group_filter = query.get("group", [None])[0]
            profiles = gpm_client.get_profiles(group_filter=group_filter)

            # Cập nhật thông tin trạng thái hoạt động thực tế
            for p in profiles:
                pid = p.get("id")
                if pid in active_profiles_tracker:
                    tracker = active_profiles_tracker[pid]
                    proc_id = tracker.get("process_id")
                    if proc_id and not GpmAPI.is_process_alive(proc_id):
                        tracker["running"] = False
                    p["running_info"] = tracker
                else:
                    p["running_info"] = {"running": False}

            groups = sorted(list(set(p.get("group_name", "") for p in profiles if p.get("group_name"))))
            self._send_json({
                "success": True,
                "total": len(profiles),
                "groups": groups,
                "profiles": profiles
            })
            return

        if path == "/api/logs":
            self._send_json({"logs": audit_logs})
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except Exception:
            req_data = {}

        if path == "/api/config":
            new_base = req_data.get("base_url")
            if new_base:
                gpm_client.base_url = new_base.rstrip("/")
                add_audit_log("CONFIG_UPDATE", "SYSTEM", "SUCCESS", {"new_base_url": gpm_client.base_url})
            self._send_json({"success": True, "base_url": gpm_client.base_url})
            return

        if path == "/api/start":
            pid = req_data.get("profile_id")
            if not pid:
                self._send_json({"success": False, "error": "Missing profile_id"}, 400)
                return

            res = gpm_client.start_profile(
                profile_id=pid,
                remote_debugging_port=req_data.get("remote_debugging_port"),
                window_size=req_data.get("window_size"),
                window_pos=req_data.get("window_pos"),
                window_scale=req_data.get("window_scale"),
                skip_proxy_check=req_data.get("skip_proxy_check"),
                addition_args=req_data.get("addition_args")
            )

            is_ok = res.get("success") is True or "data" in res
            data = res.get("data") if isinstance(res.get("data"), dict) else {}
            add_info = data.get("addition_info") or {}

            proc_id = add_info.get("process_id") or data.get("process_id")
            remote_port = data.get("remote_debugging_port")
            ws_url = data.get("websocket_debugging_url")
            hwnd = add_info.get("window_handle")

            active_profiles_tracker[pid] = {
                "running": is_ok,
                "started_at": datetime.datetime.now().strftime("%H:%M:%S"),
                "process_id": proc_id,
                "remote_debugging_port": remote_port,
                "websocket_debugging_url": ws_url,
                "window_handle": hwnd,
                "raw_response": res
            }

            add_audit_log("START_PROFILE", pid, "SUCCESS" if is_ok else "FAILED", res)
            self._send_json({
                "success": is_ok,
                "response": res,
                "tracker": active_profiles_tracker[pid]
            })
            return

        if path == "/api/stop":
            pid = req_data.get("profile_id")
            if not pid:
                self._send_json({"success": False, "error": "Missing profile_id"}, 400)
                return

            ok = gpm_client.stop_profile(pid)
            if pid in active_profiles_tracker:
                active_profiles_tracker[pid]["running"] = False

            add_audit_log("STOP_PROFILE", pid, "SUCCESS" if ok else "FAILED")
            self._send_json({"success": ok, "profile_id": pid})
            return

        if path == "/api/force_kill":
            pid = req_data.get("profile_id")
            proc_id = req_data.get("process_id")
            if not proc_id and pid in active_profiles_tracker:
                proc_id = active_profiles_tracker[pid].get("process_id")

            if not proc_id:
                self._send_json({"success": False, "error": "Không tìm thấy Process ID để cưỡng chế đóng"}, 400)
                return

            ok = GpmAPI.force_kill_process(int(proc_id))
            if pid and pid in active_profiles_tracker:
                active_profiles_tracker[pid]["running"] = False

            add_audit_log("FORCE_KILL", pid or str(proc_id), "SUCCESS" if ok else "FAILED", {"pid": proc_id})
            self._send_json({"success": ok, "process_id": proc_id})
            return

        if path == "/api/stop_all":
            stopped = []
            for pid, info in list(active_profiles_tracker.items()):
                if info.get("running"):
                    gpm_client.stop_profile(pid)
                    info["running"] = False
                    stopped.append(pid)
            add_audit_log("STOP_ALL", "ALL", "SUCCESS", {"stopped_count": len(stopped)})
            self._send_json({"success": True, "stopped_profiles": stopped})
            return

        if path == "/api/focus_window":
            profile_name = req_data.get("profile_name", "")
            hwnd = req_data.get("hwnd")
            found_hwnd = None
            if hwnd:
                found_hwnd = int(hwnd)
            elif profile_name:
                found_hwnd = WindowHelper.find_game_window(preferred_title=profile_name)

            if found_hwnd:
                ok = WindowHelper.bring_to_foreground(found_hwnd)
                rect = WindowHelper.get_window_rect(found_hwnd)
                client_rect = WindowHelper.get_client_rect_on_screen(found_hwnd)
                self._send_json({
                    "success": ok,
                    "hwnd": found_hwnd,
                    "window_rect": rect,
                    "client_rect": client_rect
                })
            else:
                self._send_json({"success": False, "error": f"Không tìm thấy cửa sổ cho profile '{profile_name}'"})
            return

        if path == "/api/screenshot":
            profile_name = req_data.get("profile_name", "")
            hwnd = req_data.get("hwnd")
            found_hwnd = None
            if hwnd:
                found_hwnd = int(hwnd)
            elif profile_name:
                found_hwnd = WindowHelper.find_game_window(preferred_title=profile_name)

            region = None
            if found_hwnd:
                cx, cy, cw, ch = WindowHelper.get_client_rect_on_screen(found_hwnd)
                if cw > 50 and ch > 50:
                    region = (cx, cy, cw, ch)

            try:
                from PIL import ImageGrab
                if region:
                    bbox = (region[0], region[1], region[0] + region[2], region[1] + region[3])
                    img = ImageGrab.grab(bbox=bbox, all_screens=True)
                else:
                    img = ImageGrab.grab(all_screens=True)

                buf = BytesIO()
                img.save(buf, format="JPEG", quality=80)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                self._send_json({
                    "success": True,
                    "image_b64": f"data:image/jpeg;base64,{b64}",
                    "width": img.width,
                    "height": img.height,
                    "hwnd": found_hwnd,
                    "region": region
                })
            except Exception as e:
                self._send_json({"success": False, "error": f"Lỗi chụp màn hình: {e}"})
            return

        if path == "/api/raw_request":
            method = req_data.get("method", "GET")
            endpoint = req_data.get("endpoint", "/v2/profiles")
            params = req_data.get("params")
            json_payload = req_data.get("json_data")
            res = gpm_client.raw_request(method, endpoint, params=params, json_data=json_payload)
            add_audit_log("RAW_API_TEST", endpoint, "SUCCESS" if res.get("success") else "FAILED", res)
            self._send_json(res)
            return

        self.send_error(404, "Endpoint not found")

    def log_message(self, format, *args):
        # Ẩn bớt log http request mặc định để terminal sạch
        return


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GPM-Login Controller & Test Center</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-main: #090d16;
      --bg-surface: #0f1626;
      --bg-card: #141c30;
      --bg-glass: rgba(20, 28, 48, 0.75);
      --border: rgba(255, 255, 255, 0.08);
      --border-focus: rgba(0, 229, 255, 0.4);
      --primary: #00e5ff;
      --primary-glow: rgba(0, 229, 255, 0.25);
      --emerald: #10b981;
      --emerald-glow: rgba(16, 185, 129, 0.2);
      --amber: #f59e0b;
      --amber-glow: rgba(245, 158, 11, 0.2);
      --crimson: #ef4444;
      --crimson-glow: rgba(239, 68, 68, 0.25);
      --purple: #8b5cf6;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --radius: 12px;
      --radius-sm: 8px;
      --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.4);
      --transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-main);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(0, 229, 255, 0.05) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.05) 0%, transparent 40%);
    }

    /* Top Navigation Bar */
    header {
      background: var(--bg-glass);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 50;
      padding: 0.85rem 2rem;
    }

    .nav-container {
      max-width: 1540px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1.5rem;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.85rem;
    }

    .brand-icon {
      width: 42px;
      height: 42px;
      background: linear-gradient(135deg, #00e5ff 0%, #3b82f6 100%);
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 20px var(--primary-glow);
    }

    .brand-icon svg { width: 24px; height: 24px; fill: #090d16; }

    .brand-text h1 {
      font-size: 1.15rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #ffffff 40%, var(--primary) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .brand-text p {
      font-size: 0.72rem;
      color: var(--text-dim);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    /* Connection pill */
    .connection-panel {
      display: flex;
      align-items: center;
      background: var(--bg-surface);
      border: 1px solid var(--border);
      padding: 0.35rem 0.6rem;
      border-radius: var(--radius-sm);
      gap: 0.75rem;
    }

    .status-pill {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.8rem;
      font-weight: 600;
      padding: 0.25rem 0.65rem;
      border-radius: 20px;
      background: rgba(16, 185, 129, 0.1);
      color: var(--emerald);
      border: 1px solid rgba(16, 185, 129, 0.2);
    }

    .status-pill.offline {
      background: rgba(239, 68, 68, 0.1);
      color: var(--crimson);
      border-color: rgba(239, 68, 68, 0.2);
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: currentColor;
      box-shadow: 0 0 10px currentColor;
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.5; transform: scale(0.85); }
    }

    .api-endpoint-input {
      background: transparent;
      border: none;
      color: var(--text);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      outline: none;
      width: 195px;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      padding: 0.5rem 0.95rem;
      font-size: 0.82rem;
      font-weight: 600;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border);
      cursor: pointer;
      background: var(--bg-card);
      color: var(--text);
      transition: var(--transition);
      font-family: inherit;
    }

    .btn:hover {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(255, 255, 255, 0.2);
      transform: translateY(-1px);
    }

    .btn-primary {
      background: linear-gradient(135deg, #00e5ff 0%, #0099ff 100%);
      color: #080d16;
      border: none;
      box-shadow: 0 4px 15px var(--primary-glow);
    }
    .btn-primary:hover {
      background: linear-gradient(135deg, #33ebff 0%, #1aa3ff 100%);
      box-shadow: 0 6px 20px var(--primary-glow);
      color: #080d16;
    }

    .btn-danger {
      background: rgba(239, 68, 68, 0.12);
      color: var(--crimson);
      border-color: rgba(239, 68, 68, 0.25);
    }
    .btn-danger:hover {
      background: var(--crimson);
      color: white;
      box-shadow: 0 4px 15px var(--crimson-glow);
    }

    .btn-success {
      background: rgba(16, 185, 129, 0.12);
      color: var(--emerald);
      border-color: rgba(16, 185, 129, 0.25);
    }
    .btn-success:hover {
      background: var(--emerald);
      color: #080d16;
      box-shadow: 0 4px 15px var(--emerald-glow);
    }

    .btn-sm { padding: 0.35rem 0.65rem; font-size: 0.75rem; }

    /* Main Container */
    main {
      max-width: 1540px;
      margin: 1.5rem auto;
      padding: 0 2rem;
      width: 100%;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    /* Metrics Strip */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
    }

    .metric-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.15rem 1.4rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }

    .metric-card::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 4px;
      height: 100%;
      background: var(--primary);
    }

    .metric-card.emerald::after { background: var(--emerald); }
    .metric-card.amber::after { background: var(--amber); }
    .metric-card.purple::after { background: var(--purple); }

    .metric-info p {
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .metric-info h3 {
      font-size: 1.75rem;
      font-weight: 800;
      margin-top: 0.3rem;
      letter-spacing: -0.02em;
    }

    .metric-icon {
      width: 46px;
      height: 46px;
      border-radius: var(--radius-sm);
      background: rgba(255, 255, 255, 0.04);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--primary);
    }
    .metric-card.emerald .metric-icon { color: var(--emerald); }
    .metric-card.amber .metric-icon { color: var(--amber); }
    .metric-card.purple .metric-icon { color: var(--purple); }

    /* Control Toolbar */
    .toolbar {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1rem 1.25rem;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      box-shadow: var(--shadow);
    }

    .filter-group {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      flex-wrap: wrap;
    }

    .search-input-wrapper {
      position: relative;
      width: 280px;
    }

    .search-input-wrapper svg {
      position: absolute;
      left: 0.85rem;
      top: 50%;
      transform: translateY(-50%);
      width: 16px;
      height: 16px;
      fill: var(--text-dim);
    }

    .search-input {
      width: 100%;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 0.5rem 0.85rem 0.5rem 2.4rem;
      color: var(--text);
      font-size: 0.85rem;
      outline: none;
      transition: var(--transition);
      font-family: inherit;
    }

    .search-input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 15px var(--primary-glow);
    }

    .chip {
      padding: 0.38rem 0.8rem;
      border-radius: 20px;
      font-size: 0.78rem;
      font-weight: 600;
      border: 1px solid var(--border);
      background: var(--bg-card);
      color: var(--text-muted);
      cursor: pointer;
      transition: var(--transition);
    }

    .chip.active, .chip:hover {
      background: rgba(0, 229, 255, 0.12);
      color: var(--primary);
      border-color: rgba(0, 229, 255, 0.3);
    }

    .action-group {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }

    /* Profiles Grid View */
    .profiles-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 1.25rem;
    }

    .profile-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
      transition: var(--transition);
      position: relative;
      box-shadow: var(--shadow);
    }

    .profile-card:hover {
      border-color: rgba(0, 229, 255, 0.3);
      transform: translateY(-2px);
      box-shadow: 0 15px 30px -10px rgba(0, 229, 255, 0.12);
    }

    .profile-card.is-running {
      border-color: rgba(16, 185, 129, 0.5);
      background: linear-gradient(180deg, rgba(16, 185, 129, 0.04) 0%, var(--bg-card) 100%);
    }

    .card-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 0.75rem;
    }

    .profile-title {
      font-size: 1.05rem;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      word-break: break-all;
    }

    .group-badge {
      font-size: 0.7rem;
      font-weight: 700;
      padding: 0.2rem 0.55rem;
      border-radius: 4px;
      background: rgba(139, 92, 246, 0.15);
      color: #c4b5fd;
      border: 1px solid rgba(139, 92, 246, 0.3);
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }

    .state-indicator {
      display: flex;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.74rem;
      font-weight: 700;
      padding: 0.25rem 0.55rem;
      border-radius: 20px;
    }

    .state-indicator.stopped {
      background: rgba(100, 116, 139, 0.15);
      color: var(--text-dim);
      border: 1px solid rgba(100, 116, 139, 0.2);
    }

    .state-indicator.running {
      background: rgba(16, 185, 129, 0.15);
      color: var(--emerald);
      border: 1px solid rgba(16, 185, 129, 0.3);
      box-shadow: 0 0 10px var(--emerald-glow);
    }

    .card-body {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      font-size: 0.8rem;
    }

    .meta-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: var(--text-muted);
      border-bottom: 1px dashed rgba(255, 255, 255, 0.05);
      padding-bottom: 0.4rem;
    }

    .meta-row:last-child { border-bottom: none; }

    .meta-val {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.76rem;
      color: var(--text);
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .running-banner {
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.25);
      border-radius: var(--radius-sm);
      padding: 0.6rem 0.75rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.4rem;
    }

    .card-actions {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-top: auto;
      padding-top: 0.5rem;
      border-top: 1px solid var(--border);
    }

    .card-actions .btn { flex: 1; }

    /* Modals */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 100;
      opacity: 0;
      pointer-events: none;
      transition: var(--transition);
      padding: 1.5rem;
    }

    .modal-overlay.active {
      opacity: 1;
      pointer-events: auto;
    }

    .modal-card {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      width: 100%;
      max-width: 650px;
      max-height: 90vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.75);
      overflow: hidden;
      transform: scale(0.95);
      transition: var(--transition);
    }

    .modal-overlay.active .modal-card {
      transform: scale(1);
    }

    .modal-head {
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .modal-head h3 {
      font-size: 1.15rem;
      font-weight: 700;
    }

    .modal-close {
      background: transparent;
      border: none;
      color: var(--text-dim);
      font-size: 1.5rem;
      cursor: pointer;
      line-height: 1;
    }
    .modal-close:hover { color: #fff; }

    .modal-body {
      padding: 1.5rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1.15rem;
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }

    .form-group label {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
    }

    .form-control {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 0.6rem 0.85rem;
      color: var(--text);
      font-size: 0.85rem;
      outline: none;
      font-family: inherit;
    }
    .form-control:focus {
      border-color: var(--primary);
    }

    .modal-foot {
      padding: 1rem 1.5rem;
      border-top: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 0.75rem;
      background: rgba(0, 0, 0, 0.15);
    }

    /* Logs & Audit Drawer */
    .drawer {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .drawer-head {
      padding: 0.9rem 1.25rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .drawer-head h4 { font-size: 0.95rem; font-weight: 700; }

    .log-stream {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      max-height: 240px;
      overflow-y: auto;
      padding: 0.75rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      background: #080c14;
    }

    .log-item {
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      line-height: 1.4;
      border-bottom: 1px solid rgba(255, 255, 255, 0.03);
      padding-bottom: 0.25rem;
    }

    .log-time { color: var(--text-dim); }
    .log-action { color: var(--primary); font-weight: 600; min-width: 130px; }
    .log-status { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; }
    .log-status.SUCCESS { background: rgba(16, 185, 129, 0.2); color: var(--emerald); }
    .log-status.FAILED { background: rgba(239, 68, 68, 0.2); color: var(--crimson); }
    .log-details { color: var(--text-muted); word-break: break-all; flex: 1; }

    /* Toast Notification */
    #toast-container {
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      z-index: 999;
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
    }

    .toast {
      background: var(--bg-card);
      border: 1px solid var(--border);
      padding: 0.85rem 1.25rem;
      border-radius: var(--radius-sm);
      font-size: 0.85rem;
      font-weight: 600;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      gap: 0.6rem;
      animation: slideIn 0.25s ease-out;
    }

    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }

    .toast.success { border-color: var(--emerald); color: var(--emerald); }
    .toast.error { border-color: var(--crimson); color: var(--crimson); }
    .toast.info { border-color: var(--primary); color: var(--primary); }
  </style>
</head>
<body>

  <!-- Top Navigation -->
  <header>
    <div class="nav-container">
      <div class="brand">
        <div class="brand-icon">
          <svg viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path></svg>
        </div>
        <div class="brand-text">
          <h1>GPM-LOGIN CONTROLLER</h1>
          <p>Sunflower Land RPA Desktop Gateway</p>
        </div>
      </div>

      <!-- Connection Pill & Switcher -->
      <div class="connection-panel">
        <div id="conn-status" class="status-pill">
          <span class="status-dot"></span>
          <span id="conn-text">Đang kết nối...</span>
        </div>
        <input type="text" id="gpm-base-url" class="api-endpoint-input" value="http://127.0.0.1:19995" title="Nhấn Enter để đổi địa chỉ API">
        <button class="btn btn-sm" id="btn-save-endpoint" onclick="changeEndpoint()">Lưu Port</button>
      </div>

      <!-- Global Actions -->
      <div class="action-group">
        <button class="btn btn-sm" id="btn-refresh-all" onclick="loadProfiles()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
          Làm mới
        </button>
        <button class="btn btn-sm" id="btn-api-playground" onclick="openPlaygroundModal()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path></svg>
          API Playground
        </button>
        <button class="btn btn-danger btn-sm" id="btn-stop-all" onclick="stopAllProfiles()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg>
          Đóng tất cả
        </button>
      </div>
    </div>
  </header>

  <!-- Main Content Area -->
  <main>
    <!-- Metrics Row -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-info">
          <p>Tổng Profiles GPM</p>
          <h3 id="stat-total">0</h3>
        </div>
        <div class="metric-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
        </div>
      </div>

      <div class="metric-card emerald">
        <div class="metric-info">
          <p>Đang Chạy (Active)</p>
          <h3 id="stat-running">0</h3>
        </div>
        <div class="metric-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polygon points="10 8 16 12 10 16 10 8"></polygon></svg>
        </div>
      </div>

      <div class="metric-card amber">
        <div class="metric-info">
          <p>Độ Trễ API (Latency)</p>
          <h3 id="stat-latency">-- ms</h3>
        </div>
        <div class="metric-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
        </div>
      </div>

      <div class="metric-card purple">
        <div class="metric-info">
          <p>Nhóm Profile (Groups)</p>
          <h3 id="stat-groups">0</h3>
        </div>
        <div class="metric-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
        </div>
      </div>
    </div>

    <!-- Toolbar Filters -->
    <div class="toolbar">
      <div class="filter-group">
        <div class="search-input-wrapper">
          <svg viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
          <input type="text" id="search-input" class="search-input" placeholder="Tìm theo tên, ID, proxy..." oninput="filterProfiles()">
        </div>
        <div id="group-chips" class="filter-group">
          <span class="chip active" onclick="selectGroup(null, this)">Tất cả</span>
        </div>
      </div>

      <div class="filter-group">
        <span style="font-size: 0.8rem; color: var(--text-muted);" id="filtered-count-label">Hiển thị 0/0 profiles</span>
      </div>
    </div>

    <!-- Profiles Cards Grid -->
    <div id="profiles-container" class="profiles-grid">
      <!-- Profiles injected here by Javascript -->
    </div>

    <!-- Live Event Audit Drawer -->
    <div class="drawer">
      <div class="drawer-head">
        <h4>NHẬT KÝ LỆNH ĐIỀU KHIỂN & API AUDIT TRAIL</h4>
        <button class="btn btn-sm" onclick="clearLogs()">Xóa lịch sử</button>
      </div>
      <div id="log-stream" class="log-stream">
        <!-- Log entries -->
      </div>
    </div>
  </main>

  <!-- Start Profile Modal (Options from GPM Docs) -->
  <div id="start-modal" class="modal-overlay">
    <div class="modal-card">
      <div class="modal-head">
        <h3 id="modal-profile-title">Khởi Động Profile GPM</h3>
        <button class="modal-close" onclick="closeModal('start-modal')">&times;</button>
      </div>
      <div class="modal-body">
        <input type="hidden" id="modal-profile-id">

        <div class="form-group">
          <label>URL Đích (Trang cần mở):</label>
          <input type="text" id="opt-url" class="form-control" value="https://sunflower-land.com/play/">
          <div style="display:flex; gap:0.4rem; margin-top:0.3rem;">
            <button class="btn btn-sm" onclick="document.getElementById('opt-url').value='https://sunflower-land.com/play/'">Sunflower Land</button>
            <button class="btn btn-sm" onclick="document.getElementById('opt-url').value='https://whoer.net'">Kiểm tra IP (Whoer)</button>
            <button class="btn btn-sm" onclick="document.getElementById('opt-url').value='about:blank'">Trang trống</button>
          </div>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.85rem;">
          <div class="form-group">
            <label>Kích thước cửa sổ (window_size):</label>
            <input type="text" id="opt-size" class="form-control" value="1280,720" placeholder="1280,720">
          </div>
          <div class="form-group">
            <label>Vị trí cửa sổ (window_pos):</label>
            <input type="text" id="opt-pos" class="form-control" placeholder="100,100 (tùy chọn)">
          </div>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.85rem;">
          <div class="form-group">
            <label>Tỷ lệ thu phóng (window_scale):</label>
            <select id="opt-scale" class="form-control">
              <option value="1.0" selected>1.0 (Chuẩn 100%)</option>
              <option value="0.8">0.8 (Thu nhỏ 80%)</option>
              <option value="0.75">0.75 (Thu nhỏ 75%)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Cổng Debug tùy biến (remote_port):</label>
            <input type="number" id="opt-port" class="form-control" placeholder="Tự động nếu để trống">
          </div>
        </div>

        <div class="form-group">
          <label>Tham số Chromium bổ sung (addition_args):</label>
          <input type="text" id="opt-args" class="form-control" value="--mute-audio --no-first-run">
        </div>

        <div class="form-group" style="flex-direction: row; align-items: center; gap: 0.6rem;">
          <input type="checkbox" id="opt-skip-proxy" style="width: 18px; height: 18px;">
          <label for="opt-skip-proxy" style="cursor: pointer;">Bỏ qua bước test proxy trước khi mở (skip_proxy_check)</label>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn" onclick="closeModal('start-modal')">Hủy</button>
        <button class="btn btn-primary" id="btn-submit-start" onclick="executeStartProfile()">🚀 Khởi Động Ngay</button>
      </div>
    </div>
  </div>

  <!-- Screenshot Preview Modal -->
  <div id="screenshot-modal" class="modal-overlay">
    <div class="modal-card" style="max-width: 900px;">
      <div class="modal-head">
        <h3 id="screenshot-title">Ảnh Chụp Cửa Sổ Game Profile</h3>
        <button class="modal-close" onclick="closeModal('screenshot-modal')">&times;</button>
      </div>
      <div class="modal-body" style="align-items: center; justify-content: center; background: #000; padding: 1rem;">
        <img id="screenshot-img" src="" alt="Screenshot" style="max-width: 100%; max-height: 550px; border-radius: 6px; border: 1px solid var(--border);">
      </div>
      <div class="modal-foot">
        <span id="screenshot-meta" style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: var(--text-dim); margin-right: auto;"></span>
        <button class="btn" onclick="closeModal('screenshot-modal')">Đóng</button>
      </div>
    </div>
  </div>

  <!-- API Playground Modal -->
  <div id="playground-modal" class="modal-overlay">
    <div class="modal-card" style="max-width: 800px;">
      <div class="modal-head">
        <h3>GPM API Interactive Playground (Docs Compliance)</h3>
        <button class="modal-close" onclick="closeModal('playground-modal')">&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label>Cài đặt sẵn (Presets):</label>
          <div style="display:flex; flex-wrap:wrap; gap:0.4rem;">
            <button class="btn btn-sm" onclick="setPreset('GET', '/v2/profiles')">GET /v2/profiles</button>
            <button class="btn btn-sm" onclick="setPreset('GET', '/api/v1/profiles')">GET /api/v1/profiles</button>
            <button class="btn btn-sm" onclick="setPreset('GET', '/v2/start', {'profile_id': currentFirstPid})">GET /v2/start</button>
            <button class="btn btn-sm" onclick="setPreset('GET', '/v2/stop', {'profile_id': currentFirstPid})">GET /v2/stop</button>
          </div>
        </div>

        <div style="display:grid; grid-template-columns: 120px 1fr; gap:0.6rem;">
          <select id="pg-method" class="form-control">
            <option value="GET">GET</option>
            <option value="POST">POST</option>
          </select>
          <input type="text" id="pg-endpoint" class="form-control" value="/v2/profiles">
        </div>

        <div class="form-group">
          <label>Tham số (Query Params dạng JSON hoặc để trống):</label>
          <input type="text" id="pg-params" class="form-control" placeholder='{"profile_id": "uuid-here"}'>
        </div>

        <button class="btn btn-primary" onclick="executePlaygroundRequest()">Gửi Request Thử Nghiệm</button>

        <div class="form-group">
          <label>Kết quả phản hồi (Response):</label>
          <pre id="pg-response" style="background:#080c14; padding:0.85rem; border-radius:var(--radius-sm); border:1px solid var(--border); font-family:'JetBrains Mono', monospace; font-size:0.75rem; max-height:260px; overflow-y:auto; color:#a7f3d0;">Chưa gửi request</pre>
        </div>
      </div>
    </div>
  </div>

  <div id="toast-container"></div>

  <script>
    let allProfiles = [];
    let currentGroupFilter = null;
    let currentFirstPid = "";

    // Toast utility
    function showToast(msg, type = "info") {
      const c = document.getElementById("toast-container");
      const t = document.createElement("div");
      t.className = `toast ${type}`;
      t.innerText = msg;
      c.appendChild(t);
      setTimeout(() => t.remove(), 4000);
    }

    // Modal helpers
    function openModal(id) { document.getElementById(id).classList.add("active"); }
    function closeModal(id) { document.getElementById(id).classList.remove("active"); }

    // Đổi base endpoint API
    async function changeEndpoint() {
      const url = document.getElementById("gpm-base-url").value.trim();
      const res = await fetch("/api/config", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({base_url: url})
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Đã đổi endpoint GPM sang: ${data.base_url}`, "success");
        loadStatus();
        loadProfiles();
      }
    }

    // Tải trạng thái kết nối
    async function loadStatus() {
      try {
        const res = await fetch("/api/status");
        const data = await res.json();
        const pill = document.getElementById("conn-status");
        const txt = document.getElementById("conn-text");
        const lat = document.getElementById("stat-latency");
        const runningEl = document.getElementById("stat-running");

        if (data.connected) {
          pill.className = "status-pill";
          txt.innerText = `Đã kết nối (${data.latency_ms}ms)`;
          lat.innerText = `${data.latency_ms} ms`;
        } else {
          pill.className = "status-pill offline";
          txt.innerText = "Mất kết nối GPM";
          lat.innerText = "Timeout";
        }
        runningEl.innerText = data.active_count;
      } catch (e) {
        document.getElementById("conn-status").className = "status-pill offline";
        document.getElementById("conn-text").innerText = "Server UI Offline";
      }
    }

    // Tải danh sách profiles
    async function loadProfiles() {
      try {
        let url = "/api/profiles";
        if (currentGroupFilter) url += `?group=${encodeURIComponent(currentGroupFilter)}`;
        const res = await fetch(url);
        const data = await res.json();
        if (data.success) {
          allProfiles = data.profiles;
          document.getElementById("stat-total").innerText = data.total;
          document.getElementById("stat-groups").innerText = data.groups.length;
          if (allProfiles.length > 0) currentFirstPid = allProfiles[0].id;
          renderGroups(data.groups);
          filterProfiles();
        }
      } catch (e) {
        showToast("Không thể tải danh sách profiles", "error");
      }
    }

    // Render nhóm filter chips
    function renderGroups(groups) {
      const c = document.getElementById("group-chips");
      c.innerHTML = `<span class="chip ${currentGroupFilter === null ? 'active' : ''}" onclick="selectGroup(null, this)">Tất cả</span>`;
      groups.forEach(g => {
        const span = document.createElement("span");
        span.className = `chip ${currentGroupFilter === g ? 'active' : ''}`;
        span.innerText = g;
        span.onclick = () => selectGroup(g, span);
        c.appendChild(span);
      });
    }

    function selectGroup(group, el) {
      currentGroupFilter = group;
      document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      if (el) el.classList.add("active");
      filterProfiles();
    }

    // Lọc và render Profile Cards
    function filterProfiles() {
      const q = document.getElementById("search-input").value.toLowerCase();
      const container = document.getElementById("profiles-container");
      container.innerHTML = "";

      const filtered = allProfiles.filter(p => {
        const matchGroup = !currentGroupFilter || (p.group_name && p.group_name.toLowerCase() === currentGroupFilter.toLowerCase());
        const matchText = (p.name && p.name.toLowerCase().includes(q)) ||
                          (p.id && p.id.toLowerCase().includes(q)) ||
                          (p.proxy && p.proxy.toLowerCase().includes(q));
        return matchGroup && matchText;
      });

      document.getElementById("filtered-count-label").innerText = `Hiển thị ${filtered.length}/${allProfiles.length} profiles`;

      if (filtered.length === 0) {
        container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-dim);">Không tìm thấy profile phù hợp</div>`;
        return;
      }

      filtered.forEach(p => {
        const isRun = p.running_info && p.running_info.running;
        const card = document.createElement("div");
        card.className = `profile-card ${isRun ? 'is-running' : ''}`;

        let runningHtml = "";
        if (isRun) {
          const runInfo = p.running_info;
          runningHtml = `
            <div class="running-banner">
              <div>PID: <b>${runInfo.process_id || 'N/A'}</b></div>
              <div>Port: <b>${runInfo.remote_debugging_port || 'N/A'}</b></div>
              <div>HWND: <b>${runInfo.window_handle || 'N/A'}</b></div>
              <div>Mở lúc: <b>${runInfo.started_at || '--'}</b></div>
            </div>
          `;
        }

        card.innerHTML = `
          <div class="card-head">
            <div style="flex: 1;">
              <div class="profile-title">
                ${escapeHtml(p.name || 'Profile không tên')}
              </div>
              <span class="group-badge">${escapeHtml(p.group_name || 'Mặc định')}</span>
            </div>
            <div class="state-indicator ${isRun ? 'running' : 'stopped'}">
              <span class="status-dot"></span>
              ${isRun ? 'ĐANG CHẠY' : 'ĐÃ TẮT'}
            </div>
          </div>

          <div class="card-body">
            <div class="meta-row">
              <span>Profile ID:</span>
              <span class="meta-val" title="${p.id}">${p.id}</span>
            </div>
            <div class="meta-row">
              <span>Proxy:</span>
              <span class="meta-val" title="${p.proxy || 'Trực tiếp (Direct)'}">
                ${p.proxy ? escapeHtml(p.proxy) : 'Direct (Không proxy)'}
              </span>
            </div>
            <div class="meta-row">
              <span>Trình duyệt:</span>
              <span class="meta-val">${p.browser_type || 'Chrome'}</span>
            </div>
            ${runningHtml}
          </div>

          <div class="card-actions">
            ${isRun ? `
              <button class="btn btn-danger btn-sm" onclick="stopProfile('${p.id}')">⏹️ Đóng</button>
              <button class="btn btn-sm" onclick="focusWindow('${escapeJs(p.name)}', ${p.running_info.window_handle || 'null'})">🔍 Focus</button>
              <button class="btn btn-sm" onclick="takeScreenshot('${escapeJs(p.name)}', ${p.running_info.window_handle || 'null'})">📸 Chụp ảnh</button>
              <button class="btn btn-danger btn-sm" onclick="forceKill('${p.id}', ${p.running_info.process_id || 'null'})" title="Force Kill PID">💀 Kill</button>
            ` : `
              <button class="btn btn-success btn-sm" onclick="quickStart('${p.id}')">🚀 Chạy nhanh</button>
              <button class="btn btn-sm" onclick="openStartModal('${p.id}', '${escapeJs(p.name)}')">⚙️ Tùy chọn</button>
            `}
          </div>
        `;
        container.appendChild(card);
      });
    }

    // Bắt đầu nhanh (Quick Start)
    async function quickStart(pid) {
      showToast(`Đang khởi động profile ${pid}...`, "info");
      try {
        const res = await fetch("/api/start", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            profile_id: pid,
            addition_args: "https://sunflower-land.com/play/ --mute-audio",
            window_size: "1280,720"
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Khởi động thành công Profile ${pid}!`, "success");
        } else {
          showToast(`Khởi động thất bại: ${JSON.stringify(data.response || data.error)}`, "error");
        }
        loadProfiles();
        loadLogs();
      } catch (e) {
        showToast(`Lỗi gửi yêu cầu: ${e}`, "error");
      }
    }

    // Modal khởi động nâng cao
    function openStartModal(pid, name) {
      document.getElementById("modal-profile-id").value = pid;
      document.getElementById("modal-profile-title").innerText = `Khởi động: ${name} (${pid.substring(0,8)}...)`;
      openModal("start-modal");
    }

    async function executeStartProfile() {
      const pid = document.getElementById("modal-profile-id").value;
      const targetUrl = document.getElementById("opt-url").value.trim();
      const size = document.getElementById("opt-size").value.trim();
      const pos = document.getElementById("opt-pos").value.trim();
      const scale = parseFloat(document.getElementById("opt-scale").value);
      const port = document.getElementById("opt-port").value.trim();
      let args = document.getElementById("opt-args").value.trim();
      const skipProxy = document.getElementById("opt-skip-proxy").checked;

      if (targetUrl) {
        args = `${targetUrl} ${args}`;
      }

      closeModal("start-modal");
      showToast("Đang phát lệnh khởi động...", "info");

      try {
        const res = await fetch("/api/start", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            profile_id: pid,
            window_size: size || null,
            window_pos: pos || null,
            window_scale: scale || null,
            remote_debugging_port: port ? parseInt(port) : null,
            addition_args: args || null,
            skip_proxy_check: skipProxy
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast("Khởi động thành công!", "success");
        } else {
          showToast(`Lỗi: ${data.response?.message || 'Không thể mở profile'}`, "error");
        }
        loadProfiles();
        loadLogs();
      } catch (e) {
        showToast(`Lỗi kết nối: ${e}`, "error");
      }
    }

    // Đóng profile
    async function stopProfile(pid) {
      showToast(`Đang đóng profile ${pid}...`, "info");
      try {
        const res = await fetch("/api/stop", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({profile_id: pid})
        });
        const data = await res.json();
        if (data.success) {
          showToast("Đã đóng profile an toàn!", "success");
        } else {
          showToast("Đóng profile thất bại!", "error");
        }
        loadProfiles();
        loadLogs();
      } catch (e) {
        showToast(`Lỗi: ${e}`, "error");
      }
    }

    // Force Kill Process
    async function forceKill(pid, procId) {
      if (!confirm(`Bạn có chắc chắn muốn Force Kill tiến trình (PID: ${procId})?`)) return;
      try {
        const res = await fetch("/api/force_kill", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({profile_id: pid, process_id: procId})
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Đã tiêu diệt Process PID ${procId}!`, "success");
        } else {
          showToast(`Không thể kill: ${data.error}`, "error");
        }
        loadProfiles();
        loadLogs();
      } catch (e) {
        showToast(`Lỗi: ${e}`, "error");
      }
    }

    // Đóng tất cả
    async function stopAllProfiles() {
      if (!confirm("Bạn có chắc chắn muốn đóng TOÀN BỘ các profile đang chạy?")) return;
      try {
        const res = await fetch("/api/stop_all", {method: "POST"});
        const data = await res.json();
        showToast(`Đã đóng ${data.stopped_profiles.length} profiles!`, "success");
        loadProfiles();
        loadLogs();
      } catch (e) {
        showToast(`Lỗi: ${e}`, "error");
      }
    }

    // Focus Window
    async function focusWindow(name, hwnd) {
      try {
        const res = await fetch("/api/focus_window", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({profile_name: name, hwnd: hwnd})
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Đã focus cửa sổ HWND ${data.hwnd}!`, "success");
        } else {
          showToast(data.error || "Không thể focus", "error");
        }
      } catch (e) {
        showToast(`Lỗi: ${e}`, "error");
      }
    }

    // Chụp màn hình
    async function takeScreenshot(name, hwnd) {
      showToast("Đang chụp màn hình cửa sổ...", "info");
      try {
        const res = await fetch("/api/screenshot", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({profile_name: name, hwnd: hwnd})
        });
        const data = await res.json();
        if (data.success) {
          document.getElementById("screenshot-img").src = data.image_b64;
          document.getElementById("screenshot-title").innerText = `Ảnh chụp: ${name} (HWND: ${data.hwnd || 'All'})`;
          document.getElementById("screenshot-meta").innerText = `Kích thước: ${data.width}x${data.height} | Region: ${JSON.stringify(data.region)}`;
          openModal("screenshot-modal");
        } else {
          showToast(data.error || "Chụp màn hình thất bại", "error");
        }
      } catch (e) {
        showToast(`Lỗi chụp: ${e}`, "error");
      }
    }

    // Logs
    async function loadLogs() {
      try {
        const res = await fetch("/api/logs");
        const data = await res.json();
        const c = document.getElementById("log-stream");
        c.innerHTML = "";
        data.logs.forEach(l => {
          const div = document.createElement("div");
          div.className = "log-item";
          div.innerHTML = `
            <span class="log-time">[${l.timestamp}]</span>
            <span class="log-action">${escapeHtml(l.action)}</span>
            <span class="log-status ${l.status}">${l.status}</span>
            <span class="log-details">${escapeHtml(JSON.stringify(l.details))}</span>
          `;
          c.appendChild(div);
        });
      } catch (e) {}
    }

    function clearLogs() {
      document.getElementById("log-stream").innerHTML = "<div style='color:var(--text-dim);'>Nhật ký đã xóa</div>";
    }

    // API Playground
    function openPlaygroundModal() {
      openModal("playground-modal");
    }

    function setPreset(method, endpoint, params = null) {
      document.getElementById("pg-method").value = method;
      document.getElementById("pg-endpoint").value = endpoint;
      document.getElementById("pg-params").value = params ? JSON.stringify(params) : "";
    }

    async function executePlaygroundRequest() {
      const method = document.getElementById("pg-method").value;
      const endpoint = document.getElementById("pg-endpoint").value.trim();
      let params = null;
      try {
        const pText = document.getElementById("pg-params").value.trim();
        if (pText) params = JSON.parse(pText);
      } catch (e) {
        showToast("JSON params không đúng định dạng", "error");
        return;
      }

      document.getElementById("pg-response").innerText = "Đang gửi request...";

      try {
        const res = await fetch("/api/raw_request", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({method, endpoint, params})
        });
        const data = await res.json();
        document.getElementById("pg-response").innerText = JSON.stringify(data, null, 2);
        loadLogs();
      } catch (e) {
        document.getElementById("pg-response").innerText = `Lỗi: ${e}`;
      }
    }

    function escapeHtml(str) {
      if (!str) return "";
      return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    function escapeJs(str) {
      if (!str) return "";
      return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
    }

    // Vòng lặp cập nhật tự động mỗi 3 giây
    window.addEventListener("DOMContentLoaded", () => {
      loadStatus();
      loadProfiles();
      loadLogs();
      setInterval(() => {
        loadStatus();
        loadLogs();
      }, 3000);
    });
  </script>
</body>
</html>
"""


def start_server(port: int = 18888):
    server_address = ("127.0.0.1", port)
    try:
        httpd = HTTPServer(server_address, GpmUIHandler)
    except OSError:
        # Nếu port 18888 bận, tự nhảy sang port 18889
        port = 18889
        server_address = ("127.0.0.1", port)
        httpd = HTTPServer(server_address, GpmUIHandler)

    print("\n" + "=" * 70)
    print(" 🚀 GPM-LOGIN CONTROL & TEST CENTER ĐÃ KHỞI CHẠY THÀNH CÔNG!")
    print(f" -> Địa chỉ Web UI: http://127.0.0.1:{port}")
    print(" -> Đang mở trình duyệt tự động để bạn thao tác...")
    print(" -> Nhấn Ctrl + C trong cửa sổ này để tắt giao diện.")
    print("=" * 70 + "\n")

    # Mở trình duyệt sau 0.8 giây
    threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[GpmUI] Đang dừng server GPM UI...")
        httpd.server_close()
        print("[GpmUI] Đã tắt sạch sẽ.")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    start_server(18888)

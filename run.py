"""
HỆ THỐNG TRUNG TÂM: ĐIỀU PHỐI TỰ ĐỘNG HÓA TỔNG THỂ (MASTER RUNNER)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Chạy tuần tự qua GPM-Login + Chuột phần cứng Win32 + AI Vision Claude Haiku
"""

import datetime
import json
import os
import random
import sys
import time
from typing import Optional, Dict, List, Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.gpm_api import GpmAPI
from core.human_mouse import HumanMouse
from core.window_helper import WindowHelper
from core.ai_vision import AIVision
from core.local_vision_engine import LocalVisionEngine
from tasks.captcha_guard import CaptchaGuard
from tasks.crop_manager import CropManager
from tasks.mushroom_hunter import MushroomHunter
from tasks.farm_maintenance import FarmMaintenance
from tasks.session_task_orchestrator import SessionTaskOrchestrator
from scheduler.farm_memory import FarmMemory
from scheduler.queue_manager import QueueManager
from scheduler.crop_selector import SmartCropSelector


class MasterRunner:
    """
    Bộ điều phối trung tâm kết nối toàn bộ 4 hệ thống thành một chu trình khép kín.
    """

    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)

        # 1. Khởi tạo các module
        gpm_cfg = self.config.get("gpm_api", {})
        self.gpm = GpmAPI(api_base_url=gpm_cfg.get("base_url", "http://127.0.0.1:19995"))
        self.group_filter = gpm_cfg.get("group_filter")

        ai_cfg = self.config.get("ai_vision", {})
        self.ai_enabled = ai_cfg.get("enabled", False)
        api_key = os.environ.get("AI_VISION_API_KEY") or os.environ.get("BEEKNOEE_API_KEY") or ai_cfg.get("api_key", "")
        self.ai = AIVision(
            api_key=api_key,
            base_url=ai_cfg.get("base_url", "https://api.openai.com/v1"),
            model_id=ai_cfg.get("model_id", "bee-tok/claude-haiku-5-5")
        )

        self.memory = FarmMemory(ai_client=self.ai if self.ai_enabled else None)
        sched_cfg = self.config.get("scheduler", {})
        self.scheduler = QueueManager(
            farm_memory=self.memory,
            sleep_start_hour=sched_cfg.get("sleep_start_hour", 1),
            sleep_end_hour=sched_cfg.get("sleep_end_hour", 6),
            inter_profile_delay=(
                sched_cfg.get("inter_profile_delay_min", 25),
                sched_cfg.get("inter_profile_delay_max", 50)
            ),
            break_every_n_profiles=sched_cfg.get("coffee_break_every_n_profiles", 5)
        )

        farm_cfg = self.config.get("farming", {})
        self.crop_mgr = CropManager(
            farm_memory=self.memory,
            sync_delay=(
                farm_cfg.get("action_sync_delay_min", 0.45),
                farm_cfg.get("action_sync_delay_max", 0.85)
            )
        )
        self.default_crop = farm_cfg.get("default_crop", "Sunflower")
        self.default_grow_sec = farm_cfg.get("default_grow_seconds", 60)
        self.seed_box_coord = tuple(farm_cfg.get("seed_box_coord", [400, 560]))
        self.plot_coords = [tuple(p) for p in farm_cfg.get("plot_coords", [
            [310, 270], [350, 270], [390, 270],
            [310, 310], [350, 310], [390, 310],
            [310, 350], [350, 350], [390, 350]
        ])]
        self.tree_coords = [tuple(p) for p in farm_cfg.get("tree_coords", [
            [220, 210], [260, 190], [520, 220]
        ])]
        self.beehive_coords = [tuple(p) for p in farm_cfg.get("beehive_coords", [
            [180, 360], [210, 360]
        ])]
        self.composter_coord = tuple(farm_cfg.get("composter_coord", [480, 420]))

        # Tái lập thực nghiệm (Reproducibility Seed)
        repro_cfg = self.config.get("reproducibility", {})
        seed_val = repro_cfg.get("seed")
        if seed_val is not None:
            random.seed(seed_val)
            print(f"[MasterRunner] Đã thiết lập seed ngẫu nhiên cố định: {seed_val}")
        self.audit_logging = repro_cfg.get("audit_logging", True)

    @staticmethod
    def _load_config(path: str) -> dict:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _record_audit_log(
        self,
        profile_id: str,
        profile_name: str,
        session_plan: dict,
        status: str,
        verification: dict,
        eff_params: dict,
        execution_status: Optional[str] = None,
        verification_status: Optional[str] = None,
        cleanup_error: Optional[str] = None
    ):
        """Ghi nhận nhật ký kiểm toán phiên (Structured Audit Trail) phục vụ đánh giá định lượng."""
        if not getattr(self, "audit_logging", True):
            return
        log_file = "audit_trail.jsonl"
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "profile_id": profile_id,
            "profile_name": profile_name,
            "session_type": session_plan.get("session_type", "UNKNOWN"),
            "status": status,
            "execution_status": execution_status or status,
            "verification_status": verification_status or verification.get("status", "UNVERIFIED"),
            "cleanup_error": cleanup_error,
            "tasks_planned": session_plan.get("tasks_to_execute", []),
            "verification": verification,
            "intra_day_metrics": {
                "vigilance": eff_params.get("vigilance_level") if isinstance(eff_params, dict) else None,
                "accumulated_fatigue": eff_params.get("accumulated_fatigue") if isinstance(eff_params, dict) else None,
                "effective_fumble_rate": eff_params.get("effective_fumble_rate") if isinstance(eff_params, dict) else None
            }
        }
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Audit Log Warning] Không thể ghi audit trail: {e}")

    def run_session_on_profile(self, profile: dict):
        """Thực thi một phiên chơi hoàn chỉnh trên 1 profile GPM dưới danh nghĩa một CON NGƯỜI SỐNG ĐỘNG ĐỜI THỰC."""
        pid = profile.get("id")
        pname = profile.get("name")
        persona = self.memory.persona_mgr.get_or_create_persona(pid, pname)
        ident = persona.get("human_identity", {})
        scenario = self.memory.scenario_engine.get_or_generate_scenario(pid, pname, ident)
        fatigue_mult = self.memory.scenario_engine.get_fatigue_multiplier()

        # Tính toán tham số hiệu dụng tức thời từ Trạng thái làm việc nội ngày (Concordia 2024 / Park 2023)
        eff_params = self.memory.scenario_engine.get_effective_behavioral_params(pid, pname)
        scenario.update(eff_params)
        speed_mult = persona["mouse_speed_factor"] * eff_params["effective_speed_multiplier"] * fatigue_mult
        scenario["speed_mult"] = speed_mult
        scenario["miss_click_prob"] = eff_params["effective_miss_click_prob"]
        scenario["fumble_rate"] = eff_params["effective_fumble_rate"]
        scenario["distraction_prob"] = eff_params["effective_distraction_prob"]
        scenario["distract_rate"] = eff_params["effective_distract_rate"]

        cur_sessions = self.memory.data.get(pid, {}).get("session_count_today", 0)
        cap = scenario.get("daily_session_cap", 6)
        now = datetime.datetime.now()
        cur_hour = now.hour + now.minute / 60.0

        # Quyết định Kế hoạch Đa nhiệm và Xác suất bỏ sót công việc trong phiên này
        session_plan = SessionTaskOrchestrator.determine_session_plan(
            scenario=scenario,
            persona=persona,
            current_hour=cur_hour,
            session_index_today=cur_sessions + 1
        )

        session_status = "INITIALIZING"
        verification = {"status": "unverified", "harvest_verified": None, "plant_verified": None}

        print("\n" + "=" * 75)
        print(f" [PHIÊN CHƠI SỐNG ĐỘNG] {scenario['real_name']} ({scenario['age']} tuổi - {scenario['job']})")
        print(f" -> Tên Profile GPM: '{pname}' | Nơi làm việc: {ident.get('workplace', 'Văn phòng')}")
        print(f" -> Tính khí: {ident.get('temperament', 'Điềm đạm')} | Đặc điểm: {ident.get('behavioral_quirk', '')}")
        print(f" -> Tình huống hôm nay: {scenario['archetype_name']}")
        print(f" -> Tâm trạng: [{eff_params['current_mood'].upper()}] | Cảnh giác: {eff_params['vigilance_level']}x | Mệt mỏi: {eff_params['accumulated_fatigue']:.2f}")
        print(f" -> Tốc độ thao tác: {speed_mult:.2f}x | Click trượt hiệu dụng: {eff_params['effective_fumble_rate']*100:.1f}%")
        print(f" -> Kế hoạch phiên này: {session_plan['type_label']} (~{session_plan['estimated_duration_sec']:.0f}s)")
        print(f"    * Công việc sẽ làm: {session_plan['tasks_to_execute']}")
        if session_plan['omitted_tasks']:
            omitted_str = " | ".join([f"{o[0]}: {o[1]}" for o in session_plan['omitted_tasks']])
            print(f"    * Tâm lý bỏ sót/quên hôm nay: {omitted_str}")
        print(f" -> Câu chuyện ngày: \"{scenario['daily_narrative']}\"")
        print(f" -> Tiến độ hôm nay: {cur_sessions}/{cap} phiên")
        print("=" * 75)

        # 1. Khởi động Profile qua GPM Local API
        start_res = self.gpm.start_profile(pid)
        if not start_res.get("success") and "data" not in start_res:
            session_status = "FAILED_START_PROFILE"
            print(f"[Runner Error] Không thể khởi động profile '{pname}', bỏ qua lượt này.")
            self._record_audit_log(pid, pname, session_plan, session_status, verification, eff_params)
            return

        # BỌC TOÀN BỘ PHIÊN TRONG TRY...FINALLY ĐỂ ĐẢM BẢO LUÔN ĐÓNG PROFILE
        try:
            # 2. Chờ game tải (Game Loading Delay có tính đến độ vội vã/chậm rãi)
            load_wait = random.uniform(12, 16) * fatigue_mult
            print(f"[Runner] {scenario['real_name']} đang chờ trình duyệt tải trang game Sunflower Land ({load_wait:.1f}s)...")
            time.sleep(load_wait)

            # 3. Tìm cửa sổ và đưa lên Foreground với cơ chế thử lại (Retry)
            hwnd = None
            for attempt in range(3):
                hwnd = WindowHelper.find_game_window(preferred_title=pname)
                if hwnd:
                    break
                time.sleep(1.0)

            if hwnd:
                focused = WindowHelper.bring_to_foreground(hwnd)
                print(f"[Runner] Đã focus cửa sổ game: HWND={hwnd} (FocusConfirmed={focused})")
            else:
                session_status = "FAILED_NO_WINDOW"
                print(f"[Runner Error] Không tìm thấy HWND cửa sổ game của profile '{pname}'. Hủy phiên để đảm bảo an toàn, không click mù!")
                self._record_audit_log(pid, pname, session_plan, session_status, verification, eff_params)
                return

            # 4. Giai đoạn Warm-up ngắm nghía người thật theo phong cách cá nhân
            cur_x, cur_y = HumanMouse.get_position()
            HumanMouse.move_to(
                cur_x + random.randint(-40, 40),
                cur_y + random.randint(-30, 30),
                duration=0.6 * speed_mult,
                random_offset=persona["jitter_px"]
            )
            HumanMouse.human_sleep(2.0, 4.0)

            # 5. Phân tích AI Vision (nếu bật cấu hình)
            analysis = {}
            if self.ai_enabled:
                if not self.ai.api_key:
                    print("[Runner Alert] Cảnh báo thị giác: ai_vision được bật nhưng thiếu API key. Dừng tác vụ để tránh click mù.")
                    session_status = "ABORTED_PERCEPTION_FAILURE"
                    verification["status"] = "VERIFICATION_SKIPPED_NO_API_KEY"
                    verification["details"].append("Perception failed: AI vision enabled but API key is missing")
                    return

                print("[Runner] Đang chụp màn hình gửi Claude Haiku 5.5 phân tích...")
                screenshot = self.ai.capture_screenshot()
                if not screenshot:
                    print("[Runner Alert] Lỗi thị giác: Không thể chụp màn hình hiện tại! Dừng tác vụ để tránh click mù.")
                    session_status = "ABORTED_PERCEPTION_FAILURE"
                    verification["status"] = "VERIFICATION_SKIPPED_NO_SCREENSHOT"
                    verification["details"].append("Perception failed: capture_screenshot returned None before starting actions")
                    return

                analysis = self.ai.analyze_screen(screenshot)
                if not isinstance(analysis, dict) or not analysis.get("success"):
                    err_reason = analysis.get("error", "No response") if isinstance(analysis, dict) else "Analysis failed"
                    print(f"[Runner Alert] Lỗi phân tích thị giác AI: {err_reason}. Dừng tác vụ để bảo vệ an toàn Captcha!")
                    session_status = "ABORTED_PERCEPTION_FAILURE"
                    verification["status"] = "VERIFICATION_SKIPPED_PERCEPTION_ERROR"
                    verification["details"].append(f"AI Vision analysis failed: {err_reason}")
                    return

                print(f"[Runner] AI phản hồi trong {analysis.get('latency')}s: {analysis}")

                # Kiểm tra Captcha có thẩm định lại sau giải
                if CaptchaGuard.check_and_guard(analysis):
                    session_status = "CAPTCHA_PAUSED"
                    self.memory.scenario_engine.register_event_feedback(pid, "CAPTCHA_ALERT", {"analysis": analysis})
                    input("Nhấn Enter sau khi bạn đã giải Captcha xong trên trình duyệt...")
                    if not CaptchaGuard.recheck_screen_after_solve(self.ai):
                        session_status = "CAPTCHA_UNRESOLVED"
                        print("[Runner Guard] Captcha vẫn chưa được giải an toàn. Hủy phiên để bảo vệ tài khoản!")
                        return
                    self.memory.scenario_engine.register_event_feedback(pid, "CAPTCHA_RESOLVED")

                # Kiểm tra Popup che màn hình (thực hiện độc lập, không phụ thuộc vào Captcha)
                if analysis.get("has_blocking_popup") and analysis.get("popup_close_button"):
                    btn_x, btn_y = analysis["popup_close_button"]
                    print(f"[Runner] Phát hiện Popup che, đang bấm tắt tại ({btn_x}, {btn_y})...")
                    HumanMouse.click(btn_x, btn_y, random_offset=persona["jitter_px"])
                    HumanMouse.human_sleep(1.0, 1.8)

                # Kiểm tra vòng xoay đồng bộ Syncing...
                if analysis.get("is_syncing"):
                    print("[Runner Perception] Phát hiện game đang đồng bộ dữ liệu (Syncing...), chờ 2.5s...")
                    time.sleep(2.5)

                # Sử dụng plots_summary từ AI
                ai_plots = analysis.get("plots_summary", {})
                if ai_plots.get("has_ready_crops"):
                    print("[Runner Perception] AI thị giác phát hiện cây đã chín trên các ô đất!")
                if ai_plots.get("has_empty_plots"):
                    print("[Runner Perception] AI thị giác phát hiện có ô đất trống chưa gieo hạt!")

                # Kiểm tra Nấm (Chỉ nhặt nếu phiên này người chơi chú ý nhìn thấy)
                if analysis.get("has_mushrooms") and analysis.get("mushroom_positions"):
                    if "MUSHROOMS" in session_plan["tasks_to_execute"]:
                        mushrooms = analysis["mushroom_positions"]
                        MushroomHunter.harvest_mushrooms(hwnd, mushrooms, is_screen_coords=True)
                    else:
                        print("[Tâm lý thị giác] Nấm mọc ở bãi cỏ rìa ngoài xa tầm mắt, phiên này người chơi vội vàng nên bỏ sót!")

            # 6. THỰC THI TÁC VỤ RUỘNG ĐẤT THỰC TẾ TRONG GAME (HARVEST & PLANT)
            if "CROPS" in session_plan["tasks_to_execute"]:
                ai_plots = analysis.get("plots_summary", {})
                ai_detected_ready = ai_plots.get("has_ready_crops", False)
                ai_detected_empty = ai_plots.get("has_empty_plots", False)
                crops_need_harvest = self.memory.is_crop_ready_for_harvest(pid) or ai_detected_ready

                # A. Thu hoạch cây chín nếu đã đến giờ hoặc AI nhìn thấy cây chín
                if crops_need_harvest:
                    print(f"[Runner] Tiến hành thu hoạch {len(self.plot_coords)} ô đất (MemoryReady={self.memory.is_crop_ready_for_harvest(pid)}, AI_Ready={ai_detected_ready})...")
                    self.crop_mgr.harvest_plots(hwnd, self.plot_coords, scenario=scenario)
                else:
                    print(f"[Runner] Cây trồng chưa đến giờ chín, bỏ qua bước thu hoạch.")

                # B. Chọn hạt giống thích ứng sinh học theo khung giờ tiếp theo
                in_slot, slot_reason, wait_to_next = self.memory.scenario_engine.is_in_active_time_slot(pid, pname)
                is_last_session = (cur_sessions >= cap - 1)
                selected_crop, grow_sec, crop_rationale = SmartCropSelector.select_best_crop(
                    scenario=scenario,
                    current_hour=cur_hour,
                    time_until_next_slot=wait_to_next,
                    is_last_session_today=is_last_session
                )

                print("\n" + "-" * 70)
                print(f" [LỰA CHỌN HẠT GIỐNG THÍCH ỨNG SINH HỌC]")
                print(f" -> Loại hạt chọn: '{selected_crop}' (Thời gian lớn: {grow_sec/60:.1f} phút)")
                print(f" -> Lý do đời thực: \"{crop_rationale}\"")
                print("-" * 70 + "\n")

                # C. Cơ chế treo tab gián đoạn đời thực (Xao nhãng trước khi gieo)
                distract_prob = scenario.get("distraction_prob", 0.12)
                if random.random() < distract_prob:
                    afk_reason = random.choice(scenario.get("daily_distractions", ["Có việc bận đột xuất ngoài đời"]))
                    self.memory.scenario_engine.register_event_feedback(pid, "AFK_DISTRACTION", {"reason": afk_reason})
                    HumanMouse.tab_lingering_pause(min_sec=20.0, max_sec=60.0, reason=afk_reason)

                # D. Gieo hạt nếu vừa thu hoạch xong HOẶC AI phát hiện đất trống
                if crops_need_harvest or ai_detected_empty or not self.memory.data.get(pid, {}).get("planted_crop"):
                    print(f"[Runner] Tiến hành gieo '{selected_crop}' lên {len(self.plot_coords)} ô đất...")
                    self.crop_mgr.plant_plots(
                        hwnd=hwnd,
                        seed_box_coord=self.seed_box_coord,
                        plot_coords=self.plot_coords,
                        profile_id=pid,
                        crop_name=selected_crop,
                        grow_seconds=grow_sec,
                        scenario=scenario,
                        profile_name=pname
                    )
            else:
                print(f"[Runner] Phiên này '{scenario['real_name']}' không làm ruộng (do phân loại phiên hoặc bỏ sót).")

            # 7. THỰC THI CÁC TÁC VỤ PHỤ TRỢ (CHẶT CÂY, MẬT ONG, COMPOSTER) THEO KẾ HOẠCH PHIÊN
            if "TREES" in session_plan["tasks_to_execute"]:
                FarmMaintenance.chop_trees(hwnd, self.tree_coords, scenario=scenario)

            if "HONEY" in session_plan["tasks_to_execute"]:
                FarmMaintenance.harvest_honey(hwnd, self.beehive_coords, scenario=scenario)

            if "COMPOSTER" in session_plan["tasks_to_execute"]:
                FarmMaintenance.manage_composter(hwnd, self.composter_coord, scenario=scenario)

            # 8. HẬU KIỂM ĐÓNG VÒNG LẶP THỊ GIÁC (CLOSED-LOOP VERIFICATION)
            print("[Runner Verification] Bắt đầu quy trình hậu kiểm trạng thái màn hình khép kín...")
            verification = {
                "status": "UNVERIFIED",
                "harvest_verified": None,
                "plant_verified": None,
                "tier1_local_verified": False,
                "tier2_vlm_verified": None,
                "details": []
            }

            post_scr = None
            if self.ai:
                post_scr = self.ai.capture_screenshot()
            elif AIVision:
                post_scr = AIVision.capture_screenshot()

            if post_scr and hwnd:
                # A. TIER 1: KIỂM CHỨNG CỤC BỘ BẰNG LOCAL VISION ENGINE (OPENCV/PIXEL)
                cx, cy, cw, ch = WindowHelper.get_client_rect_on_screen(hwnd)
                if self.plot_coords and cw > 0 and ch > 0:
                    local_checks = []
                    # Kiểm tra toàn bộ các plot_coords để có đánh giá đại diện chính xác
                    for (rel_x, rel_y) in self.plot_coords:
                        screen_x, screen_y = cx + rel_x, cy + rel_y
                        p_state = LocalVisionEngine.analyze_plot_state(post_scr, screen_x, screen_y)
                        local_checks.append(p_state["state"])

                    known_plots = [s for s in local_checks if s in ("GROWING", "READY", "EMPTY")]
                    growing_count = sum(1 for s in local_checks if s == "GROWING")
                    ready_count = sum(1 for s in local_checks if s == "READY")
                    empty_count = sum(1 for s in local_checks if s == "EMPTY")
                    unknown_count = sum(1 for s in local_checks if s not in ("GROWING", "READY", "EMPTY"))

                    verification["tier1_local_verified"] = True
                    verification["details"].append(
                        f"LocalVision plots (Total={len(local_checks)}): GROWING={growing_count}, READY={ready_count}, EMPTY={empty_count}, UNKNOWN={unknown_count}"
                    )

                    if "CROPS" in session_plan["tasks_to_execute"]:
                        min_confident_plots = max(3, int(len(self.plot_coords) * 0.4))
                        if len(known_plots) >= min_confident_plots:
                            if crops_need_harvest:
                                # Hậu kiểm thu hoạch: Đã gặt hết cây chín nếu ready_count == 0
                                verification["harvest_verified"] = (ready_count == 0)

                            # Hậu kiểm gieo hạt: Chỉ coi là PASS khi có bằng chứng dương tính (GROWING > 0 và không còn ô đất trống)
                            if crops_need_harvest or ai_detected_empty or not self.memory.data.get(pid, {}).get("planted_crop"):
                                if growing_count > 0 and empty_count == 0:
                                    verification["plant_verified"] = True
                                elif growing_count > 0 and empty_count > 0:
                                    verification["plant_verified"] = False  # Vẫn còn ô đất trống bị bỏ sót
                                elif empty_count > 0 and growing_count == 0:
                                    verification["plant_verified"] = False
                                else:
                                    verification["plant_verified"] = None
                        else:
                            verification["details"].append("Mẫu nhận diện ô đất không đủ độ tin cậy để kết luận hậu kiểm (quá nhiều UNKNOWN).")

                # B. TIER 2: KIỂM CHỨNG BẰNG CLOUD VLM (CLAUDE HAIKU 5.5) NẾU CÓ BẬT
                if self.ai_enabled and self.ai.api_key:
                    post_analysis = self.ai.analyze_screen(post_scr)
                    if isinstance(post_analysis, dict) and post_analysis.get("success") is True:
                        post_plots = post_analysis.get("plots_summary", {})
                        pre_plots = analysis.get("plots_summary", {})

                        if pre_plots.get("has_ready_crops"):
                            if "has_ready_crops" in post_plots:
                                verification["harvest_verified"] = (post_plots["has_ready_crops"] is False)
                        if pre_plots.get("has_empty_plots") or crops_need_harvest:
                            if "has_empty_plots" in post_plots:
                                verification["plant_verified"] = (post_plots["has_empty_plots"] is False)

                        verification["tier2_vlm_verified"] = True
                    else:
                        err_reason = post_analysis.get("error", "API không phản hồi") if isinstance(post_analysis, dict) else "Phân tích không thành công"
                        verification["tier2_vlm_verified"] = False
                        verification["details"].append(f"Cloud VLM verification: {err_reason}")

                # C. ĐÁNH GIÁ CHỈ SỐ STATUS CHÍNH XÁC (Phân biệt PASS, FAIL, UNVERIFIED)
                valid_checks = []
                for label, v in [("harvest", verification["harvest_verified"]), ("plant", verification["plant_verified"])]:
                    if v is not None:
                        valid_checks.append(v)

                if valid_checks:
                    if all(c is True for c in valid_checks):
                        verification["status"] = "VERIFIED_SUCCESS"
                    elif any(c is True for c in valid_checks):
                        verification["status"] = "VERIFIED_PARTIAL"
                    else:
                        verification["status"] = "VERIFIED_FAILED"
                else:
                    # Tuyệt đối không được gán VERIFIED_SUCCESS khi không có bằng chứng dương tính!
                    verification["status"] = "UNVERIFIED"

                print(f"[Runner Verification Report] Kết quả hậu kiểm: {verification['status']} | Chi tiết: {verification}")
            else:
                verification["status"] = "VERIFICATION_SKIPPED_NO_SCREENSHOT"

            # Xác định trạng thái thực thi dựa trên kết quả hậu kiểm
            if verification["status"] == "VERIFIED_FAILED":
                session_status = "COMPLETED_WITH_VERIFICATION_FAILURE"
            elif verification["status"] == "UNVERIFIED":
                session_status = "COMPLETED_UNVERIFIED"
            else:
                session_status = "COMPLETED"

            # Ghi nhận hoàn thành phiên vào Working Memory của Agent (Park 2023 / Concordia 2024)
            self.memory.scenario_engine.register_event_feedback(
                profile_id=pid,
                event_type="SESSION_COMPLETED",
                details={
                    "tasks_executed": session_plan["tasks_to_execute"],
                    "verification_status": verification["status"]
                }
            )

            # 9. Cơ chế nán lại nhìn ruộng, rê chuột ngắm farm trước khi đóng
            HumanMouse.post_farming_linger(min_sec=6.0, max_sec=18.0)

        except Exception as e:
            session_status = f"EXCEPTION: {str(e)}"
            print(f"[Runner Exception] Gặp lỗi ngoài dự kiến trong phiên profile '{pname}': {e}")
        finally:
            cleanup_error = None
            try:
                print(f"[Runner] Đang dọn dẹp và đóng profile '{pname}'...")
                self.gpm.stop_profile(pid)
            except Exception as clean_ex:
                cleanup_error = str(clean_ex)
                print(f"[Runner Cleanup Warning] Lỗi dọn dẹp khi đóng profile '{pname}': {clean_ex}")

            # Ghi nhận nhật ký kiểm toán phiên với đầy đủ execution_status, verification_status và cleanup_error
            self._record_audit_log(
                profile_id=pid,
                profile_name=pname,
                session_plan=session_plan,
                status=session_status,
                verification=verification,
                eff_params=eff_params,
                execution_status=session_status,
                verification_status=verification.get("status", "UNVERIFIED"),
                cleanup_error=cleanup_error
            )
            print(f"[Runner] {scenario['real_name']} đã kết thúc phiên làm việc trên '{pname}' (ExecStatus={session_status}, VerifyStatus={verification['status']}, Cleanup={'OK' if not cleanup_error else cleanup_error})!")

    def start_loop(self):
        """Vòng lặp chính điều phối 33 profile theo lịch trình người thật."""
        print("\n" + "#" * 65)
        print(" SFL AUTONOMOUS RPA BOT ĐÃ KHỞI CHẠY!")
        print(" Hệ thống: GPM-Login v2 | Chuột Win32 SendInput | Lịch trình Sinh học")
        print("#" * 65 + "\n")

        # Kiểm tra kết nối GPM
        if not self.gpm.check_connection():
            print("[CRITICAL] Khong the ket noi den GPM-Login tai 127.0.0.1:19995!")
            print("Vui long dam bao ban da mo ung dung GPM-Login truoc khi chay tool.")
            return

        profiles = self.gpm.get_profiles(group_filter=self.group_filter)
        print(f"[Runner] Tim thay tong cong {len(profiles)} profile san sang de van hanh.")

        while True:
            # 0. Tự động làm mới danh sách profiles từ GPM để nhận diện profile mới/xóa
            try:
                latest_profiles = self.gpm.get_profiles(group_filter=self.group_filter)
                if latest_profiles:
                    profiles = latest_profiles
            except Exception as e:
                print(f"[Scheduler Warning] Không thể làm mới danh sách profile: {e}")

            # 1. Kiểm tra giờ ngủ đêm
            if self.scheduler.is_sleep_time():
                print("[Scheduler] Hien dang la khung gio ngu dem sinh hoc. Tool se tam nghi den sang...")
                time.sleep(900)  # Ngủ 15 phút rồi kiểm tra lại
                continue

            # 1.5. Kiểm tra giờ ăn trưa / ăn tối (giảm tần suất sinh học)
            if self.scheduler.is_meal_time() and random.random() < 0.7:
                meal_pause = random.uniform(300, 600)  # Tạm nghỉ 5 - 10 phút
                print(f"[Scheduler] Dang trong khung gio com trua/toi sinh hoat gia dinh. Tam dung {meal_pause:.0f}s...")
                time.sleep(meal_pause)
                continue

            # 2. Chọn profile đã đến giờ chín (đã tính Session Cap, Trễ Quên, và Cụm Khung Giờ Sinh Hoạt)
            next_profile = self.scheduler.select_next_profile(profiles)

            if next_profile:
                # Chạy phiên trên profile này
                self.run_session_on_profile(next_profile)

                # Nghỉ ngẫu nhiên giữa 2 profile (Cool-down)
                self.scheduler.wait_inter_profile_delay()
            else:
                # In bảng báo cáo trực quan tình trạng sinh học của các profile
                self.scheduler.print_status_summary(profiles)

                # Tất cả đều đang bận / đợi cây lớn / ngoài khung giờ sinh hoạt -> Tạm nghỉ thông minh
                wait_time = self.scheduler.get_min_wait_time(profiles)
                wait_sec = max(30.0, min(180.0, wait_time))
                print(f"[Scheduler] Đang trong thời gian nghỉ sinh học hoặc đợi cây lớn. Tạm dừng {wait_sec:.0f}s...\n")
                time.sleep(wait_sec)


SunflowerAutomationRunner = MasterRunner  # Alias tương thích ngược


if __name__ == "__main__":
    runner = MasterRunner()
    print("MasterRunner da khoi tao thanh cong!")

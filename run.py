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

from dataclasses import asdict
from core.gpm_api import GpmAPI
from core.human_mouse import HumanMouse
from core.window_helper import WindowHelper
from core.ai_vision import AIVision
from core.local_vision_engine import LocalVisionEngine
from core.evidence_engine import EvidenceFuser, EnvironmentBeliefState, TaskVerifier, PlotStateEnum, VerificationStatus
from tasks.captcha_guard import CaptchaGuard
from tasks.crop_manager import CropManager
from tasks.mushroom_hunter import MushroomHunter
from tasks.farm_maintenance import FarmMaintenance
from tasks.session_task_orchestrator import SessionTaskOrchestrator
from scheduler.farm_memory import FarmMemory
from scheduler.queue_manager import QueueManager
from scheduler.crop_selector import SmartCropSelector
from scheduler.goal_tracker import GoalTracker, SubGoalType, GoalStatus, TaskResumptionManager


class MasterRunner:
    """
    Bộ điều phối trung tâm kết nối toàn bộ 4 hệ thống thành một chu trình khép kín.
    """

    @staticmethod
    def _load_env_file(filepath: str = ".env"):
        """Nạp biến môi trường từ file .env cục bộ nếu có."""
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip()
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

    def __init__(self, config_path: str = "config.json"):
        self._load_env_file()
        self.config = self._load_config(config_path)

        # 1. Khởi tạo các module
        gpm_cfg = self.config.get("gpm_api", {})
        self.gpm = GpmAPI(api_base_url=gpm_cfg.get("base_url", "http://127.0.0.1:19995"))
        self.group_filter = gpm_cfg.get("group_filter")

        ai_cfg = self.config.get("ai_vision", {})
        self.ai_enabled = ai_cfg.get("enabled", False)
        api_key = os.environ.get("AI_VISION_API_KEY") or os.environ.get("BEEKNOEE_API_KEY") or ai_cfg.get("api_key", "")
        base_url = os.environ.get("BEEKNOEE_BASE_URL") or ai_cfg.get("base_url", "https://platform.beeknoee.com/v1")
        model_id = os.environ.get("BEEKNOEE_MODEL_ID") or ai_cfg.get("model_id", "bee-tok/claude-haiku-5-5")
        self.ai = AIVision(
            api_key=api_key,
            base_url=base_url,
            model_id=model_id
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

        # Khởi tạo Branch 2: Quản lý mục tiêu nhận thức theo kiến trúc ACT-R & Memory for Goals
        goal_tracker = GoalTracker(profile_id=pid, macro_goal="FARM_MAINTENANCE_CYCLE")
        goal_tracker.build_goals_from_plan(session_plan["tasks_to_execute"], total_plots=len(self.plot_coords))
        saved_checkpoint = self.memory.get_checkpoint(pid)
        if saved_checkpoint:
            print(f"[Memory for Goals] Phát hiện Checkpoint gián đoạn từ phiên trước: SubGoal='{saved_checkpoint.get('active_subgoal')}'")

        # 1. Khởi động Profile qua GPM Local API
        start_res = self.gpm.start_profile(pid)
        if not start_res.get("success") and "data" not in start_res:
            session_status = "FAILED_START_PROFILE"
            print(f"[Runner Error] Không thể khởi động profile '{pname}', bỏ qua lượt này.")
            self._record_audit_log(pid, pname, session_plan, session_status, verification, eff_params)
            return

        # BỌC TOÀN BỘ PHIÊN TRONG TRY...FINALLY ĐỂ ĐẢM BẢO LUÔN ĐÓNG PROFILE
        try:
            debug_addr = start_res.get("selenium_remote_debug_address")
            debug_port = start_res.get("remote_debug_port")
            browser_pid = start_res.get("process_id")

            # 1b. Dò Process ID của trình duyệt nếu chưa có
            if debug_port and not browser_pid:
                for _ in range(6):
                    browser_pid = self.gpm.find_pid_by_port(debug_port)
                    if browser_pid:
                        break
                    time.sleep(0.5)

            # 1c. Kiểm tra và tự động điều hướng sang Sunflower Land qua CDP nếu chưa mở
            if debug_addr:
                try:
                    tabs = self.gpm.get_cdp_tabs(debug_addr)
                    page_tabs = [t for t in tabs if t.get("type") == "page"]
                    has_sfl = any("sunflower-land.com" in (t.get("url") or "") for t in page_tabs)
                    if not has_sfl:
                        print(f"[Runner] Chưa mở Sunflower Land trên tab active, đang điều hướng CDP tới https://sunflower-land.com/play/...")
                        self.gpm.cdp_navigate(debug_addr, "https://sunflower-land.com/play/")
                except Exception as cdp_err:
                    print(f"[Runner Warning] Không thể kiểm tra tab qua CDP: {cdp_err}")

            # 2. Chờ game tải (Game Loading Delay có tính đến độ vội vã/chậm rãi)
            load_wait = random.uniform(12, 16) * fatigue_mult
            print(f"[Runner] {scenario['real_name']} đang chờ trình duyệt tải trang game Sunflower Land ({load_wait:.1f}s)...")
            time.sleep(load_wait)

            # 3. Tìm cửa sổ và đưa lên Foreground với cơ chế thử lại (Retry)
            hwnd = None
            for attempt in range(5):
                hwnd = WindowHelper.find_game_window(preferred_title=pname, target_pid=browser_pid)
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
            if cur_x <= 0 and cur_y <= 0:
                cx, cy, cw, ch = WindowHelper.get_client_rect_on_screen(hwnd)
                cur_x, cur_y = cx + cw // 2, cy + ch // 2
            HumanMouse.move_to(
                cur_x + random.randint(-40, 40),
                cur_y + random.randint(-30, 30),
                duration=0.6 * speed_mult,
                random_offset=persona["jitter_px"]
            )
            HumanMouse.human_sleep(2.0, 4.0)

            # 5. Phân tích Thị giác & Trạng thái Niềm tin POMDP (Branch 1)
            screenshot = None
            if self.ai:
                screenshot = self.ai.capture_screenshot()
            elif AIVision:
                screenshot = AIVision.capture_screenshot()

            if not screenshot:
                print("[Runner Alert] Lỗi thị giác: Không thể chụp màn hình hiện tại! Dừng tác vụ để tránh click mù.")
                session_status = "ABORTED_PERCEPTION_FAILURE"
                verification["status"] = "VERIFICATION_SKIPPED_NO_SCREENSHOT"
                verification["details"].append("Perception failed: capture_screenshot returned None before starting actions")
                return

            cx, cy, cw, ch = WindowHelper.get_client_rect_on_screen(hwnd)
            local_plots_obs = []
            if self.plot_coords and cw > 0 and ch > 0:
                for (rel_x, rel_y) in self.plot_coords:
                    local_plots_obs.append(LocalVisionEngine.analyze_plot_state(screenshot, cx + rel_x, cy + rel_y))

            analysis = {}
            if self.ai_enabled:
                if not self.ai.api_key:
                    print("[Runner Alert] Cảnh báo thị giác: ai_vision được bật nhưng thiếu API key. Dừng tác vụ để tránh click mù.")
                    session_status = "ABORTED_PERCEPTION_FAILURE"
                    verification["status"] = "VERIFICATION_SKIPPED_NO_API_KEY"
                    verification["details"].append("Perception failed: AI vision enabled but API key is missing")
                    return

                print("[Runner] Đang chụp màn hình gửi Claude Haiku 5.5 phân tích...")
                analysis = self.ai.analyze_screen(screenshot)
                if not isinstance(analysis, dict) or not analysis.get("success"):
                    err_reason = analysis.get("error", "No response") if isinstance(analysis, dict) else "Analysis failed"
                    print(f"[Runner Alert] Lỗi phân tích thị giác AI: {err_reason}. Dừng tác vụ để bảo vệ an toàn Captcha!")
                    session_status = "ABORTED_PERCEPTION_FAILURE"
                    verification["status"] = "VERIFICATION_SKIPPED_PERCEPTION_ERROR"
                    verification["details"].append(f"AI Vision analysis failed: {err_reason}")
                    return
                print(f"[Runner] AI phản hồi trong {analysis.get('latency')}s: {analysis}")

            # Hợp nhất bằng chứng đa nguồn thành Trạng thái Niềm tin POMDP (Branch 1)
            pre_belief = EvidenceFuser.build_environment_belief(
                timestamp=time.time(),
                plot_coords=self.plot_coords,
                local_plots_analysis=local_plots_obs,
                vlm_analysis=analysis
            )
            print(f"[POMDP Belief State] Tin cậy: {pre_belief.overall_confidence:.2f} | Ô chín: {pre_belief.ready_plots_count} | Ô trống: {pre_belief.empty_plots_count} | Đang lớn: {pre_belief.growing_plots_count} | Chưa rõ: {pre_belief.unknown_plots_count}")

            # Chính sách từ chối hành động (Abstention Policy - Kurniawati 2022)
            if pre_belief.abstention_triggered:
                print(f"[POMDP Abstention] Kích hoạt chính sách từ chối hành động: {pre_belief.abstention_reason}")
                if pre_belief.has_captcha:
                    session_status = "CAPTCHA_PAUSED"
                    self.memory.scenario_engine.register_event_feedback(pid, "CAPTCHA_ALERT", {"analysis": analysis})
                    input("Nhấn Enter sau khi bạn đã giải Captcha xong trên trình duyệt...")
                    if not CaptchaGuard.recheck_screen_after_solve(self.ai):
                        session_status = "CAPTCHA_UNRESOLVED"
                        print("[Runner Guard] Captcha vẫn chưa được giải an toàn. Hủy phiên để bảo vệ tài khoản!")
                        return
                    self.memory.scenario_engine.register_event_feedback(pid, "CAPTCHA_RESOLVED")
                elif pre_belief.is_syncing:
                    print("[Runner Perception] Game đang đồng bộ dữ liệu (Syncing...), chờ 2.5s...")
                    time.sleep(2.5)

            # Xử lý Popup che màn hình nếu có
            if pre_belief.has_blocking_popup and pre_belief.popup_close_button:
                btn_x, btn_y = pre_belief.popup_close_button
                print(f"[Runner] Phát hiện Popup che, đang bấm tắt tại ({btn_x}, {btn_y})...")
                HumanMouse.click(btn_x, btn_y, random_offset=persona["jitter_px"])
                HumanMouse.human_sleep(1.0, 1.8)

            # Thu nhặt nấm dại nếu có
            if pre_belief.has_mushrooms and pre_belief.mushroom_positions:
                if "MUSHROOMS" in session_plan["tasks_to_execute"]:
                    MushroomHunter.harvest_mushrooms(hwnd, pre_belief.mushroom_positions, is_screen_coords=True)

            # Đối chiếu Phục hồi Tác vụ sau Gián đoạn (Branch 2 Memory for Goals)
            resumption_plan = TaskResumptionManager.reconcile_interrupted_session(saved_checkpoint, pre_belief)
            if resumption_plan.get("resumption_mode") != "FRESH_START":
                print(f"[Memory for Goals] {resumption_plan['rationale']}")

            # 6. THỰC THI TÁC VỤ RUỘNG ĐẤT THỰC TẾ TRONG GAME (HARVEST & PLANT)
            if "CROPS" in session_plan["tasks_to_execute"]:
                if resumption_plan.get("resumption_mode") == "ABSTAIN_UNCERTAIN":
                    print(f"[Runner Warning] Không đủ bằng chứng tin cậy để tiếp tục tác vụ ruộng ({resumption_plan.get('rationale')}). Tạm dừng tác vụ ruộng để bảo vệ tài khoản.")
                    goal_tracker.skip_subgoal(SubGoalType.HARVEST_CROPS, reason="ABSTAIN_UNCERTAIN_OBSERVATION")
                    goal_tracker.skip_subgoal(SubGoalType.SELECT_CROP, reason="ABSTAIN_UNCERTAIN_OBSERVATION")
                    goal_tracker.skip_subgoal(SubGoalType.PLANT_SEEDS, reason="ABSTAIN_UNCERTAIN_OBSERVATION")
                else:
                    crops_need_harvest = (
                        resumption_plan.get("resumption_mode") == "RESUME_PARTIAL_HARVEST" or
                        (
                            resumption_plan.get("resumption_mode") not in ("ADVANCE_TO_VERIFICATION", "ADVANCE_TO_PLANTING") and
                            (self.memory.is_crop_ready_for_harvest(pid) or pre_belief.ready_plots_count > 0)
                        )
                    )

                    # A. Thu hoạch cây chín
                    if crops_need_harvest:
                        goal_tracker.start_subgoal(SubGoalType.HARVEST_CROPS)
                        harvest_plots = self.plot_coords
                        if resumption_plan.get("resumption_mode") == "RESUME_PARTIAL_HARVEST" and resumption_plan.get("target_plots"):
                            harvest_plots = [self.plot_coords[i] for i in resumption_plan["target_plots"] if i < len(self.plot_coords)]

                        print(f"[Runner] Tiến hành thu hoạch {len(harvest_plots)} ô đất (BeliefReady={pre_belief.ready_plots_count})...")
                        h_res = self.crop_mgr.harvest_plots(hwnd, harvest_plots, scenario=scenario)
                        if h_res.get("status") == "FAILED":
                            goal_tracker.fail_subgoal(SubGoalType.HARVEST_CROPS, error_message=h_res.get("error", "HARVEST_FAILED"), metadata=h_res)
                        else:
                            goal_tracker.record_commands_issued(SubGoalType.HARVEST_CROPS, metadata=h_res)

                        self.memory.save_checkpoint(pid, asdict(goal_tracker.create_checkpoint(
                            last_attempted_action="HARVEST_CROPS",
                            is_verified=False,
                            metadata=h_res
                        )))
                    else:
                        goal_tracker.skip_subgoal(SubGoalType.HARVEST_CROPS, reason="CROPS_NOT_READY")
                        print(f"[Runner] Cây trồng chưa đến giờ chín, bỏ qua bước thu hoạch.")

                    # B. Chọn hạt giống thích ứng sinh học theo khung giờ tiếp theo
                    goal_tracker.start_subgoal(SubGoalType.SELECT_CROP)
                    in_slot, slot_reason, wait_to_next = self.memory.scenario_engine.is_in_active_time_slot(pid, pname)
                    is_last_session = (cur_sessions >= cap - 1)
                    selected_crop, grow_sec, crop_rationale = SmartCropSelector.select_best_crop(
                        scenario=scenario,
                        current_hour=cur_hour,
                        time_until_next_slot=wait_to_next,
                        is_last_session_today=is_last_session
                    )
                    goal_tracker.complete_subgoal(SubGoalType.SELECT_CROP, metadata={"selected_crop": selected_crop, "grow_sec": grow_sec})

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

                    # D. Gieo hạt nếu vừa thu hoạch xong HOẶC đất trống
                    should_plant = (
                        resumption_plan.get("resumption_mode") in ("RESUME_PARTIAL_PLANTING", "ADVANCE_TO_PLANTING") or
                        (
                            resumption_plan.get("resumption_mode") != "ADVANCE_TO_VERIFICATION" and
                            (
                                crops_need_harvest or
                                pre_belief.empty_plots_count > 0 or
                                not self.memory.data.get(pid, {}).get("planted_crop")
                            )
                        )
                    )
                    if should_plant:
                        goal_tracker.start_subgoal(SubGoalType.PLANT_SEEDS)
                        plant_plots = self.plot_coords
                        if resumption_plan.get("resumption_mode") == "RESUME_PARTIAL_PLANTING" and resumption_plan.get("target_plots"):
                            plant_plots = [self.plot_coords[i] for i in resumption_plan["target_plots"] if i < len(self.plot_coords)]

                        print(f"[Runner] Tiến hành gieo '{selected_crop}' lên {len(plant_plots)} ô đất...")
                        p_res = self.crop_mgr.plant_plots(
                            hwnd=hwnd,
                            seed_box_coord=self.seed_box_coord,
                            plot_coords=plant_plots,
                            profile_id=pid,
                            crop_name=selected_crop,
                            grow_seconds=grow_sec,
                            scenario=scenario,
                            profile_name=pname,
                            record_memory=True
                        )
                        if p_res.get("status") in ("TOOL_SELECTION_FAILED", "FAILED", "INVALID_HWND"):
                            goal_tracker.fail_subgoal(SubGoalType.PLANT_SEEDS, error_message=p_res.get("error", "PLANT_FAILED"), metadata=p_res)
                        else:
                            goal_tracker.record_commands_issued(SubGoalType.PLANT_SEEDS, metadata=p_res)

                        self.memory.save_checkpoint(pid, asdict(goal_tracker.create_checkpoint(
                            last_attempted_action="PLANT_SEEDS",
                            is_verified=False,
                            metadata={"selected_crop": selected_crop, "grow_sec": grow_sec, "plant_result": p_res}
                        )))
                    else:
                        goal_tracker.skip_subgoal(SubGoalType.PLANT_SEEDS, reason="PLANTING_NOT_NEEDED")
            else:
                print(f"[Runner] Phiên này '{scenario['real_name']}' không làm ruộng (do phân loại phiên hoặc bỏ sót).")

            # 7. THỰC THI CÁC TÁC VỤ PHỤ TRỢ (CHẶT CÂY, MẬT ONG, COMPOSTER) THEO KẾ HOẠCH PHIÊN
            if "TREES" in session_plan["tasks_to_execute"]:
                if self.memory.is_tree_ready_for_chop(pid):
                    goal_tracker.start_subgoal(SubGoalType.CHOP_TREES)
                    chop_res = FarmMaintenance.chop_trees(hwnd, self.tree_coords, scenario=scenario, hits_per_tree=3)
                    self.memory.record_tree_chop(pid)
                    goal_tracker.record_commands_issued(SubGoalType.CHOP_TREES, metadata=chop_res)
                    goal_tracker.complete_subgoal(SubGoalType.CHOP_TREES)
                else:
                    ready_at = self.memory.data.get(pid, {}).get("trees_ready_at", 0)
                    rem_min = max(0.0, (ready_at - time.time()) / 60)
                    print(f"[Runner] Rừng cây đang trong thời gian hồi sinh (còn ~{rem_min:.1f} phút nữa mới mọc lại), bỏ qua chặt cây.")
                    goal_tracker.skip_subgoal(SubGoalType.CHOP_TREES, reason="TREES_RECOVERING")

            if "HONEY" in session_plan["tasks_to_execute"]:
                goal_tracker.start_subgoal(SubGoalType.HARVEST_HONEY)
                honey_res = FarmMaintenance.harvest_honey(hwnd, self.beehive_coords, scenario=scenario)
                goal_tracker.record_commands_issued(SubGoalType.HARVEST_HONEY, metadata=honey_res)
                goal_tracker.complete_subgoal(SubGoalType.HARVEST_HONEY)

            if "COMPOSTER" in session_plan["tasks_to_execute"]:
                goal_tracker.start_subgoal(SubGoalType.MANAGE_COMPOSTER)
                comp_res = FarmMaintenance.manage_composter(hwnd, self.composter_coord, scenario=scenario)
                goal_tracker.record_commands_issued(SubGoalType.MANAGE_COMPOSTER, metadata=comp_res)
                goal_tracker.complete_subgoal(SubGoalType.MANAGE_COMPOSTER)

            # 8. HẬU KIỂM ĐÓNG VÒNG LẶP THỊ GIÁC (CLOSED-LOOP VERIFICATION)
            print("[Runner Verification] Bắt đầu quy trình hậu kiểm trạng thái màn hình khép kín...")
            goal_tracker.start_subgoal(SubGoalType.POST_VERIFICATION)
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
                cx, cy, cw, ch = WindowHelper.get_client_rect_on_screen(hwnd)
                post_local_plots = []
                if self.plot_coords and cw > 0 and ch > 0:
                    for (rel_x, rel_y) in self.plot_coords:
                        screen_x, screen_y = cx + rel_x, cy + rel_y
                        p_state = LocalVisionEngine.analyze_plot_state(post_scr, screen_x, screen_y)
                        post_local_plots.append(p_state)

                post_vlm_analysis = {}
                if self.ai_enabled and self.ai.api_key:
                    post_analysis = self.ai.analyze_screen(post_scr)
                    if isinstance(post_analysis, dict) and post_analysis.get("success") is True:
                        post_vlm_analysis = post_analysis
                        verification["tier2_vlm_verified"] = True
                    else:
                        err_reason = post_analysis.get("error", "API không phản hồi") if isinstance(post_analysis, dict) else "Phân tích không thành công"
                        verification["tier2_vlm_verified"] = False
                        verification["details"].append(f"Cloud VLM verification: {err_reason}")

                # Xây dựng Trạng thái Niềm tin hậu kỳ (Branch 1 POMDP)
                post_belief = EvidenceFuser.build_environment_belief(
                    timestamp=time.time(),
                    plot_coords=self.plot_coords,
                    local_plots_analysis=post_local_plots,
                    vlm_analysis=post_vlm_analysis
                )

                verification["tier1_local_verified"] = len(post_local_plots) > 0
                verification["details"].append(
                    f"Post-action Belief: READY={post_belief.ready_plots_count}, EMPTY={post_belief.empty_plots_count}, GROWING={post_belief.growing_plots_count}, UNKNOWN={post_belief.unknown_plots_count} (Conf={post_belief.overall_confidence:.2f})"
                )

                # Thẩm định vị từ đóng theo phong cách OSWorld (TaskVerifier)
                if "CROPS" in session_plan["tasks_to_execute"]:
                    if crops_need_harvest:
                        h_res = TaskVerifier.verify_harvest_action(pre_belief, post_belief)
                        verification["harvest_verified"] = h_res["verified"]
                        verification["details"].append(f"Harvest Verification: {h_res['status']} ({h_res['reason']})")

                    if should_plant:
                        p_res = TaskVerifier.verify_plant_action(pre_belief, post_belief)
                        verification["plant_verified"] = p_res["verified"]
                        verification["details"].append(f"Plant Verification: {p_res['status']} ({p_res['reason']})")

                # Đánh giá chỉ số status chính xác
                valid_checks = []
                for label, v in [("harvest", verification["harvest_verified"]), ("plant", verification["plant_verified"])]:
                    if v is not None:
                        valid_checks.append(v)

                if valid_checks:
                    if all(c is True for c in valid_checks):
                        verification["status"] = VerificationStatus.VERIFIED_SUCCESS.value
                    elif any(c is True for c in valid_checks):
                        verification["status"] = VerificationStatus.VERIFIED_PARTIAL.value
                    else:
                        verification["status"] = VerificationStatus.VERIFIED_FAILED.value
                else:
                    if post_belief.abstention_triggered:
                        verification["status"] = VerificationStatus.ABSTAIN_UNCERTAIN.value
                    else:
                        verification["status"] = "UNVERIFIED"

                if verification["status"] == VerificationStatus.VERIFIED_SUCCESS.value:
                    if "CROPS" in session_plan["tasks_to_execute"]:
                        if crops_need_harvest and verification.get("harvest_verified"):
                            goal_tracker.complete_subgoal(SubGoalType.HARVEST_CROPS)
                        if should_plant and verification.get("plant_verified"):
                            goal_tracker.complete_subgoal(SubGoalType.PLANT_SEEDS)
                            self.memory.mark_planting_verified(pid, True)
                    goal_tracker.complete_subgoal(SubGoalType.POST_VERIFICATION)
                    self.memory.clear_checkpoint(pid)
                    print(f"[Memory for Goals] Hậu kiểm thành công (PASS)! Đã dọn sạch Checkpoint.")
                elif verification["status"] == VerificationStatus.VERIFIED_FAILED.value:
                    if "CROPS" in session_plan["tasks_to_execute"]:
                        if crops_need_harvest and verification.get("harvest_verified") is False:
                            goal_tracker.fail_subgoal(SubGoalType.HARVEST_CROPS, error_message="HARVEST_VERIFICATION_FAILED")
                        if should_plant and verification.get("plant_verified") is False:
                            goal_tracker.fail_subgoal(SubGoalType.PLANT_SEEDS, error_message="PLANT_VERIFICATION_FAILED")
                    goal_tracker.fail_subgoal(SubGoalType.POST_VERIFICATION, error_message="POST_VERIFICATION_FAILED")
                    print(f"[Memory for Goals] Hậu kiểm thất bại ({verification['status']}), cập nhật Checkpoint trạng thái.")
                    self.memory.save_checkpoint(pid, asdict(goal_tracker.create_checkpoint(
                        last_action="POST_VERIFICATION",
                        is_verified=False,
                        metadata={"verification_status": verification["status"]}
                    )))
                else:
                    print(f"[Memory for Goals] Hậu kiểm chưa đạt tuyệt đối ({verification['status']}), cập nhật Checkpoint trạng thái.")
                    self.memory.save_checkpoint(pid, asdict(goal_tracker.create_checkpoint(
                        last_action="POST_VERIFICATION",
                        is_verified=False,
                        metadata={"verification_status": verification["status"]}
                    )))

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
            interrupted_sg = goal_tracker.interrupt_active_subgoal(reason=f"EXCEPTION: {str(e)}")
            if interrupted_sg:
                ckpt = goal_tracker.create_checkpoint(
                    last_attempted_action=interrupted_sg.name.value,
                    is_verified=False,
                    metadata={"exception": str(e), "profile_name": pname}
                )
                self.memory.save_checkpoint(pid, asdict(ckpt))
                print(f"[Memory for Goals] Đã lưu Checkpoint phục hồi khi gặp ngoại lệ: SubGoal='{interrupted_sg.name.value}'")
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
    import argparse
    parser = argparse.ArgumentParser(description="Sunflower Land Autonomous Desktop RPA Master Runner")
    parser.add_argument("--profile", "-p", type=str, help="Chạy một phiên duy nhất trên profile chỉ định (Tên profile hoặc Profile ID)")
    parser.add_argument("--config", "-c", type=str, default="config.json", help="Đường dẫn file cấu hình JSON")
    args = parser.parse_args()

    runner = MasterRunner(config_path=args.config)

    if args.profile:
        print(f"[MasterRunner] Đang tìm kiếm profile: '{args.profile}'...")
        target_profile = runner.gpm.find_profile_by_name(args.profile)
        if not target_profile:
            # Tìm kiếm mở rộng theo ID hoặc substring tên
            for p in runner.gpm.get_profiles():
                if p.get("id") == args.profile or p.get("name", "").lower() == args.profile.lower() or args.profile.lower() in p.get("name", "").lower():
                    target_profile = p
                    break

        if not target_profile:
            print(f"[MasterRunner Error] Không tìm thấy profile nào khớp với: '{args.profile}'!")
            sys.exit(1)

        print(f"[MasterRunner] Đã tìm thấy profile: '{target_profile.get('name')}' (ID: {target_profile.get('id')})")
        runner.run_session_on_profile(target_profile)
    else:
        runner.start_loop()

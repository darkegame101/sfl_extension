"""
TEST SUITE CHUYÊN SÂU: KIỂM ĐỊNH SCENARIO ENGINE & SUY LUẬN BỐI CẢNH ĐỘNG
Kiểm tra:
1. Dynamic Context Inference (Lịch thực tế, Ngày trong tuần, Nghề nghiệp).
2. Chuỗi chuyển trạng thái Markov & Mệt mỏi tích lũy (Burnout / Historical Carryover).
3. Tính tương thích Alias giữa fumble_rate và miss_click_prob.
4. Độ phủ chiến lược riêng biệt của cả 6 nhóm bối cảnh trong CropSelector & Orchestrator.
"""

import unittest
import os
import sys
import tempfile
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler.scenario_engine import ScenarioEngine
from scheduler.crop_selector import SmartCropSelector
from tasks.session_task_orchestrator import SessionTaskOrchestrator


class TestScenarioEngineEvaluation(unittest.TestCase):

    def setUp(self):
        import random
        random.seed(42)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_file = os.path.join(self.temp_dir.name, "test_dynamic_scenarios.json")
        self.engine = ScenarioEngine(self.storage_file)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_alias_compatibility_fumble_and_distraction(self):
        """Kiểm tra alias giữa fumble_rate và miss_click_prob để không bị lỗi gãy tích hợp."""
        ident = {"real_name": "Nam", "occupation": "Kỹ sư phần mềm"}
        sc = self.engine.get_or_generate_scenario("p_test_alias", "Profile Alias", ident)

        # Cả 2 khóa phải tồn tại và có cùng giá trị
        self.assertIn("fumble_rate", sc)
        self.assertIn("miss_click_prob", sc)
        self.assertEqual(sc["fumble_rate"], sc["miss_click_prob"])

        self.assertIn("distraction_prob", sc)
        self.assertIn("distract_rate", sc)
        self.assertEqual(sc["distraction_prob"], sc["distract_rate"])

    def test_dynamic_weights_occupation_influence(self):
        """Kỹ sư phần mềm phải có xác suất WFH cao hơn nhân viên ngân hàng."""
        dev_ident = {"occupation": "Kỹ sư phần mềm (Backend Developer)"}
        banker_ident = {"occupation": "Nhân viên Ngân hàng (Giao dịch viên)"}

        dev_weights = self.engine._calculate_dynamic_archetype_weights("dev_1", dev_ident)
        banker_weights = self.engine._calculate_dynamic_archetype_weights("bank_1", banker_ident)

        # Index 0 là WFH_RAINY_DAY trong DAILY_LIFE_SITUATIONS
        self.assertGreater(dev_weights[0], banker_weights[0])

    def test_historical_burnout_carryover(self):
        """Nếu hôm qua tăng ca kiệt sức (DEADLINE_OVERTIME), hôm nay xác suất lười biếng bù phải tăng vọt."""
        pid = "prof_burnout"
        # Giả lập trạng thái hôm qua
        self.engine.scenarios[pid] = {
            "date": "2026-10-14",
            "scenario": {"category": "DEADLINE_OVERTIME"}
        }

        weights = self.engine._calculate_dynamic_archetype_weights(pid, {"occupation": "Kỹ sư"})
        # Index 4 là LAZY_RAINY_AFTERNOON trong DAILY_LIFE_SITUATIONS
        # Base weight là 7, sau khi tăng ca phải được boost ít nhất 2.5x
        self.assertGreater(weights[4], 14.0)

    def test_all_six_archetypes_have_distinct_crop_strategies(self):
        """Đảm bảo toàn bộ 6 nhóm bối cảnh đều có chiến lược gieo hạt riêng biệt, định lượng rõ rệt."""
        categories = [
            "DEADLINE_OVERTIME",
            "FAMILY_TRIP_DETOX",
            "LAZY_RAINY_AFTERNOON",
            "WEEKEND_CAFE",
            "WFH_RAINY_DAY",
            "OFFICE_STANDARD"
        ]

        durations = {}
        for cat in categories:
            sc = {"category": cat, "real_name": "Test", "job": "Tester"}
            crop, sec, rationale = SmartCropSelector.select_best_crop(
                scenario=sc,
                current_hour=14.0,  # Giữa chiều
                time_until_next_slot=7200.0,
                is_last_session_today=False
            )
            durations[cat] = sec
            self.assertIsNotNone(crop)
            self.assertGreater(sec, 0)

        # Định lượng: FAMILY_TRIP_DETOX chọn cây dài hạn (>= 38880s ~ 10.8h)
        self.assertGreaterEqual(durations["FAMILY_TRIP_DETOX"], 38880)

        # Định lượng: WFH_RAINY_DAY cày cuốc liên tục nên chọn cây siêu ngắn (<= 300s ~ 5 phút)
        self.assertLessEqual(durations["WFH_RAINY_DAY"], 300)

        # Sự khác biệt thời gian gieo giữa Đi chơi xa và WFH phải chênh lệch ít nhất 100 lần!
        self.assertGreater(durations["FAMILY_TRIP_DETOX"] / durations["WFH_RAINY_DAY"], 100.0)

    def test_all_six_archetypes_have_distinct_orchestrator_weights(self):
        """Đảm bảo SessionTaskOrchestrator phân bổ xác suất phiên khác biệt định lượng giữa các Archetype."""
        persona = {"human_identity": {"temperament": "Cân bằng"}}

        # 1. DEADLINE_OVERTIME: Phải chủ yếu là QUICK_RUSH và 0% FULL_MAINTENANCE
        sc_deadline = {"category": "DEADLINE_OVERTIME", "real_name": "Test", "job": "Tester", "daily_session_cap": 2}
        deadline_types = [SessionTaskOrchestrator.determine_session_plan(sc_deadline, persona, 14.0, 1)["session_type"] for _ in range(40)]
        self.assertNotIn("FULL_MAINTENANCE", deadline_types)
        quick_ratio_deadline = deadline_types.count("QUICK_RUSH") / len(deadline_types)
        self.assertGreater(quick_ratio_deadline, 0.70)

        # 2. WEEKEND_CAFE: Thư thái nên phải xuất hiện FULL_MAINTENANCE và ít QUICK_RUSH hơn hẳn
        sc_cafe = {"category": "WEEKEND_CAFE", "real_name": "Test", "job": "Tester", "daily_session_cap": 8}
        cafe_types = [SessionTaskOrchestrator.determine_session_plan(sc_cafe, persona, 14.0, 1)["session_type"] for _ in range(40)]
        self.assertIn("FULL_MAINTENANCE", cafe_types)
        quick_ratio_cafe = cafe_types.count("QUICK_RUSH") / len(cafe_types)
        self.assertLess(quick_ratio_cafe, 0.40)

    def test_episodic_stream_and_captcha_vigilance(self):
        """Kiểm tra luồng sự kiện hồi tưởng (Park 2023) & Tăng cảnh giác tức thời sau Captcha."""
        pid = "p_episodic_captcha"
        sc = self.engine.get_or_generate_scenario(pid, "Profile Captcha Test")

        # Ban đầu mức cảnh giác = 1.0, stream rỗng
        self.assertEqual(sc["intra_day_state"]["vigilance_level"], 1.0)
        self.assertEqual(len(sc["episodic_stream"]), 0)

        # Ghi nhận sự kiện Captcha Alert
        self.engine.register_event_feedback(pid, "CAPTCHA_ALERT", {"trigger": "visual_ai"})
        eff_params = self.engine.get_effective_behavioral_params(pid)

        # Cảnh giác phải tăng vọt
        self.assertGreater(eff_params["vigilance_level"], 1.3)
        self.assertEqual(eff_params["current_mood"], "Căng thẳng & Cảnh giác cao độ")
        # Do tập trung cao độ, fumble rate phải giảm so với gốc
        self.assertLess(eff_params["effective_fumble_rate"], sc["fumble_rate"])

        # Sau khi giải xong Captcha
        self.engine.register_event_feedback(pid, "CAPTCHA_RESOLVED", {"status": "success"})
        eff_params_after = self.engine.get_effective_behavioral_params(pid)
        self.assertLess(eff_params_after["vigilance_level"], eff_params["vigilance_level"])
        self.assertGreaterEqual(len(self.engine.scenarios[pid]["scenario"]["episodic_stream"]), 2)

    def test_intra_day_session_fatigue_accumulation(self):
        """Kiểm tra tích lũy mệt mỏi qua nhiều phiên liên tiếp trong ngày (Concordia 2024)."""
        pid = "p_fatigue_acc"
        sc = self.engine.get_or_generate_scenario(pid, "Profile Fatigue Test")

        init_params = self.engine.get_effective_behavioral_params(pid)
        init_fatigue = init_params["accumulated_fatigue"]

        # Mô phỏng hoàn thành 6 phiên liên tiếp
        for i in range(6):
            self.engine.register_event_feedback(pid, "SESSION_COMPLETED", {"session_num": i + 1})

        post_params = self.engine.get_effective_behavioral_params(pid)
        self.assertGreater(post_params["accumulated_fatigue"], init_fatigue)
        self.assertEqual(post_params["sessions_completed"], 6)
        # Mệt mỏi cao làm giảm độ nhanh nhạy (tăng speed_multiplier di chuyển chuột)
        self.assertGreater(post_params["effective_speed_multiplier"], init_params["effective_speed_multiplier"])
        # Khi mệt mỏi >= 0.45, tâm trạng chuyển sang Oải & Giảm tập trung
        self.assertEqual(post_params["current_mood"], "Oải & Giảm tập trung")


if __name__ == "__main__":
    unittest.main()


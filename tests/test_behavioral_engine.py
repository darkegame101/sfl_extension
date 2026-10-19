"""
TEST SUITE: KIỂM THỬ ĐỘNG CƠ HÀNH VI & LỊCH TRÌNH SINH HỌC
Kiểm tra tính đúng đắn của PersonaManager, ScenarioEngine, SmartCropSelector, SessionTaskOrchestrator
"""

import unittest
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler.persona_manager import PersonaManager
from scheduler.scenario_engine import ScenarioEngine
from scheduler.crop_selector import SmartCropSelector
from tasks.session_task_orchestrator import SessionTaskOrchestrator


class TestBehavioralEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.persona_file = os.path.join(self.temp_dir.name, "test_personas.json")
        self.scenario_file = os.path.join(self.temp_dir.name, "test_scenarios.json")
        self.persona_mgr = PersonaManager(self.persona_file)
        self.scenario_engine = ScenarioEngine(self.scenario_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_persona_creation_and_persistence(self):
        """Kiểm tra khởi tạo Persona với nhân khẩu học và tính bất biến khi gọi lại."""
        p1 = self.persona_mgr.get_or_create_persona("profile_abc", "Profile ABC")
        self.assertIn("human_identity", p1)
        self.assertIn("mouse_speed_factor", p1)
        self.assertIn("jitter_px", p1)

        # Lần gọi thứ 2 phải trả về đúng Persona đã lưu
        p2 = self.persona_mgr.get_or_create_persona("profile_abc", "Profile ABC")
        self.assertEqual(p1["human_identity"]["real_name"], p2["human_identity"]["real_name"])
        self.assertEqual(p1["mouse_speed_factor"], p2["mouse_speed_factor"])

    def test_scenario_time_slot_clustering(self):
        """Kiểm tra logic phân cụm khung giờ sinh hoạt (Time-Slot Clustering)."""
        ident = {"job": "Kế toán viên doanh nghiệp", "temperament": "Cẩn thận & Tỉ mỉ"}
        scenario = self.scenario_engine.get_or_generate_scenario("p1", "Profile 1", ident)

        self.assertIn("today_slots", scenario)
        self.assertIn("daily_session_cap", scenario)
        self.assertGreaterEqual(scenario["daily_session_cap"], 1)
        self.assertLessEqual(scenario["daily_session_cap"], 22)

    def test_smart_crop_selector(self):
        """Kiểm tra bộ chọn hạt giống thích ứng theo thời gian trống."""
        scenario = {"archetype_name": "Test Archetype"}

        # TH1: Còn 50 phút đến slot tiếp theo -> Phải chọn cây có thời gian chín <= 50 phút
        crop, sec, rationale = SmartCropSelector.select_best_crop(
            scenario=scenario,
            current_hour=10.0,
            time_until_next_slot=3000,  # 50 phút
            is_last_session_today=False
        )
        self.assertLessEqual(sec, 3000)

        # TH2: Phiên cuối cùng trong ngày (chuẩn bị ngủ đêm) -> Phải chọn cây dài ngày (> 4 giờ)
        crop_night, sec_night, rat_night = SmartCropSelector.select_best_crop(
            scenario=scenario,
            current_hour=23.0,
            time_until_next_slot=28800,  # 8 tiếng
            is_last_session_today=True
        )
        self.assertGreaterEqual(sec_night, 14400)  # Ít nhất 4 giờ

    def test_session_task_orchestrator(self):
        """Kiểm tra phân loại phiên và xác suất thị giác thị phần."""
        persona = {"human_identity": {"temperament": "Điềm đạm"}}
        scenario = {"category": "OFFICE_STANDARD", "daily_session_cap": 5, "real_name": "Tester"}

        plan = SessionTaskOrchestrator.determine_session_plan(
            scenario=scenario,
            persona=persona,
            current_hour=12.0,
            session_index_today=1
        )
        self.assertIn(plan["session_type"], ["QUICK_RUSH", "STANDARD", "FULL_MAINTENANCE"])
        # Ruộng đất luôn phải được thực thi (100% thị giác)
        self.assertIn("CROPS", plan["tasks_to_execute"])


if __name__ == "__main__":
    unittest.main()

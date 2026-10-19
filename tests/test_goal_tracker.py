import os
import unittest
import time
from dataclasses import asdict
from scheduler.goal_tracker import (
    GoalTracker,
    SubGoalType,
    GoalStatus,
    TaskResumptionManager,
    TaskCheckpoint
)
from core.evidence_engine import PlotBelief, PlotStateEnum, EnvironmentBeliefState
from scheduler.farm_memory import FarmMemory


class TestGoalTracker(unittest.TestCase):
    """
    Unit test cho Branch 2: Quản trị Mục tiêu nhận thức (ACT-R, Ritter 2019)
    và Phục hồi Tác vụ sau Gián đoạn (Borst CHI 2015, Trafton 2003 Memory for Goals).
    Đảm bảo chạy offline, tất định.
    """

    def setUp(self):
        self.profile_id = "test_profile_actr"
        self.tracker = GoalTracker(profile_id=self.profile_id, macro_goal="FARM_MAINTENANCE_CYCLE")
        self.test_memory_file = "test_farm_memory_goal_tracker.json"
        if os.path.exists(self.test_memory_file):
            os.remove(self.test_memory_file)
        self.memory = FarmMemory(memory_file=self.test_memory_file)

    def tearDown(self):
        if os.path.exists(self.test_memory_file):
            try:
                os.remove(self.test_memory_file)
            except Exception:
                pass

    def test_goal_hierarchy_initialization(self):
        """Khởi tạo cây mục tiêu từ SessionPlan với các SubGoal hợp lệ."""
        tasks = ["CROPS", "TREES", "HONEY"]
        self.tracker.build_goals_from_plan(tasks, total_plots=9)

        goal_names = [sg.name for sg in self.tracker.subgoals]
        self.assertEqual(goal_names[0], SubGoalType.PRE_INSPECTION)
        self.assertIn(SubGoalType.HARVEST_CROPS, goal_names)
        self.assertIn(SubGoalType.SELECT_CROP, goal_names)
        self.assertIn(SubGoalType.PLANT_SEEDS, goal_names)
        self.assertIn(SubGoalType.CHOP_TREES, goal_names)
        self.assertIn(SubGoalType.HARVEST_HONEY, goal_names)
        self.assertEqual(goal_names[-1], SubGoalType.POST_VERIFICATION)

    def test_subgoal_lifecycle_transitions(self):
        """Kiểm tra vòng đời SubGoal: PENDING -> IN_PROGRESS -> COMPLETED."""
        self.tracker.build_goals_from_plan(["CROPS"])
        
        sg = self.tracker.start_subgoal(SubGoalType.PRE_INSPECTION)
        self.assertIsNotNone(sg)
        self.assertEqual(sg.status, GoalStatus.IN_PROGRESS)

        self.tracker.complete_subgoal(SubGoalType.PRE_INSPECTION)
        self.assertEqual(sg.status, GoalStatus.COMPLETED)
        self.assertIsNotNone(sg.completed_at)

    def test_checkpoint_creation_and_interruption(self):
        """Tạo Checkpoint Problem State khi xảy ra gián đoạn giữa chừng."""
        self.tracker.build_goals_from_plan(["CROPS"])
        self.tracker.start_subgoal(SubGoalType.HARVEST_CROPS)
        self.tracker.complete_subgoal(SubGoalType.HARVEST_CROPS)

        self.tracker.start_subgoal(SubGoalType.PLANT_SEEDS)
        self.tracker.interrupt_active_subgoal(reason="BROWSER_CRASH_OR_TIMEOUT")

        ckpt = self.tracker.create_checkpoint(last_action="PLANT_SEEDS", metadata={"selected_crop": "Sunflower"})
        self.assertEqual(ckpt.profile_id, self.profile_id)
        self.assertEqual(ckpt.active_subgoal, SubGoalType.PLANT_SEEDS.value)
        self.assertIn(SubGoalType.HARVEST_CROPS.value, ckpt.completed_subgoals)
        self.assertEqual(ckpt.metadata["selected_crop"], "Sunflower")

    def test_resumption_partial_planting(self):
        """Khi bị ngắt lúc gieo hạt, đối chiếu và chỉ gieo nốt các ô đất EMPTY thực tế."""
        checkpoint_data = {
            "profile_id": self.profile_id,
            "active_subgoal": SubGoalType.PLANT_SEEDS.value,
            "metadata": {"selected_crop": "Pumpkin"}
        }

        # Thực tế quan sát: ô 0 đã có cây, ô 1 và 2 vẫn trống
        observed_plots = [
            PlotBelief(0, (100, 200), {"GROWING": 0.9}, PlotStateEnum.GROWING, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"]),
            PlotBelief(2, (200, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"])
        ]
        belief = EnvironmentBeliefState(time.time(), observed_plots, overall_confidence=0.9)

        resumption = TaskResumptionManager.reconcile_interrupted_session(checkpoint_data, belief)
        self.assertEqual(resumption["resumption_mode"], "RESUME_PARTIAL_PLANTING")
        self.assertEqual(resumption["target_plots"], [1, 2])
        self.assertEqual(resumption["crop_name"], "Pumpkin")

    def test_resumption_partial_harvest(self):
        """Khi bị ngắt lúc thu hoạch, chỉ thu hoạch nốt các ô READY thực tế."""
        checkpoint_data = {
            "profile_id": self.profile_id,
            "active_subgoal": SubGoalType.HARVEST_CROPS.value
        }

        # Thực tế quan sát: ô 0 đã được gặt (EMPTY), ô 1 còn READY
        observed_plots = [
            PlotBelief(0, (100, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"READY": 0.9}, PlotStateEnum.READY, 0.9, ["LOCAL"])
        ]
        belief = EnvironmentBeliefState(time.time(), observed_plots, overall_confidence=0.9)

        resumption = TaskResumptionManager.reconcile_interrupted_session(checkpoint_data, belief)
        self.assertEqual(resumption["resumption_mode"], "RESUME_PARTIAL_HARVEST")
        self.assertEqual(resumption["target_plots"], [1])

    def test_resumption_advance_to_verification_if_all_growing(self):
        """Nếu toàn bộ ruộng đã được gieo đầy đủ, chuyển thẳng sang bước hậu kiểm."""
        checkpoint_data = {
            "profile_id": self.profile_id,
            "active_subgoal": SubGoalType.PLANT_SEEDS.value
        }

        observed_plots = [
            PlotBelief(0, (100, 200), {"GROWING": 0.9}, PlotStateEnum.GROWING, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"GROWING": 0.9}, PlotStateEnum.GROWING, 0.9, ["LOCAL"])
        ]
        belief = EnvironmentBeliefState(time.time(), observed_plots, overall_confidence=0.9)

        resumption = TaskResumptionManager.reconcile_interrupted_session(checkpoint_data, belief)
        self.assertEqual(resumption["resumption_mode"], "ADVANCE_TO_VERIFICATION")

    def test_farm_memory_atomic_checkpoint_persistence(self):
        """Kiểm tra lưu trữ, đọc lại và dọn sạch checkpoint an toàn trên FarmMemory."""
        self.tracker.build_goals_from_plan(["CROPS"])
        self.tracker.start_subgoal(SubGoalType.HARVEST_CROPS)
        ckpt = self.tracker.create_checkpoint(last_action="HARVEST_CROPS", metadata={"session_id": "test_123"})

        # Lưu checkpoint
        self.memory.save_checkpoint(self.profile_id, asdict(ckpt))

        # Đọc lại checkpoint
        loaded = self.memory.get_checkpoint(self.profile_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["profile_id"], self.profile_id)
        self.assertEqual(loaded["last_verified_action"], "HARVEST_CROPS")
        self.assertEqual(loaded["metadata"]["session_id"], "test_123")

        # Xóa checkpoint sau khi hoàn thành phiên
        self.memory.clear_checkpoint(self.profile_id)
        cleared = self.memory.get_checkpoint(self.profile_id)
        self.assertIsNone(cleared)


if __name__ == "__main__":
    unittest.main()

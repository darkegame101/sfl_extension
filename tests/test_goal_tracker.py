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

    def test_sequential_lifecycle_and_active_index(self):
        """Luồng tuần tự thành công: active_index tăng chính xác và đạt len(subgoals) khi hoàn thành."""
        self.tracker.build_goals_from_plan(["CROPS"])
        total = len(self.tracker.subgoals)
        self.assertEqual(total, 5)
        self.assertEqual(self.tracker.active_index, 0)

        # 1. PRE_INSPECTION
        sg = self.tracker.start_subgoal(SubGoalType.PRE_INSPECTION)
        self.assertEqual(self.tracker.active_index, 0)
        self.assertEqual(sg.status, GoalStatus.IN_PROGRESS)
        self.tracker.complete_subgoal(SubGoalType.PRE_INSPECTION)
        self.assertEqual(self.tracker.active_index, 1)
        self.assertEqual(self.tracker.current_subgoal.name, SubGoalType.HARVEST_CROPS)

        # 2. HARVEST_CROPS
        self.tracker.start_subgoal(SubGoalType.HARVEST_CROPS)
        self.assertEqual(self.tracker.active_index, 1)
        self.tracker.complete_subgoal(SubGoalType.HARVEST_CROPS)
        self.assertEqual(self.tracker.active_index, 2)
        self.assertEqual(self.tracker.current_subgoal.name, SubGoalType.SELECT_CROP)

        # 3. SELECT_CROP
        self.tracker.start_subgoal(SubGoalType.SELECT_CROP)
        self.assertEqual(self.tracker.active_index, 2)
        self.tracker.complete_subgoal(SubGoalType.SELECT_CROP)
        self.assertEqual(self.tracker.active_index, 3)
        self.assertEqual(self.tracker.current_subgoal.name, SubGoalType.PLANT_SEEDS)

        # 4. PLANT_SEEDS
        self.tracker.start_subgoal(SubGoalType.PLANT_SEEDS)
        self.assertEqual(self.tracker.active_index, 3)
        self.tracker.complete_subgoal(SubGoalType.PLANT_SEEDS)
        self.assertEqual(self.tracker.active_index, 4)
        self.assertEqual(self.tracker.current_subgoal.name, SubGoalType.POST_VERIFICATION)

        # 5. POST_VERIFICATION
        self.tracker.start_subgoal(SubGoalType.POST_VERIFICATION)
        self.assertEqual(self.tracker.active_index, 4)
        self.tracker.complete_subgoal(SubGoalType.POST_VERIFICATION)
        self.assertEqual(self.tracker.active_index, total)
        self.assertIsNone(self.tracker.current_subgoal)

    def test_out_of_order_completion_preserves_running_target(self):
        """Hoàn thành ngoài thứ tự khi có subgoal đang chạy không được làm lệch active_index."""
        self.tracker.build_goals_from_plan(["CROPS"])
        # Bắt đầu mục tiêu index 3 (PLANT_SEEDS)
        self.tracker.start_subgoal(SubGoalType.PLANT_SEEDS)
        self.assertEqual(self.tracker.active_index, 3)
        self.assertEqual(self.tracker.current_subgoal.name, SubGoalType.PLANT_SEEDS)

        # Hoàn thành ngoài thứ tự PRE_INSPECTION (index 0)
        completed = self.tracker.complete_subgoal(SubGoalType.PRE_INSPECTION)
        self.assertTrue(completed)
        self.assertEqual(self.tracker.active_index, 3)
        self.assertEqual(self.tracker.current_subgoal.name, SubGoalType.PLANT_SEEDS)

        # Hoàn thành ngoài thứ tự SELECT_CROP (index 2)
        completed = self.tracker.complete_subgoal(SubGoalType.SELECT_CROP)
        self.assertTrue(completed)
        self.assertEqual(self.tracker.active_index, 3)
        self.assertEqual(self.tracker.current_subgoal.name, SubGoalType.PLANT_SEEDS)

        # Hoàn thành chính mục tiêu đang chạy (PLANT_SEEDS)
        self.tracker.complete_subgoal(SubGoalType.PLANT_SEEDS)
        # Mục tiêu tiếp theo chưa xong là POST_VERIFICATION (index 4)
        self.assertEqual(self.tracker.active_index, 4)
        self.assertEqual(self.tracker.current_subgoal.name, SubGoalType.POST_VERIFICATION)

    def test_out_of_order_completion_idle_advancement(self):
        """Hoàn thành ngoài thứ tự khi idle: không nhảy lùi, và khi hoàn thành mục tiêu trước sẽ nhảy cóc qua mục tiêu đã xong."""
        self.tracker.build_goals_from_plan(["CROPS"])
        self.assertEqual(self.tracker.active_index, 0)

        # Hoàn thành trước SELECT_CROP (index 2) khi chưa chạy gì
        self.tracker.complete_subgoal(SubGoalType.SELECT_CROP)
        # active_index vẫn giữ nguyên trỏ vào mục tiêu PENDING đầu tiên (index 0: PRE_INSPECTION)
        self.assertEqual(self.tracker.active_index, 0)

        # Hoàn thành PRE_INSPECTION (index 0)
        self.tracker.complete_subgoal(SubGoalType.PRE_INSPECTION)
        self.assertEqual(self.tracker.active_index, 1)

        # Hoàn thành HARVEST_CROPS (index 1) -> vì SELECT_CROP (index 2) đã xong, phải nhảy cóc sang PLANT_SEEDS (index 3)
        self.tracker.complete_subgoal(SubGoalType.HARVEST_CROPS)
        self.assertEqual(self.tracker.active_index, 3)
        self.assertEqual(self.tracker.current_subgoal.name, SubGoalType.PLANT_SEEDS)

    def test_skip_and_fail_subgoal_records_reason_and_status(self):
        """Ghi nhận chính xác FAILED và SKIPPED với lý do và metadata, active_index đồng bộ đúng."""
        self.tracker.build_goals_from_plan(["CROPS", "TREES"])

        # Bắt đầu CHOP_TREES rồi đánh dấu FAILED
        sg_tree = self.tracker.start_subgoal(SubGoalType.CHOP_TREES)
        self.assertIsNotNone(sg_tree)
        failed = self.tracker.fail_subgoal(
            SubGoalType.CHOP_TREES,
            error_message="AXE_DEPLETED",
            metadata={"tool": "axe"}
        )
        self.assertTrue(failed)
        self.assertEqual(sg_tree.status, GoalStatus.FAILED)
        self.assertEqual(sg_tree.error_message, "AXE_DEPLETED")
        self.assertEqual(sg_tree.metadata["tool"], "axe")
        self.assertIsNotNone(sg_tree.completed_at)

        # Bỏ qua một mục tiêu chưa chạy (SKIPPED)
        skipped = self.tracker.skip_subgoal(
            SubGoalType.PRE_INSPECTION,
            reason="WEATHER_TOO_FOGGY",
            metadata={"weather": "fog"}
        )
        self.assertTrue(skipped)
        sg_pre = self.tracker.subgoals[0]
        self.assertEqual(sg_pre.status, GoalStatus.SKIPPED)
        self.assertEqual(sg_pre.error_message, "WEATHER_TOO_FOGGY")
        self.assertEqual(sg_pre.metadata["weather"], "fog")

    def test_interruption_preserves_active_index_for_resumption(self):
        """Gián đoạn (INTERRUPTED) bảo toàn active_index để Checkpoint và Resumption xác định đúng mục tiêu dở dang."""
        self.tracker.build_goals_from_plan(["CROPS"])
        self.tracker.start_subgoal(SubGoalType.HARVEST_CROPS)
        self.assertEqual(self.tracker.active_index, 1)

        interrupted = self.tracker.interrupt_active_subgoal(reason="NETWORK_DROP")
        self.assertIsNotNone(interrupted)
        self.assertEqual(interrupted.status, GoalStatus.INTERRUPTED)
        self.assertEqual(interrupted.error_message, "NETWORK_DROP")
        # active_index vẫn trỏ tới HARVEST_CROPS (index 1)
        self.assertEqual(self.tracker.active_index, 1)

        ckpt = self.tracker.create_checkpoint()
        self.assertEqual(ckpt.active_subgoal, SubGoalType.HARVEST_CROPS.value)

    def test_invalid_state_transitions_rejected(self):
        """Từ chối các chuyển trạng thái không hợp lệ trong ma trận trạng thái."""
        self.tracker.build_goals_from_plan(["CROPS"])

        # Hoàn thành PRE_INSPECTION
        self.tracker.start_subgoal(SubGoalType.PRE_INSPECTION)
        self.tracker.complete_subgoal(SubGoalType.PRE_INSPECTION)

        # Không thể start lại một subgoal đã COMPLETED
        res_start = self.tracker.start_subgoal(SubGoalType.PRE_INSPECTION)
        self.assertIsNone(res_start)

        # Không thể fail một subgoal đã COMPLETED
        res_fail = self.tracker.fail_subgoal(SubGoalType.PRE_INSPECTION, "CANNOT_FAIL_COMPLETED")
        self.assertFalse(res_fail)

        # Không thể skip một subgoal đã COMPLETED
        res_skip = self.tracker.skip_subgoal(SubGoalType.PRE_INSPECTION, "CANNOT_SKIP_COMPLETED")
        self.assertFalse(res_skip)

        # SubGoal không có trong plan trả về False
        res_none = self.tracker.complete_subgoal(SubGoalType.HARVEST_HONEY)
        self.assertFalse(res_none)

    def test_active_index_always_bounded(self):
        """active_index luôn nằm trong phạm vi an toàn [0, len(subgoals)]."""
        # Case 1: Tracker rỗng
        empty_tracker = GoalTracker("empty_pid")
        self.assertEqual(empty_tracker.active_index, 0)
        self.assertIsNone(empty_tracker.current_subgoal)

        # Case 2: Hoàn thành toàn bộ rồi gọi tiếp complete_subgoal
        self.tracker.build_goals_from_plan(["CROPS"])
        total = len(self.tracker.subgoals)
        for sg in list(self.tracker.subgoals):
            self.tracker.complete_subgoal(sg.name)

        self.assertEqual(self.tracker.active_index, total)
        self.assertIsNone(self.tracker.current_subgoal)

        # Gọi thêm lần nữa không được tăng quá total
        self.tracker.complete_subgoal(SubGoalType.PRE_INSPECTION)
        self.assertEqual(self.tracker.active_index, total)
        self.assertTrue(0 <= self.tracker.active_index <= total)

    def test_single_active_subgoal_policy(self):
        """Tuân thủ Single Active Subgoal Policy theo mô hình ACT-R Problem State Bottleneck."""
        self.tracker.build_goals_from_plan(["CROPS"])
        sg1 = self.tracker.start_subgoal(SubGoalType.PRE_INSPECTION)
        self.assertEqual(sg1.status, GoalStatus.IN_PROGRESS)

        # Thử khởi chạy subgoal thứ hai mà không ngắt cái trước -> bị từ chối
        sg2 = self.tracker.start_subgoal(SubGoalType.HARVEST_CROPS, auto_interrupt_previous=False)
        self.assertIsNone(sg2)
        self.assertEqual(sg1.status, GoalStatus.IN_PROGRESS)
        self.assertEqual(self.tracker.active_index, 0)

        # Khởi chạy với auto_interrupt_previous=True -> subgoal cũ bị ngắt, subgoal mới bắt đầu
        sg2 = self.tracker.start_subgoal(SubGoalType.HARVEST_CROPS, auto_interrupt_previous=True)
        self.assertIsNotNone(sg2)
        self.assertEqual(sg2.status, GoalStatus.IN_PROGRESS)
        self.assertEqual(sg1.status, GoalStatus.INTERRUPTED)
        self.assertIn("PREEMPTED", sg1.error_message)
        self.assertEqual(self.tracker.active_index, 1)

    def test_checkpoint_distinguishes_attempted_vs_verified(self):
        """Checkpoint phân biệt rõ ràng giữa last_attempted_action và last_verified_action."""
        self.tracker.build_goals_from_plan(["CROPS"])
        self.tracker.start_subgoal(SubGoalType.PLANT_SEEDS)

        # 1. Thao tác mới phát lệnh nhưng chưa hậu kiểm thị giác (is_verified=False)
        ckpt_attempt = self.tracker.create_checkpoint(
            last_action="PLANT_SEEDS",
            is_verified=False,
            metadata={"crop": "Sunflower"}
        )
        self.assertEqual(ckpt_attempt.last_attempted_action, "PLANT_SEEDS")
        self.assertIsNone(ckpt_attempt.last_verified_action)
        self.assertFalse(ckpt_attempt.metadata["verified"])

        # 2. Thao tác đã được hậu kiểm thị giác thành công (is_verified=True)
        ckpt_verified = self.tracker.create_checkpoint(
            last_action="POST_VERIFICATION",
            is_verified=True
        )
        self.assertEqual(ckpt_verified.last_attempted_action, "POST_VERIFICATION")
        self.assertEqual(ckpt_verified.last_verified_action, "POST_VERIFICATION")
        self.assertTrue(ckpt_verified.metadata["verified"])

        # 3. Chỉ định rõ ràng từng trường
        ckpt_explicit = self.tracker.create_checkpoint(
            last_attempted_action="PLANT_SEEDS",
            last_verified_action="HARVEST_CROPS"
        )
        self.assertEqual(ckpt_explicit.last_attempted_action, "PLANT_SEEDS")
        self.assertEqual(ckpt_explicit.last_verified_action, "HARVEST_CROPS")

    def test_legacy_checkpoint_unverified_action_not_treated_as_verified(self):
        """Dữ liệu checkpoint cũ không được diễn giải nhầm lệnh chưa xác minh thành đã xác minh."""
        # Checkpoint cũ khi đang gieo dở thì crash: active_subgoal="PLANT_SEEDS", last_verified_action="PLANT_SEEDS"
        legacy_unverified = {
            "profile_id": self.profile_id,
            "active_subgoal": "PLANT_SEEDS",
            "completed_subgoals": ["PRE_INSPECTION", "HARVEST_CROPS", "SELECT_CROP"],
            "pending_subgoals": ["POST_VERIFICATION"],
            "last_verified_action": "PLANT_SEEDS"
        }
        # Hàm trích xuất an toàn phải nhận diện PLANT_SEEDS chưa xong và trả về None
        verified = TaskResumptionManager.get_verified_action(legacy_unverified)
        self.assertIsNone(verified)

        # Checkpoint cũ đã hoàn thành thật sự (nằm trong completed_subgoals)
        legacy_completed = {
            "profile_id": self.profile_id,
            "active_subgoal": "POST_VERIFICATION",
            "completed_subgoals": ["PRE_INSPECTION", "HARVEST_CROPS"],
            "pending_subgoals": [],
            "last_verified_action": "HARVEST_CROPS"
        }
        verified_legit = TaskResumptionManager.get_verified_action(legacy_completed)
        self.assertEqual(verified_legit, "HARVEST_CROPS")

    def test_commands_issued_state_and_checkpoint(self):
        """Trạng thái COMMANDS_ISSUED biểu thị lệnh đã phát qua OS nhưng chưa xác minh trong game."""
        self.tracker.build_goals_from_plan(["CROPS"])
        self.tracker.start_subgoal(SubGoalType.HARVEST_CROPS)

        # Ghi nhận đã phát lệnh
        issued = self.tracker.record_commands_issued(
            SubGoalType.HARVEST_CROPS,
            metadata={"plots_attempted": 9}
        )
        self.assertTrue(issued)
        self.assertEqual(self.tracker.current_subgoal.status, GoalStatus.COMMANDS_ISSUED)
        self.assertEqual(self.tracker.current_subgoal.metadata["plots_attempted"], 9)
        self.assertEqual(self.tracker.active_index, 1)

        # Gián đoạn khi đang chờ xác minh
        interrupted = self.tracker.interrupt_active_subgoal(reason="WINDOW_CLOSED_BEFORE_VERIFY")
        self.assertIsNotNone(interrupted)
        self.assertEqual(interrupted.status, GoalStatus.INTERRUPTED)
        self.assertEqual(interrupted.error_message, "WINDOW_CLOSED_BEFORE_VERIFY")

    def test_resumption_abstains_when_belief_uncertain_or_abstention_triggered(self):
        """Từ chối khôi phục hoặc hành động mù khi abstention kích hoạt hoặc đa số ô đất UNKNOWN."""
        checkpoint_data = {
            "profile_id": self.profile_id,
            "active_subgoal": SubGoalType.PLANT_SEEDS.value,
            "metadata": {"selected_crop": "Sunflower"}
        }

        # Trường hợp 1: abstention_triggered = True (do xung đột quan sát hoặc tin cậy thấp)
        observed_plots_1 = [
            PlotBelief(0, (100, 200), {"EMPTY": 0.5}, PlotStateEnum.EMPTY, 0.5, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"GROWING": 0.5}, PlotStateEnum.GROWING, 0.5, ["LOCAL"])
        ]
        belief_abstain = EnvironmentBeliefState(
            time.time(),
            observed_plots_1,
            overall_confidence=0.4,
            abstention_triggered=True,
            abstention_reason="EVIDENCE_CONFLICT"
        )
        res_abstain = TaskResumptionManager.reconcile_interrupted_session(checkpoint_data, belief_abstain)
        self.assertEqual(res_abstain["resumption_mode"], "ABSTAIN_UNCERTAIN")
        self.assertTrue(res_abstain.get("uncertain"))

        # Trường hợp 2: Hơn 50% ô đất có trạng thái UNKNOWN
        observed_plots_2 = [
            PlotBelief(0, (100, 200), {"UNKNOWN": 0.9}, PlotStateEnum.UNKNOWN, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"UNKNOWN": 0.9}, PlotStateEnum.UNKNOWN, 0.9, ["LOCAL"]),
            PlotBelief(2, (200, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"])
        ]
        belief_unknown = EnvironmentBeliefState(time.time(), observed_plots_2, overall_confidence=0.7)
        res_unknown = TaskResumptionManager.reconcile_interrupted_session(checkpoint_data, belief_unknown)
        self.assertEqual(res_unknown["resumption_mode"], "ABSTAIN_UNCERTAIN")
        self.assertTrue(res_unknown.get("uncertain"))

    def test_resumption_adaptive_replan_and_advance_to_planting(self):
        """Khôi phục thích ứng khi thực tế môi trường khác với trạng thái gián đoạn."""
        # 1. Đang gieo nhưng thực tế cây đã chín (READY) -> ADAPTIVE_REPLAN
        ckpt_planting = {
            "profile_id": self.profile_id,
            "active_subgoal": SubGoalType.PLANT_SEEDS.value
        }
        plots_ready = [
            PlotBelief(0, (100, 200), {"READY": 0.9}, PlotStateEnum.READY, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"READY": 0.9}, PlotStateEnum.READY, 0.9, ["LOCAL"])
        ]
        belief_ready = EnvironmentBeliefState(time.time(), plots_ready, overall_confidence=0.9)
        plan_replan = TaskResumptionManager.reconcile_interrupted_session(ckpt_planting, belief_ready)
        self.assertEqual(plan_replan["resumption_mode"], "ADAPTIVE_REPLAN")

        # 2. Đang thu hoạch nhưng thực tế các ô đã trống (EMPTY) -> ADVANCE_TO_PLANTING
        ckpt_harvest = {
            "profile_id": self.profile_id,
            "active_subgoal": SubGoalType.HARVEST_CROPS.value
        }
        plots_empty = [
            PlotBelief(0, (100, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"])
        ]
        belief_empty = EnvironmentBeliefState(time.time(), plots_empty, overall_confidence=0.9)
        plan_plant = TaskResumptionManager.reconcile_interrupted_session(ckpt_harvest, belief_empty)
        self.assertEqual(plan_plant["resumption_mode"], "ADVANCE_TO_PLANTING")

        # 3. Đang thu hoạch nhưng thực tế cây đang lớn (GROWING) -> ADAPTIVE_REPLAN
        plots_growing = [
            PlotBelief(0, (100, 200), {"GROWING": 0.9}, PlotStateEnum.GROWING, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"GROWING": 0.9}, PlotStateEnum.GROWING, 0.9, ["LOCAL"])
        ]
        belief_growing = EnvironmentBeliefState(time.time(), plots_growing, overall_confidence=0.9)
        plan_replan_growing = TaskResumptionManager.reconcile_interrupted_session(ckpt_harvest, belief_growing)
        self.assertEqual(plan_replan_growing["resumption_mode"], "ADAPTIVE_REPLAN")

    def test_resumption_after_exception_interrupted_checkpoint(self):
        """Phục hồi sau exception: checkpoint gián đoạn không được xem là đã xác minh và đối chiếu theo quan sát mới."""
        self.tracker.build_goals_from_plan(["CROPS"])
        self.tracker.start_subgoal(SubGoalType.HARVEST_CROPS)
        self.tracker.record_commands_issued(SubGoalType.HARVEST_CROPS)

        # Exception xảy ra
        self.tracker.interrupt_active_subgoal(reason="EXCEPTION: BrowserConnectionError")
        ckpt = self.tracker.create_checkpoint(
            last_attempted_action="HARVEST_CROPS",
            is_verified=False,
            metadata={"error": "BrowserConnectionError"}
        )

        ckpt_dict = asdict(ckpt)
        # last_verified_action phải là None
        self.assertIsNone(ckpt_dict["last_verified_action"])
        self.assertEqual(ckpt_dict["last_attempted_action"], "HARVEST_CROPS")
        self.assertIsNone(TaskResumptionManager.get_verified_action(ckpt_dict))

        # Khi phiên mới mở lại với quan sát thực tế (1 ô READY, 1 ô EMPTY)
        plots_obs = [
            PlotBelief(0, (100, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"READY": 0.9}, PlotStateEnum.READY, 0.9, ["LOCAL"])
        ]
        belief = EnvironmentBeliefState(time.time(), plots_obs, overall_confidence=0.9)
        resumption = TaskResumptionManager.reconcile_interrupted_session(ckpt_dict, belief)
        self.assertEqual(resumption["resumption_mode"], "RESUME_PARTIAL_HARVEST")
        self.assertEqual(resumption["target_plots"], [1])


if __name__ == "__main__":
    unittest.main()

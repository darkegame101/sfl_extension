"""
HỆ THỐNG NHÁNH 2: QUẢN TRỊ MỤC TIÊU, TIẾN ĐỘ & PHỤC HỒI SAU GIÁN ĐOẠN
(GOAL HIERARCHY, TASK RESUMPTION & STATE-AWARE SCHEDULING)

Cơ sở nghiên cứu:
1. ACT-R: A Cognitive Architecture for Modeling Cognition (Ritter et al., WIREs 2019)
   - Phân cấp mục tiêu nhận thức: MacroGoal -> SubGoals -> Operators.
   - Tách biệt rõ ràng giữa Nhận thức (Cognition), Quyết định (Decision) và Vận động (Action).
2. What Makes Interruptions Disruptive? The Problem State Bottleneck (Borst, Taatgen, van Rijn, CHI 2015)
   - Lưu trữ Checkpoint Problem State trước khi chuyển ngữ cảnh hoặc kết thúc phiên.
3. Preparing to Resume an Interrupted Task: Prospective Goal Encoding (Trafton, Altmann et al., 2003)
   - "Memory for Goals": Khi khôi phục phiên (sau crash, timeout, đổi profile), đối chiếu
     trạng thái quan sát thực tế với Checkpoint để phục hồi tác vụ chính xác thay vì chạy lại từ đầu.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import time
from typing import Dict, List, Optional, Tuple, Any
from core.evidence_engine import EnvironmentBeliefState, PlotStateEnum


class GoalStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class SubGoalType(str, Enum):
    PRE_INSPECTION = "PRE_INSPECTION"
    DISMISS_POPUP = "DISMISS_POPUP"
    SOLVE_CAPTCHA = "SOLVE_CAPTCHA"
    HARVEST_CROPS = "HARVEST_CROPS"
    SELECT_CROP = "SELECT_CROP"
    PLANT_SEEDS = "PLANT_SEEDS"
    CHOP_TREES = "CHOP_TREES"
    HARVEST_HONEY = "HARVEST_HONEY"
    MANAGE_COMPOSTER = "MANAGE_COMPOSTER"
    POST_VERIFICATION = "POST_VERIFICATION"


@dataclass
class SubGoal:
    """Mục tiêu thành phần trong cây phân cấp mục tiêu ACT-R."""
    name: SubGoalType
    status: GoalStatus = GoalStatus.PENDING
    target_indices: List[int] = field(default_factory=list)
    completed_indices: List[int] = field(default_factory=list)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class TaskCheckpoint:
    """Bản ghi phục hồi tác vụ khi bị gián đoạn (Trafton & Altmann 2003 Memory for Goals)."""
    checkpoint_id: str
    profile_id: str
    macro_goal: str
    active_subgoal: Optional[str]
    completed_subgoals: List[str]
    pending_subgoals: List[str]
    last_verified_action: Optional[str]
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class GoalTracker:
    """
    Quản lý cây mục tiêu phiên làm việc theo mô hình ACT-R:
    - Khởi tạo cây mục tiêu dựa trên kế hoạch phiên (SessionPlan).
    - Cập nhật tiến độ từng SubGoal.
    - Xuất Checkpoint khi xảy ra gián đoạn hoặc kết thúc phiên.
    """

    def __init__(self, profile_id: str, macro_goal: str = "FARM_MAINTENANCE_CYCLE"):
        self.profile_id = profile_id
        self.macro_goal = macro_goal
        self.subgoals: List[SubGoal] = []
        self.active_index: int = 0
        self.created_at = time.time()

    def build_goals_from_plan(self, tasks_to_execute: List[str], total_plots: int = 9):
        """Khởi tạo danh sách SubGoal tuần tự theo kế hoạch phiên."""
        self.subgoals = [SubGoal(name=SubGoalType.PRE_INSPECTION)]

        if "CROPS" in tasks_to_execute:
            self.subgoals.append(SubGoal(name=SubGoalType.HARVEST_CROPS, target_indices=list(range(total_plots))))
            self.subgoals.append(SubGoal(name=SubGoalType.SELECT_CROP))
            self.subgoals.append(SubGoal(name=SubGoalType.PLANT_SEEDS, target_indices=list(range(total_plots))))

        if "TREES" in tasks_to_execute:
            self.subgoals.append(SubGoal(name=SubGoalType.CHOP_TREES))

        if "HONEY" in tasks_to_execute:
            self.subgoals.append(SubGoal(name=SubGoalType.HARVEST_HONEY))

        if "COMPOSTER" in tasks_to_execute:
            self.subgoals.append(SubGoal(name=SubGoalType.MANAGE_COMPOSTER))

        self.subgoals.append(SubGoal(name=SubGoalType.POST_VERIFICATION))

    @property
    def current_subgoal(self) -> Optional[SubGoal]:
        if 0 <= self.active_index < len(self.subgoals):
            return self.subgoals[self.active_index]
        return None

    def start_subgoal(self, name: SubGoalType) -> Optional[SubGoal]:
        """Bắt đầu thực thi một mục tiêu con."""
        for idx, sg in enumerate(self.subgoals):
            if sg.name == name and sg.status in [GoalStatus.PENDING, GoalStatus.INTERRUPTED]:
                self.active_index = idx
                sg.status = GoalStatus.IN_PROGRESS
                sg.started_at = time.time()
                return sg
        return None

    def complete_subgoal(self, name: SubGoalType, metadata: Dict[str, Any] = None):
        """Đánh dấu một mục tiêu con đã hoàn thành."""
        for sg in self.subgoals:
            if sg.name == name:
                sg.status = GoalStatus.COMPLETED
                sg.completed_at = time.time()
                break
        self.active_index += 1

    def interrupt_active_subgoal(self, reason: str = "SESSION_INTERRUPTED"):
        """Ghi nhận mục tiêu hiện tại bị gián đoạn và tạo Checkpoint."""
        curr = self.current_subgoal
        if curr and curr.status == GoalStatus.IN_PROGRESS:
            curr.status = GoalStatus.INTERRUPTED
            curr.error_message = reason

    def create_checkpoint(self, last_action: Optional[str] = None, metadata: Dict[str, Any] = None) -> TaskCheckpoint:
        """Tạo đối tượng Checkpoint chứa toàn bộ ngữ cảnh cần thiết để khôi phục."""
        curr = self.current_subgoal
        completed = [sg.name.value for sg in self.subgoals if sg.status == GoalStatus.COMPLETED]
        pending = [sg.name.value for sg in self.subgoals if sg.status in [GoalStatus.PENDING, GoalStatus.INTERRUPTED]]

        return TaskCheckpoint(
            checkpoint_id=f"ckpt_{int(time.time()*1000)}",
            profile_id=self.profile_id,
            macro_goal=self.macro_goal,
            active_subgoal=curr.name.value if curr else None,
            completed_subgoals=completed,
            pending_subgoals=pending,
            last_verified_action=last_action,
            created_at=time.time(),
            metadata=metadata or {}
        )


class TaskResumptionManager:
    """
    Bộ điều phối phục hồi tác vụ thông minh (Memory for Goals Reconciler):
    - Đọc Checkpoint lưu trữ từ phiên trước.
    - Đối chiếu Checkpoint với Trạng thái Niềm tin thực tế (BeliefState từ Branch 1).
    - Tạo kế hoạch thích ứng khôi phục:
      + Nếu bị ngắt giữa chừng khi gieo hạt, chỉ gieo nốt các ô EMPTY thực tế, KHÔNG gieo đè ô đã có cây.
      + Nếu bị ngắt khi thu hoạch, kiểm tra ô nào còn READY thì mới hái tiếp.
      + Nếu thực tế khác hoàn toàn checkpoint, tự động điều chỉnh mục tiêu theo thực tế quan sát.
    """

    @classmethod
    def reconcile_interrupted_session(
        cls,
        checkpoint: Optional[Dict[str, Any]],
        observed_belief: EnvironmentBeliefState
    ) -> Dict[str, Any]:
        """
        Đối chiếu Checkpoint phiên trước với quan sát thị giác hiện tại.
        Trả về chiến lược hành động phục hồi (Resumption Action Plan).
        """
        if not checkpoint:
            return {
                "resumption_mode": "FRESH_START",
                "recommended_tasks": ["CROPS"],
                "rationale": "Không có checkpoint gián đoạn, bắt đầu phiên mới tiêu chuẩn"
            }

        active_subgoal = checkpoint.get("active_subgoal")
        meta = checkpoint.get("metadata", {})
        ready_count = observed_belief.ready_plots_count
        empty_count = observed_belief.empty_plots_count
        growing_count = observed_belief.growing_plots_count

        # Tình huống 1: Bị ngắt khi đang gieo hạt (PLANT_SEEDS)
        if active_subgoal == SubGoalType.PLANT_SEEDS.value:
            empty_indices = [
                p.plot_index for p in observed_belief.plots
                if p.most_likely_state == PlotStateEnum.EMPTY
            ]
            if empty_indices:
                return {
                    "resumption_mode": "RESUME_PARTIAL_PLANTING",
                    "target_plots": empty_indices,
                    "crop_name": meta.get("selected_crop", "Sunflower"),
                    "rationale": f"Phục hồi sau gián đoạn gieo hạt: Phát hiện còn {len(empty_indices)} ô đất trống cần gieo nốt, bỏ qua các ô đã có hạt"
                }
            elif growing_count > 0 and empty_count == 0:
                return {
                    "resumption_mode": "ADVANCE_TO_VERIFICATION",
                    "rationale": "Quan sát thực tế cho thấy toàn bộ các ô đất đã có cây đang lớn, chuyển thẳng sang bước hậu kiểm"
                }

        # Tình huống 2: Bị ngắt khi đang thu hoạch (HARVEST_CROPS)
        if active_subgoal == SubGoalType.HARVEST_CROPS.value:
            ready_indices = [
                p.plot_index for p in observed_belief.plots
                if p.most_likely_state == PlotStateEnum.READY
            ]
            if ready_indices:
                return {
                    "resumption_mode": "RESUME_PARTIAL_HARVEST",
                    "target_plots": ready_indices,
                    "rationale": f"Phục hồi sau gián đoạn thu hoạch: Còn {len(ready_indices)} ô đất chín cần hái nốt"
                }

        # Mặc định: Trạng thái môi trường đã thay đổi, hành động theo niềm tin thực tế
        return {
            "resumption_mode": "ADAPTIVE_REPLAN",
            "ready_count": ready_count,
            "empty_count": empty_count,
            "growing_count": growing_count,
            "rationale": "Môi trường thực tế đã thay đổi so với thời điểm gián đoạn, lập kế hoạch hành động thích ứng theo quan sát"
        }

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
    COMMANDS_ISSUED = "COMMANDS_ISSUED"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    SKIPPED = "SKIPPED"


# Bảng ma trận chuyển trạng thái hợp lệ cho SubGoal
VALID_GOAL_TRANSITIONS: Dict[GoalStatus, List[GoalStatus]] = {
    GoalStatus.PENDING: [
        GoalStatus.IN_PROGRESS,
        GoalStatus.COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.SKIPPED,
        GoalStatus.ABORTED,
    ],
    GoalStatus.IN_PROGRESS: [
        GoalStatus.COMMANDS_ISSUED,
        GoalStatus.COMPLETED,
        GoalStatus.INTERRUPTED,
        GoalStatus.FAILED,
        GoalStatus.ABORTED,
        GoalStatus.SKIPPED,
    ],
    GoalStatus.COMMANDS_ISSUED: [
        GoalStatus.COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.INTERRUPTED,
        GoalStatus.ABORTED,
    ],
    GoalStatus.INTERRUPTED: [
        GoalStatus.IN_PROGRESS,
        GoalStatus.COMPLETED,
        GoalStatus.SKIPPED,
        GoalStatus.ABORTED,
        GoalStatus.FAILED,
    ],
    GoalStatus.COMPLETED: [],
    GoalStatus.FAILED: [
        GoalStatus.IN_PROGRESS,  # Cho phép retry
    ],
    GoalStatus.ABORTED: [],
    GoalStatus.SKIPPED: [],
}


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
    metadata: Dict[str, Any] = field(default_factory=dict)


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
    last_attempted_action: Optional[str] = None
    failed_subgoals: List[str] = field(default_factory=list)
    skipped_subgoals: List[str] = field(default_factory=list)


class GoalTracker:
    """
    Quản lý cây mục tiêu phiên làm việc theo mô hình ACT-R:
    - Khởi tạo cây mục tiêu dựa trên kế hoạch phiên (SessionPlan).
    - Cập nhật tiến độ từng SubGoal với chuyển trạng thái có kiểm soát.
    - Duy trì invariant của active_index trong [0, len(subgoals)].
    - Tuân thủ Single Active Subgoal Policy (Problem State Bottleneck, Borst CHI 2015).
    - Xuất Checkpoint khi xảy ra gián đoạn hoặc kết thúc phiên, phân biệt rõ attempted vs verified.
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
        self.active_index = 0

    @property
    def current_subgoal(self) -> Optional[SubGoal]:
        if 0 <= self.active_index < len(self.subgoals):
            return self.subgoals[self.active_index]
        return None

    def get_running_subgoal(self) -> Optional[SubGoal]:
        """Trả về subgoal đang chạy (IN_PROGRESS hoặc COMMANDS_ISSUED) nếu có."""
        for sg in self.subgoals:
            if sg.status in (GoalStatus.IN_PROGRESS, GoalStatus.COMMANDS_ISSUED):
                return sg
        return None

    def _sync_active_index_after_terminal(self, finished_idx: int):
        """
        Đồng bộ active_index khi một subgoal chuyển sang trạng thái kết thúc (COMPLETED/FAILED/SKIPPED/ABORTED):
        1. Nếu có subgoal khác đang chạy (IN_PROGRESS / COMMANDS_ISSUED), active_index trỏ tới nó.
        2. Nếu không có subgoal nào đang chạy:
           - Nếu finished_idx == self.active_index (hoặc current_subgoal đã kết thúc):
             Tìm subgoal PENDING/INTERRUPTED kế tiếp, quét từ finished_idx + 1 đến cuối,
             rồi quét vòng từ 0 đến finished_idx nếu chưa tìm thấy.
           - Nếu finished_idx != self.active_index và current_subgoal vẫn là PENDING/INTERRUPTED:
             Giữ nguyên self.active_index không đổi (out-of-order completion không làm lệch mục tiêu đang chờ).
        3. Nếu toàn bộ đã kết thúc: active_index = len(self.subgoals).
        Luôn đảm bảo: 0 <= self.active_index <= len(self.subgoals).
        """
        # 1. Có mục tiêu đang chạy?
        running = self.get_running_subgoal()
        if running is not None:
            self.active_index = self.subgoals.index(running)
            return

        # 2. Kiểm tra nếu current_subgoal vẫn còn hợp lệ (chưa bắt đầu hoặc bị gián đoạn) và khác finished_idx
        if (
            0 <= self.active_index < len(self.subgoals)
            and self.active_index != finished_idx
            and self.subgoals[self.active_index].status in (GoalStatus.PENDING, GoalStatus.INTERRUPTED)
        ):
            return

        # 3. Quét tìm subgoal PENDING / INTERRUPTED tiếp theo từ finished_idx + 1
        for idx in range(finished_idx + 1, len(self.subgoals)):
            if self.subgoals[idx].status in (GoalStatus.PENDING, GoalStatus.INTERRUPTED):
                self.active_index = idx
                return

        # 4. Quét từ 0 đến finished_idx
        for idx in range(0, min(finished_idx, len(self.subgoals))):
            if self.subgoals[idx].status in (GoalStatus.PENDING, GoalStatus.INTERRUPTED):
                self.active_index = idx
                return

        # 5. Tất cả đã ở trạng thái kết thúc
        self.active_index = len(self.subgoals)

    def start_subgoal(self, name: SubGoalType, auto_interrupt_previous: bool = False) -> Optional[SubGoal]:
        """
        Bắt đầu thực thi một mục tiêu con theo chính sách Problem State Bottleneck (Borst 2015):
        - Tại một thời điểm, chỉ cho phép DUY NHẤT một SubGoal ở trạng thái IN_PROGRESS / COMMANDS_ISSUED.
        - Nếu có subgoal khác đang chạy:
          + Nếu auto_interrupt_previous=False: Từ chối khởi chạy (trả về None).
          + Nếu auto_interrupt_previous=True: Ngắt subgoal cũ trước khi bắt đầu mục tiêu mới.
        """
        target_idx = None
        target_sg = None
        for idx, sg in enumerate(self.subgoals):
            if sg.name == name:
                target_idx = idx
                target_sg = sg
                break

        if target_sg is None:
            return None

        # Kiểm tra chuyển trạng thái hợp lệ
        if GoalStatus.IN_PROGRESS not in VALID_GOAL_TRANSITIONS.get(target_sg.status, []):
            return None

        # Kiểm tra subgoal đang chạy khác
        running = self.get_running_subgoal()
        if running is not None and running is not target_sg:
            if not auto_interrupt_previous:
                return None
            running.status = GoalStatus.INTERRUPTED
            running.error_message = f"PREEMPTED_BY_{name.value if isinstance(name, SubGoalType) else name}"

        self.active_index = target_idx
        target_sg.status = GoalStatus.IN_PROGRESS
        target_sg.started_at = time.time()
        return target_sg

    def complete_subgoal(self, name: SubGoalType, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Đánh dấu một mục tiêu con đã hoàn thành và đồng bộ active_index:
        - Không tăng active_index vô điều kiện.
        - Hoàn thành ngoài thứ tự không làm lệch mục tiêu đang thực thi.
        - active_index luôn nằm trong [0, len(subgoals)].
        """
        target_idx = None
        target_sg = None
        for idx, sg in enumerate(self.subgoals):
            if sg.name == name:
                target_idx = idx
                target_sg = sg
                break

        if target_sg is None:
            return False

        if GoalStatus.COMPLETED not in VALID_GOAL_TRANSITIONS.get(target_sg.status, []):
            return False

        target_sg.status = GoalStatus.COMPLETED
        target_sg.completed_at = time.time()
        if metadata:
            target_sg.metadata.update(metadata)

        self._sync_active_index_after_terminal(target_idx)
        return True

    def fail_subgoal(
        self,
        name: SubGoalType,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Ghi nhận mục tiêu con thất bại với lý do cụ thể và đồng bộ active_index.
        """
        target_idx = None
        target_sg = None
        for idx, sg in enumerate(self.subgoals):
            if sg.name == name:
                target_idx = idx
                target_sg = sg
                break

        if target_sg is None:
            return False

        if GoalStatus.FAILED not in VALID_GOAL_TRANSITIONS.get(target_sg.status, []):
            return False

        target_sg.status = GoalStatus.FAILED
        target_sg.completed_at = time.time()
        target_sg.error_message = error_message
        if metadata:
            target_sg.metadata.update(metadata)

        self._sync_active_index_after_terminal(target_idx)
        return True

    def skip_subgoal(
        self,
        name: SubGoalType,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Bỏ qua một mục tiêu con với lý do cụ thể và đồng bộ active_index.
        """
        target_idx = None
        target_sg = None
        for idx, sg in enumerate(self.subgoals):
            if sg.name == name:
                target_idx = idx
                target_sg = sg
                break

        if target_sg is None:
            return False

        if GoalStatus.SKIPPED not in VALID_GOAL_TRANSITIONS.get(target_sg.status, []):
            return False

        target_sg.status = GoalStatus.SKIPPED
        target_sg.completed_at = time.time()
        target_sg.error_message = reason
        if metadata:
            target_sg.metadata.update(metadata)

        self._sync_active_index_after_terminal(target_idx)
        return True

    def abort_subgoal(self, name: SubGoalType, reason: Optional[str] = None) -> bool:
        """Huỷ bỏ hoàn toàn một mục tiêu con."""
        target_idx = None
        target_sg = None
        for idx, sg in enumerate(self.subgoals):
            if sg.name == name:
                target_idx = idx
                target_sg = sg
                break

        if target_sg is None:
            return False

        if GoalStatus.ABORTED not in VALID_GOAL_TRANSITIONS.get(target_sg.status, []):
            return False

        target_sg.status = GoalStatus.ABORTED
        target_sg.completed_at = time.time()
        target_sg.error_message = reason
        self._sync_active_index_after_terminal(target_idx)
        return True

    def record_commands_issued(self, name: SubGoalType, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Ghi nhận lệnh thao tác (chuột/phím) đã được phát cho mục tiêu con nhưng chưa hậu kiểm thị giác.
        Chuyển trạng thái từ IN_PROGRESS -> COMMANDS_ISSUED.
        active_index giữ nguyên trỏ tới subgoal này.
        """
        target_idx = None
        target_sg = None
        for idx, sg in enumerate(self.subgoals):
            if sg.name == name:
                target_idx = idx
                target_sg = sg
                break

        if target_sg is None:
            return False

        if GoalStatus.COMMANDS_ISSUED not in VALID_GOAL_TRANSITIONS.get(target_sg.status, []):
            return False

        target_sg.status = GoalStatus.COMMANDS_ISSUED
        if metadata:
            target_sg.metadata.update(metadata)
        self.active_index = target_idx
        return True

    def interrupt_active_subgoal(self, reason: str = "SESSION_INTERRUPTED") -> Optional[SubGoal]:
        """Ghi nhận mục tiêu hiện tại bị gián đoạn và bảo toàn active_index cho checkpoint."""
        curr = self.get_running_subgoal() or self.current_subgoal
        if curr and curr.status in (GoalStatus.IN_PROGRESS, GoalStatus.COMMANDS_ISSUED):
            curr.status = GoalStatus.INTERRUPTED
            curr.error_message = reason
            self.active_index = self.subgoals.index(curr)
            return curr
        return None

    def create_checkpoint(
        self,
        last_action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        last_verified_action: Optional[str] = None,
        last_attempted_action: Optional[str] = None,
        is_verified: Optional[bool] = None
    ) -> TaskCheckpoint:
        """
        Tạo đối tượng Checkpoint chứa toàn bộ ngữ cảnh cần thiết để khôi phục:
        - Phân biệt rõ ràng giữa last_attempted_action và last_verified_action.
        - Giữ nguyên tham số vị trí cũ (last_action, metadata) để tương thích 100% với caller hiện có.
        - Nếu is_verified=False: last_verified_action sẽ là None, tránh hiểu nhầm thao tác phát lệnh là đã thành công.
        """
        curr = self.current_subgoal
        completed = [sg.name.value for sg in self.subgoals if sg.status == GoalStatus.COMPLETED]
        pending = [sg.name.value for sg in self.subgoals if sg.status in (GoalStatus.PENDING, GoalStatus.INTERRUPTED)]
        failed = [sg.name.value for sg in self.subgoals if sg.status == GoalStatus.FAILED]
        skipped = [sg.name.value for sg in self.subgoals if sg.status == GoalStatus.SKIPPED]

        meta = dict(metadata or {})
        attempted = last_attempted_action or last_action

        if last_verified_action is not None:
            verified = last_verified_action
            meta["verified"] = True
        elif is_verified is True:
            verified = last_action
            meta["verified"] = True
        elif is_verified is False:
            verified = None
            meta["verified"] = False
        else:
            # Caller cũ gọi create_checkpoint(last_action="...") mà không truyền is_verified.
            # Để bảo toàn tương thích ngược cho các test/caller cũ, gán last_verified_action = last_action,
            # nhưng lưu ý rằng các hàm phục hồi (TaskResumptionManager.get_verified_action)
            # sẽ kiểm tra chéo với completed_subgoals để không diễn giải nhầm lệnh chưa xác minh thành đã xác minh.
            verified = last_action

        return TaskCheckpoint(
            checkpoint_id=f"ckpt_{int(time.time()*1000)}",
            profile_id=self.profile_id,
            macro_goal=self.macro_goal,
            active_subgoal=curr.name.value if curr else None,
            completed_subgoals=completed,
            pending_subgoals=pending,
            last_verified_action=verified,
            created_at=time.time(),
            metadata=meta,
            last_attempted_action=attempted,
            failed_subgoals=failed,
            skipped_subgoals=skipped,
        )


class TaskResumptionManager:
    """
    Bộ điều phối phục hồi tác vụ thông minh (Memory for Goals Reconciler):
    - Đọc Checkpoint lưu trữ từ phiên trước.
    - Đối chiếu Checkpoint với Trạng thái Niềm tin thực tế (BeliefState từ Branch 1).
    - Phân biệt hành động đã thực sự xác minh vs hành động mới phát lệnh.
    - Tạo kế hoạch thích ứng khôi phục:
      + Nếu bị ngắt giữa chừng khi gieo hạt, chỉ gieo nốt các ô EMPTY thực tế, KHÔNG gieo đè ô đã có cây.
      + Nếu bị ngắt khi thu hoạch, kiểm tra ô nào còn READY thì mới hái tiếp.
      + Nếu thực tế khác hoàn toàn checkpoint, tự động điều chỉnh mục tiêu theo thực tế quan sát.
    """

    @staticmethod
    def get_verified_action(checkpoint: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Trích xuất hành động đã thực sự được xác minh từ checkpoint một cách an toàn:
        - Nếu checkpoint có cờ metadata['verified'] is False -> trả về None.
        - Với checkpoint có cả last_attempted_action và last_verified_action:
          trả về last_verified_action (có thể là None nếu chưa xác minh).
        - Xử lý an toàn dữ liệu checkpoint cũ:
          Nếu last_verified_action trùng với active_subgoal nhưng active_subgoal KHÔNG nằm trong
          completed_subgoals, đây chỉ là lệnh vừa phát trước khi bị ngắt, CHƯA được xác minh -> trả về None.
        """
        if not checkpoint:
            return None

        meta = checkpoint.get("metadata", {})
        if meta.get("verified") is False:
            return None

        last_verified = checkpoint.get("last_verified_action")
        if not last_verified:
            return None

        # Checkpoint mới có trường last_attempted_action rõ ràng
        if "last_attempted_action" in checkpoint:
            return last_verified

        # Checkpoint cũ: phòng ngừa gán nhầm action đang dở dang thành đã xác minh
        active_sg = checkpoint.get("active_subgoal")
        completed = checkpoint.get("completed_subgoals", [])
        if active_sg == last_verified and active_sg not in completed:
            return None

        return last_verified

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
            if getattr(observed_belief, "abstention_triggered", False) and not (
                getattr(observed_belief, "has_captcha", False) or getattr(observed_belief, "is_syncing", False)
            ):
                return {
                    "resumption_mode": "ABSTAIN_UNCERTAIN",
                    "recommended_tasks": [],
                    "uncertain": True,
                    "rationale": f"Từ chối hành động do quan sát môi trường không chắc chắn: {observed_belief.abstention_reason or 'Độ tin cậy thấp'}"
                }
            return {
                "resumption_mode": "FRESH_START",
                "recommended_tasks": ["CROPS"],
                "rationale": "Không có checkpoint gián đoạn, bắt đầu phiên mới tiêu chuẩn"
            }

        # 1. Kiểm tra chính sách từ chối hành động nếu quan sát thiếu độ tin cậy hoặc xung đột
        if getattr(observed_belief, "abstention_triggered", False) and not (
            getattr(observed_belief, "has_captcha", False) or getattr(observed_belief, "is_syncing", False)
        ):
            return {
                "resumption_mode": "ABSTAIN_UNCERTAIN",
                "uncertain": True,
                "rationale": f"Từ chối khôi phục do môi trường không chắc chắn: {observed_belief.abstention_reason or 'Độ tin cậy thấp hoặc xung đột quan sát'}"
            }

        # 2. Kiểm tra tỷ lệ ô đất UNKNOWN: nếu > 50% số ô không xác định được trạng thái tin cậy, không đoán mù
        total_plots = len(observed_belief.plots)
        if total_plots > 0 and (observed_belief.unknown_plots_count / total_plots) > 0.5:
            return {
                "resumption_mode": "ABSTAIN_UNCERTAIN",
                "uncertain": True,
                "unknown_count": observed_belief.unknown_plots_count,
                "total_plots": total_plots,
                "rationale": f"Hơn 50% ô đất có trạng thái UNKNOWN ({observed_belief.unknown_plots_count}/{total_plots}), dừng lại để quan sát lại thay vì thao tác mù"
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
                if p.most_likely_state == PlotStateEnum.EMPTY and getattr(p, "confidence", 1.0) >= 0.60
            ]
            if empty_indices:
                return {
                    "resumption_mode": "RESUME_PARTIAL_PLANTING",
                    "target_plots": empty_indices,
                    "crop_name": meta.get("selected_crop", "Sunflower"),
                    "rationale": f"Phục hồi sau gián đoạn gieo hạt: Phát hiện còn {len(empty_indices)} ô đất trống tin cậy cần gieo nốt, bỏ qua các ô đã có hạt"
                }
            elif growing_count > 0 and empty_count == 0:
                return {
                    "resumption_mode": "ADVANCE_TO_VERIFICATION",
                    "rationale": "Quan sát thực tế cho thấy toàn bộ các ô đất đã có cây đang lớn, chuyển thẳng sang bước hậu kiểm"
                }
            elif ready_count > 0 and empty_count == 0:
                return {
                    "resumption_mode": "ADAPTIVE_REPLAN",
                    "ready_count": ready_count,
                    "empty_count": empty_count,
                    "rationale": "Quan sát thực tế cho thấy cây đã chín thay vì đất trống, chuyển sang thu hoạch theo quan sát thực tế"
                }

        # Tình huống 2: Bị ngắt khi đang thu hoạch (HARVEST_CROPS)
        if active_subgoal == SubGoalType.HARVEST_CROPS.value:
            ready_indices = [
                p.plot_index for p in observed_belief.plots
                if p.most_likely_state == PlotStateEnum.READY and getattr(p, "confidence", 1.0) >= 0.60
            ]
            if ready_indices:
                return {
                    "resumption_mode": "RESUME_PARTIAL_HARVEST",
                    "target_plots": ready_indices,
                    "rationale": f"Phục hồi sau gián đoạn thu hoạch: Còn {len(ready_indices)} ô đất chín tin cậy cần hái nốt"
                }
            elif empty_count > 0 and ready_count == 0:
                return {
                    "resumption_mode": "ADVANCE_TO_PLANTING",
                    "rationale": "Thu hoạch đã hoàn tất trước đó (các ô đều là đất trống), chuyển sang gieo hạt"
                }
            elif growing_count > 0 and ready_count == 0:
                return {
                    "resumption_mode": "ADAPTIVE_REPLAN",
                    "growing_count": growing_count,
                    "ready_count": ready_count,
                    "rationale": "Cây trồng đang trong giai đoạn phát triển, không cần thu hoạch thêm"
                }

        # Tình huống 3: Bị ngắt khi đang chặt cây (CHOP_TREES)
        if active_subgoal == SubGoalType.CHOP_TREES.value:
            return {
                "resumption_mode": "RESUME_CHOP_TREES",
                "rationale": "Phục hồi sau gián đoạn chặt cây: Yêu cầu kiểm tra lại trạng thái cây gỗ trước khi thao tác"
            }

        # Mặc định: Trạng thái môi trường đã thay đổi, hành động theo niềm tin thực tế
        return {
            "resumption_mode": "ADAPTIVE_REPLAN",
            "ready_count": ready_count,
            "empty_count": empty_count,
            "growing_count": growing_count,
            "unknown_count": observed_belief.unknown_plots_count,
            "rationale": "Môi trường thực tế đã thay đổi so với thời điểm gián đoạn, lập kế hoạch hành động thích ứng theo quan sát"
        }

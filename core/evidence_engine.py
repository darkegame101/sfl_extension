"""
HỆ THỐNG NHÁNH 1: QUYẾT ĐỊNH DỰA TRÊN BẰNG CHỨNG & HẬU KIỂM VÒNG LẶP ĐÓNG
(EVIDENCE-BASED DECISION & CLOSED-LOOP VERIFICATION)

Cơ sở nghiên cứu:
1. Partially Observable Markov Decision Processes (POMDP) in Robotics (Hanna Kurniawati, Annual Review 2022)
   - Duy trì Trạng thái Niềm tin (Belief State) phân phối xác suất p(s) thay vì giả định nhị phân.
   - Cơ chế từ chối phán đoán (Abstention Policy) khi độ tin cậy < ngưỡng hoặc có bất đồng bằng chứng.
2. OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks (Xie et al., NeurIPS 2024)
   - Tiêu chí đánh giá hành động bằng vị từ tiền điều kiện (Pre-conditions) và hậu điều kiện (Post-conditions)
     có thể kiểm chứng khách quan trên màn hình.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


class PlotStateEnum(str, Enum):
    GROWING = "GROWING"
    READY = "READY"
    EMPTY = "EMPTY"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


class VerificationStatus(str, Enum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_PARTIAL = "VERIFIED_PARTIAL"
    VERIFIED_FAILED = "VERIFIED_FAILED"
    ABSTAIN_UNCERTAIN = "ABSTAIN_UNCERTAIN"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class PlotBelief:
    """Biểu diễn trạng thái niềm tin (POMDP Belief) của một ô đất cụ thể."""
    plot_index: int
    coordinates: Tuple[int, int]
    probabilities: Dict[str, float]  # {GROWING: 0.1, READY: 0.8, EMPTY: 0.05, UNKNOWN: 0.05}
    most_likely_state: PlotStateEnum
    confidence: float
    sources: List[str] = field(default_factory=list)  # ["LOCAL_VISION", "VLM"]
    evidence_agreement: float = 1.0  # 1.0 = đồng thuận cao, <0.5 = xung đột


@dataclass
class EnvironmentBeliefState:
    """Trạng thái niềm tin toàn cảnh của môi trường nông trại tại thời điểm t."""
    timestamp: float
    plots: List[PlotBelief]
    has_blocking_popup: bool = False
    popup_close_button: Optional[Tuple[int, int]] = None
    is_syncing: bool = False
    has_captcha: bool = False
    has_mushrooms: bool = False
    mushroom_positions: List[Tuple[int, int]] = field(default_factory=list)
    overall_confidence: float = 1.0
    abstention_triggered: bool = False
    abstention_reason: Optional[str] = None

    @property
    def ready_plots_count(self) -> int:
        return sum(1 for p in self.plots if p.most_likely_state == PlotStateEnum.READY and p.confidence >= 0.60)

    @property
    def empty_plots_count(self) -> int:
        return sum(1 for p in self.plots if p.most_likely_state == PlotStateEnum.EMPTY and p.confidence >= 0.60)

    @property
    def growing_plots_count(self) -> int:
        return sum(1 for p in self.plots if p.most_likely_state == PlotStateEnum.GROWING and p.confidence >= 0.60)

    @property
    def unknown_plots_count(self) -> int:
        return sum(1 for p in self.plots if p.most_likely_state == PlotStateEnum.UNKNOWN or p.confidence < 0.60)


class EvidenceFuser:
    """
    Hợp nhất bằng chứng đa nguồn (Local Vision Heuristic + VLM Perception).
    Áp dụng chính sách Abstention (Kurniawati 2022) khi thiếu bằng chứng hoặc xung đột.
    """

    CONFIDENCE_THRESHOLD = 0.65  # Ngưỡng tin cậy tối thiểu để hành động
    CONFLICT_PENALTY = 0.35      # Giảm trừ tin cậy khi 2 nguồn quan sát bất đồng

    @classmethod
    def fuse_plot_observations(
        cls,
        plot_index: int,
        coords: Tuple[int, int],
        local_obs: Optional[Dict[str, Any]],
        vlm_plots_summary: Optional[Dict[str, Any]] = None
    ) -> PlotBelief:
        """
        Hợp nhất quan sát ô đất từ LocalVision (HSV/OpenCV) và VLM (Claude Vision).
        Trả về phân phối xác suất và độ tin cậy được hiệu chuẩn.
        """
        probs = {
            PlotStateEnum.GROWING.value: 0.05,
            PlotStateEnum.READY.value: 0.05,
            PlotStateEnum.EMPTY.value: 0.05,
            PlotStateEnum.UNKNOWN.value: 0.85
        }
        sources = []
        agreement = 1.0

        local_state = local_obs.get("state", "UNKNOWN") if local_obs else "UNKNOWN"
        local_conf = float(local_obs.get("confidence", 0.5)) if local_obs else 0.5
        if local_obs:
            sources.append("LOCAL_VISION")

        # Khởi tạo xác suất từ Local Vision
        if local_state in probs:
            probs[local_state] = local_conf
            rem = max(0.0, 1.0 - local_conf)
            other_keys = [k for k in probs if k != local_state]
            for k in other_keys:
                probs[k] = rem / len(other_keys)

        # Kết hợp thông tin tổng quát từ VLM nếu có
        if vlm_plots_summary:
            sources.append("VLM_PERCEPTION")
            vlm_has_ready = vlm_plots_summary.get("has_ready_crops", False)
            vlm_has_empty = vlm_plots_summary.get("has_empty_plots", False)

            # Đánh giá mức độ đồng thuận
            if local_state == PlotStateEnum.READY.value and not vlm_has_ready:
                agreement -= cls.CONFLICT_PENALTY
            elif local_state == PlotStateEnum.EMPTY.value and not vlm_has_empty:
                agreement -= cls.CONFLICT_PENALTY
            elif local_state == PlotStateEnum.READY.value and vlm_has_ready:
                probs[PlotStateEnum.READY.value] = min(0.98, probs[PlotStateEnum.READY.value] + 0.15)
            elif local_state == PlotStateEnum.EMPTY.value and vlm_has_empty:
                probs[PlotStateEnum.EMPTY.value] = min(0.98, probs[PlotStateEnum.EMPTY.value] + 0.15)

        # Chuẩn hóa tổng xác suất = 1.0
        total_p = sum(probs.values())
        if total_p > 0:
            probs = {k: round(v / total_p, 4) for k, v in probs.items()}

        best_state_str = max(probs, key=probs.get)
        confidence = probs[best_state_str] * max(0.2, agreement)

        # Chính sách Abstention: Nếu tin cậy thấp hơn ngưỡng, gán về UNKNOWN
        if confidence < cls.CONFIDENCE_THRESHOLD:
            final_state = PlotStateEnum.UNKNOWN
        else:
            final_state = PlotStateEnum(best_state_str)

        return PlotBelief(
            plot_index=plot_index,
            coordinates=coords,
            probabilities=probs,
            most_likely_state=final_state,
            confidence=round(confidence, 3),
            sources=sources,
            evidence_agreement=round(agreement, 2)
        )

    @classmethod
    def build_environment_belief(
        cls,
        timestamp: float,
        plot_coords: List[Tuple[int, int]],
        local_plots_analysis: List[Dict[str, Any]],
        vlm_analysis: Optional[Dict[str, Any]] = None
    ) -> EnvironmentBeliefState:
        """Xây dựng trạng thái niềm tin toàn cảnh và đánh giá điều kiện Abstention."""
        vlm_data = vlm_analysis or {}
        vlm_plots = vlm_data.get("plots_summary", {})

        plots_beliefs = []
        for idx, coord in enumerate(plot_coords):
            local_obs = local_plots_analysis[idx] if idx < len(local_plots_analysis) else None
            p_belief = cls.fuse_plot_observations(idx, coord, local_obs, vlm_plots)
            plots_beliefs.append(p_belief)

        # Tính toán độ tin cậy trung bình
        avg_conf = float(np.mean([p.confidence for p in plots_beliefs])) if plots_beliefs else 0.0

        # Kiểm tra điều kiện Abstention toàn cục
        has_captcha = bool(vlm_data.get("has_captcha", False))
        is_syncing = bool(vlm_data.get("is_syncing", False))
        unknown_ratio = sum(1 for p in plots_beliefs if p.most_likely_state == PlotStateEnum.UNKNOWN) / max(1, len(plots_beliefs))

        abstain = False
        reason = None
        if has_captcha:
            abstain = True
            reason = "CAPTCHA_DETECTED"
        elif is_syncing:
            abstain = True
            reason = "GAME_SYNCING_IN_PROGRESS"
        elif unknown_ratio > 0.50:
            abstain = True
            reason = f"EXCESSIVE_PERCEPTION_UNCERTAINTY (Unknown ratio: {unknown_ratio*100:.1f}%)"

        return EnvironmentBeliefState(
            timestamp=timestamp,
            plots=plots_beliefs,
            has_blocking_popup=bool(vlm_data.get("has_blocking_popup", False)),
            popup_close_button=vlm_data.get("popup_close_button"),
            is_syncing=is_syncing,
            has_captcha=has_captcha,
            has_mushrooms=bool(vlm_data.get("has_mushrooms", False)),
            mushroom_positions=vlm_data.get("mushroom_positions", []),
            overall_confidence=round(avg_conf, 3),
            abstention_triggered=abstain,
            abstention_reason=reason
        )


class TaskVerifier:
    """
    Bộ thẩm định hậu kiểm vòng lặp đóng theo phong cách OSWorld (Xie et al., NeurIPS 2024):
    - Đánh giá Tiền điều kiện (Pre-conditions) trước khi phát lệnh click chuột.
    - Đánh giá Hậu điều kiện (Post-conditions) sau khi thao tác kết thúc.
    - Phân loại trạng thái khép kín: SUCCESS, PARTIAL, FAILED, hoặc ABSTAIN.
    """

    @staticmethod
    def verify_harvest_action(
        pre_belief: EnvironmentBeliefState,
        post_belief: EnvironmentBeliefState
    ) -> Dict[str, Any]:
        """
        Vị từ hậu kiểm cho tác vụ THU HOẠCH (HARVEST):
        - Tiền điều kiện kỳ vọng: Có ít nhất 1 ô đất chín (READY > 0) hoặc có tín hiệu thu hoạch.
        - Hậu điều kiện thành công: Số ô READY giảm, và số ô EMPTY hoặc GROWING tăng tương ứng.
        """
        pre_ready = pre_belief.ready_plots_count
        post_ready = post_belief.ready_plots_count
        post_empty = post_belief.empty_plots_count
        post_growing = post_belief.growing_plots_count

        # Nếu độ tin cậy hậu kỳ quá thấp -> Không đưa ra kết luận giả
        if post_belief.overall_confidence < 0.50 or post_belief.unknown_plots_count > len(post_belief.plots) // 2:
            return {
                "status": VerificationStatus.ABSTAIN_UNCERTAIN.value,
                "verified": False,
                "reason": "Insufficient post-action visual evidence (Abstention under uncertainty)",
                "delta": {"pre_ready": pre_ready, "post_ready": post_ready}
            }

        if pre_ready > 0 and post_ready < pre_ready:
            return {
                "status": VerificationStatus.VERIFIED_SUCCESS.value,
                "verified": True,
                "reason": f"Harvest confirmed: Ready plots reduced from {pre_ready} to {post_ready}",
                "delta": {"ready_reduced": pre_ready - post_ready, "post_empty": post_empty}
            }
        elif post_empty > 0 or post_growing > 0:
            return {
                "status": VerificationStatus.VERIFIED_PARTIAL.value,
                "verified": True,
                "reason": "Plots cleared/empty observed after harvest action",
                "delta": {"post_empty": post_empty, "post_growing": post_growing}
            }
        else:
            return {
                "status": VerificationStatus.VERIFIED_FAILED.value,
                "verified": False,
                "reason": "Post-condition failed: Plots remain in ready/unchanged state",
                "delta": {"pre_ready": pre_ready, "post_ready": post_ready}
            }

    @staticmethod
    def verify_plant_action(
        pre_belief: EnvironmentBeliefState,
        post_belief: EnvironmentBeliefState
    ) -> Dict[str, Any]:
        """
        Vị từ hậu kiểm cho tác vụ GIEO HẠT (PLANT):
        - Tiền điều kiện: Ô đất đang ở trạng thái trống (EMPTY > 0).
        - Hậu điều kiện: Số ô đất EMPTY giảm về 0, và số ô GROWING (có mầm/timer) xuất hiện.
        """
        pre_empty = pre_belief.empty_plots_count
        post_empty = post_belief.empty_plots_count
        post_growing = post_belief.growing_plots_count
        total_plots = len(post_belief.plots)

        if post_belief.overall_confidence < 0.50 or post_belief.unknown_plots_count > total_plots // 2:
            return {
                "status": VerificationStatus.ABSTAIN_UNCERTAIN.value,
                "verified": False,
                "reason": "Insufficient post-action visual evidence to verify seeding",
                "delta": {"post_growing": post_growing, "post_empty": post_empty}
            }

        if post_growing > 0 and post_empty == 0:
            return {
                "status": VerificationStatus.VERIFIED_SUCCESS.value,
                "verified": True,
                "reason": f"Seeding fully confirmed: All {total_plots} plots active with growing crops/timer badges",
                "delta": {"post_growing": post_growing, "post_empty": 0}
            }
        elif post_growing > 0:
            return {
                "status": VerificationStatus.VERIFIED_PARTIAL.value,
                "verified": True,
                "reason": f"Partial seeding confirmed: {post_growing}/{total_plots} plots have active crops",
                "delta": {"post_growing": post_growing, "post_empty": post_empty}
            }
        else:
            return {
                "status": VerificationStatus.VERIFIED_FAILED.value,
                "verified": False,
                "reason": "Post-condition failed: No seedlings or timer badges observed after planting",
                "delta": {"pre_empty": pre_empty, "post_empty": post_empty}
            }

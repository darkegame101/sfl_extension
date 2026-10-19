import unittest
import time
from core.evidence_engine import (
    PlotStateEnum,
    PlotBelief,
    EnvironmentBeliefState,
    EvidenceFuser,
    TaskVerifier,
    VerificationStatus
)


class TestEvidenceEngine(unittest.TestCase):
    """
    Unit test cho Branch 1: Trạng thái niềm tin POMDP (Kurniawati 2022)
    và Thẩm định Hậu kiểm Vòng lặp đóng (OSWorld, Xie et al., NeurIPS 2024).
    Đảm bảo chạy offline, tất định, không phụ thuộc external LLM hay API.
    """

    def setUp(self):
        self.plot_coords = [(100, 200), (150, 200), (200, 200)]

    def test_bayesian_fusion_high_agreement(self):
        """Khi LocalVision và VLM đồng thuận (ví dụ cùng thấy READY), confidence phải cao (> 0.85)."""
        local_obs = {"state": "READY", "confidence": 0.85, "badge_detected": True}
        vlm_plots = {"has_ready_crops": True, "has_empty_plots": False}

        belief = EvidenceFuser.fuse_plot_observations(
            plot_index=0,
            coords=(100, 200),
            local_obs=local_obs,
            vlm_plots_summary=vlm_plots
        )

        self.assertEqual(belief.most_likely_state, PlotStateEnum.READY)
        self.assertGreater(belief.confidence, 0.80)
        self.assertIn("LOCAL_VISION", belief.sources)
        self.assertIn("VLM_PERCEPTION", belief.sources)

    def test_bayesian_fusion_conflict_penalty(self):
        """Khi LocalVision báo READY nhưng VLM khẳng định không có cây chín, confidence phải giảm do phạt xung đột."""
        local_obs = {"state": "READY", "confidence": 0.70}
        vlm_plots = {"has_ready_crops": False, "has_empty_plots": True}

        belief = EvidenceFuser.fuse_plot_observations(
            plot_index=0,
            coords=(100, 200),
            local_obs=local_obs,
            vlm_plots_summary=vlm_plots
        )

        self.assertLessEqual(belief.evidence_agreement, 0.70)
        self.assertLess(belief.confidence, 0.75)

    def test_abstention_triggered_on_captcha(self):
        """Phát hiện Captcha phải kích hoạt Abstention Policy ngay lập tức để dừng tự động hóa."""
        local_obs = [{"state": "EMPTY", "confidence": 0.9}] * 3
        vlm_data = {"has_captcha": True, "plots_summary": {}}

        env_belief = EvidenceFuser.build_environment_belief(
            timestamp=time.time(),
            plot_coords=self.plot_coords,
            local_plots_analysis=local_obs,
            vlm_analysis=vlm_data
        )

        self.assertTrue(env_belief.abstention_triggered)
        self.assertEqual(env_belief.abstention_reason, "CAPTCHA_DETECTED")
        self.assertTrue(env_belief.has_captcha)

    def test_abstention_triggered_on_syncing(self):
        """Khi game đang đồng bộ dữ liệu (Syncing), hệ thống phải từ chối thao tác."""
        local_obs = [{"state": "GROWING", "confidence": 0.8}] * 3
        vlm_data = {"is_syncing": True}

        env_belief = EvidenceFuser.build_environment_belief(
            timestamp=time.time(),
            plot_coords=self.plot_coords,
            local_plots_analysis=local_obs,
            vlm_analysis=vlm_data
        )

        self.assertTrue(env_belief.abstention_triggered)
        self.assertEqual(env_belief.abstention_reason, "GAME_SYNCING_IN_PROGRESS")

    def test_abstention_triggered_on_excessive_uncertainty(self):
        """Khi tỷ lệ ô đất UNKNOWN > 50%, hệ thống phải từ chối click mù để bảo vệ an toàn."""
        local_obs = [
            {"state": "UNKNOWN", "confidence": 0.2},
            {"state": "UNKNOWN", "confidence": 0.3},
            {"state": "READY", "confidence": 0.7}
        ]

        env_belief = EvidenceFuser.build_environment_belief(
            timestamp=time.time(),
            plot_coords=self.plot_coords,
            local_plots_analysis=local_obs,
            vlm_analysis={}
        )

        self.assertTrue(env_belief.abstention_triggered)
        self.assertIn("EXCESSIVE_PERCEPTION_UNCERTAINTY", env_belief.abstention_reason)

    def test_osworld_verify_harvest_success(self):
        """Kiểm chứng vị từ thu hoạch thành công: ready giảm, empty/growing xuất hiện."""
        pre_plots = [
            PlotBelief(0, (100, 200), {"READY": 0.9}, PlotStateEnum.READY, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"READY": 0.85}, PlotStateEnum.READY, 0.85, ["LOCAL"])
        ]
        post_plots = [
            PlotBelief(0, (100, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"EMPTY": 0.85}, PlotStateEnum.EMPTY, 0.85, ["LOCAL"])
        ]
        pre_env = EnvironmentBeliefState(time.time(), pre_plots, overall_confidence=0.88)
        post_env = EnvironmentBeliefState(time.time(), post_plots, overall_confidence=0.88)

        res = TaskVerifier.verify_harvest_action(pre_env, post_env)
        self.assertEqual(res["status"], VerificationStatus.VERIFIED_SUCCESS.value)
        self.assertTrue(res["verified"])

    def test_osworld_verify_harvest_failed(self):
        """Kiểm chứng vị từ thu hoạch thất bại: các ô vẫn giữ nguyên READY."""
        pre_plots = [
            PlotBelief(0, (100, 200), {"READY": 0.9}, PlotStateEnum.READY, 0.9, ["LOCAL"])
        ]
        post_plots = [
            PlotBelief(0, (100, 200), {"READY": 0.9}, PlotStateEnum.READY, 0.9, ["LOCAL"])
        ]
        pre_env = EnvironmentBeliefState(time.time(), pre_plots, overall_confidence=0.9)
        post_env = EnvironmentBeliefState(time.time(), post_plots, overall_confidence=0.9)

        res = TaskVerifier.verify_harvest_action(pre_env, post_env)
        self.assertEqual(res["status"], VerificationStatus.VERIFIED_FAILED.value)
        self.assertFalse(res["verified"])

    def test_osworld_verify_plant_success(self):
        """Kiểm chứng vị từ gieo hạt thành công: toàn bộ ô đất rỗng chuyển thành GROWING."""
        pre_plots = [
            PlotBelief(0, (100, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"EMPTY": 0.85}, PlotStateEnum.EMPTY, 0.85, ["LOCAL"])
        ]
        post_plots = [
            PlotBelief(0, (100, 200), {"GROWING": 0.9}, PlotStateEnum.GROWING, 0.9, ["LOCAL"]),
            PlotBelief(1, (150, 200), {"GROWING": 0.85}, PlotStateEnum.GROWING, 0.85, ["LOCAL"])
        ]
        pre_env = EnvironmentBeliefState(time.time(), pre_plots, overall_confidence=0.88)
        post_env = EnvironmentBeliefState(time.time(), post_plots, overall_confidence=0.88)

        res = TaskVerifier.verify_plant_action(pre_env, post_env)
        self.assertEqual(res["status"], VerificationStatus.VERIFIED_SUCCESS.value)
        self.assertTrue(res["verified"])

    def test_osworld_verify_plant_failed(self):
        """Kiểm chứng vị từ gieo hạt thất bại: các ô vẫn EMPTY không có mầm cây hay timer."""
        pre_plots = [
            PlotBelief(0, (100, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"])
        ]
        post_plots = [
            PlotBelief(0, (100, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"])
        ]
        pre_env = EnvironmentBeliefState(time.time(), pre_plots, overall_confidence=0.9)
        post_env = EnvironmentBeliefState(time.time(), post_plots, overall_confidence=0.9)

        res = TaskVerifier.verify_plant_action(pre_env, post_env)
        self.assertEqual(res["status"], VerificationStatus.VERIFIED_FAILED.value)
        self.assertFalse(res["verified"])

    def test_verifier_abstention_on_poor_post_confidence(self):
        """Khi ảnh hậu kỳ mờ hoặc không đủ tự tin, TaskVerifier phải trả về ABSTAIN thay vì đoán bừa."""
        pre_plots = [PlotBelief(0, (100, 200), {"EMPTY": 0.9}, PlotStateEnum.EMPTY, 0.9, ["LOCAL"])]
        post_plots = [PlotBelief(0, (100, 200), {"UNKNOWN": 0.3}, PlotStateEnum.UNKNOWN, 0.3, ["LOCAL"])]
        pre_env = EnvironmentBeliefState(time.time(), pre_plots, overall_confidence=0.9)
        post_env = EnvironmentBeliefState(time.time(), post_plots, overall_confidence=0.3)

        res = TaskVerifier.verify_plant_action(pre_env, post_env)
        self.assertEqual(res["status"], VerificationStatus.ABSTAIN_UNCERTAIN.value)
        self.assertFalse(res["verified"])


if __name__ == "__main__":
    unittest.main()

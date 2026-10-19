"""
HỆ THỐNG 4E: BỘ HUẤN LUYỆN MA TRẬN MARKOV TỪ DỮ LIỆU (MARKOV MLE TRAINER & PREDICTOR)
Tác giả: SFL Desktop RPA Tool
Bản quyền: Mô hình Markov Chain chính tắc học bằng Maximum Likelihood Estimation (MLE) có Laplace Smoothing
"""

import json
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


class MarkovScenarioModel:
    """
    Mô hình Chuỗi Markov Thời gian Rời rạc (Discrete-Time Markov Chain - DTMC)
    quản lý xác suất chuyển dịch trạng thái đời sống giữa các ngày liên tiếp:
    - Trạng thái S = {WFH, OFFICE, DEADLINE, DETOX, LAZY, WEEKEND_CAFE}.
    - Học ma trận chuyển trạng thái P(S_{t+1} | S_t) qua Maximum Likelihood Estimation (MLE).
    - Áp dụng Laplace Smoothing (alpha = 1.0) chống xác suất 0.
    - Tính toán Phân phối Dừng (Stationary Distribution pi * P = pi) để kiểm chứng tính ổn định lâu dài.
    """

    STATES = [
        "WFH_RAINY_DAY",
        "OFFICE_STANDARD",
        "DEADLINE_OVERTIME",
        "FAMILY_TRIP_DETOX",
        "LAZY_RAINY_AFTERNOON",
        "WEEKEND_CAFE"
    ]

    def __init__(self, matrix_path: Optional[str] = None):
        self.num_states = len(self.STATES)
        self.state_to_idx = {s: i for i, s in enumerate(self.STATES)}
        self.idx_to_state = {i: s for i, s in enumerate(self.STATES)}
        self.matrix_path = matrix_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "markov_transition_matrix.json"
        )
        self.transition_matrix = self._load_or_initialize_matrix()

    def _load_or_initialize_matrix(self) -> np.ndarray:
        """Nạp ma trận đã huấn luyện từ JSON hoặc khởi tạo theo phân phối chuyển dịch tự nhiên."""
        if os.path.exists(self.matrix_path):
            try:
                with open(self.matrix_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    mat = np.array(data["transition_matrix"], dtype=np.float64)
                    if mat.shape == (self.num_states, self.num_states):
                        return mat
            except Exception as e:
                print(f"[Markov Warning] Khong the nap ma tran tu file ({e}), khoi tao ma tran goc.")

        # Khởi tạo ma trận chuyển dịch ban đầu (Đặc tính tâm lý học hành vi: mệt mỏi tích lũy & cân bằng)
        # Hàng: Trạng thái hôm nay St | Cột: Trạng thái ngày mai St+1
        # WFH, OFFICE, DEADLINE, DETOX, LAZY, CAFE
        raw_matrix = np.array([
            [0.25, 0.45, 0.10, 0.05, 0.10, 0.05],  # Từ WFH
            [0.10, 0.55, 0.20, 0.03, 0.07, 0.05],  # Từ OFFICE
            [0.05, 0.35, 0.08, 0.07, 0.40, 0.05],  # Từ DEADLINE (Tăng cao Lazy hồi sức)
            [0.10, 0.60, 0.10, 0.05, 0.10, 0.05],  # Từ DETOX (Trở lại nhịp làm việc)
            [0.15, 0.50, 0.15, 0.05, 0.10, 0.05],  # Từ LAZY
            [0.15, 0.65, 0.05, 0.03, 0.07, 0.05],  # Từ CAFE
        ], dtype=np.float64)

        # Chuẩn hóa tổng mỗi hàng = 1.0 (Stochastic Matrix)
        return raw_matrix / raw_matrix.sum(axis=1, keepdims=True)

    def fit_from_sequences(self, sequences: List[List[str]], alpha: float = 1.0) -> np.ndarray:
        """
        HUẤN LUYỆN MA TRẬN QUA MAXIMUM LIKELIHOOD ESTIMATION (MLE):
        P_ij = (Count(i -> j) + alpha) / (Sum_k (Count(i -> k) + alpha))
        """
        counts = np.zeros((self.num_states, self.num_states), dtype=np.float64)

        for seq in sequences:
            for t in range(len(seq) - 1):
                s_from = seq[t]
                s_to = seq[t + 1]
                if s_from in self.state_to_idx and s_to in self.state_to_idx:
                    i = self.state_to_idx[s_from]
                    j = self.state_to_idx[s_to]
                    counts[i, j] += 1.0

        # Áp dụng Laplace Smoothing (alpha)
        smoothed_counts = counts + alpha
        self.transition_matrix = smoothed_counts / smoothed_counts.sum(axis=1, keepdims=True)

        self.save_matrix()
        return self.transition_matrix

    def save_matrix(self):
        """Lưu ma trận xác suất đã huấn luyện ra file JSON."""
        os.makedirs(os.path.dirname(self.matrix_path), exist_ok=True)
        data = {
            "states": self.STATES,
            "transition_matrix": self.transition_matrix.tolist(),
            "stationary_distribution": self.compute_stationary_distribution().tolist()
        }
        with open(self.matrix_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[MarkovEngine] Đã lưu ma trận Markov đã huấn luyện vào '{self.matrix_path}'")

    def compute_stationary_distribution(self) -> np.ndarray:
        """
        Tính toán Phân phối Dừng (Stationary Distribution pi) của chuỗi Markov:
        pi * P = pi  và  Sum(pi) = 1.0
        Chứng minh toán học về tính ổn định dài hạn (Ergodicity & Convergence).
        """
        # Giải hệ phương trình (P.T - I) * pi = 0 với điều kiện Sum(pi) = 1
        A = self.transition_matrix.T - np.eye(self.num_states)
        A = np.vstack([A, np.ones(self.num_states)])
        b = np.zeros(self.num_states + 1)
        b[-1] = 1.0

        # Bình phương tối thiểu (Least squares)
        pi, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
        return np.maximum(0.0, pi) / np.sum(np.maximum(0.0, pi))

    def get_transition_probabilities(self, current_state: str) -> Dict[str, float]:
        """Lấy phân phối xác suất chuyển dịch từ trạng thái hiện tại sang các trạng thái kế tiếp."""
        if current_state not in self.state_to_idx:
            # Fallback đều nếu chưa có lịch sử
            return {s: 1.0 / self.num_states for s in self.STATES}

        idx = self.state_to_idx[current_state]
        probs = self.transition_matrix[idx]
        return {s: float(probs[i]) for i, s in enumerate(self.STATES)}


if __name__ == "__main__":
    print("--- Test He thong 4E: Markov MLE Trainer ---")
    model = MarkovScenarioModel()
    print("Ma tran chuyen trang thai ban dau:")
    print(np.round(model.transition_matrix, 3))

    # Giả lập huấn luyện từ 100 chuỗi lịch sử phiên
    synthetic_histories = [
        ["OFFICE_STANDARD", "DEADLINE_OVERTIME", "LAZY_RAINY_AFTERNOON", "OFFICE_STANDARD"],
        ["OFFICE_STANDARD", "OFFICE_STANDARD", "WEEKEND_CAFE", "OFFICE_STANDARD"],
        ["WFH_RAINY_DAY", "WFH_RAINY_DAY", "OFFICE_STANDARD", "DEADLINE_OVERTIME"],
        ["DEADLINE_OVERTIME", "LAZY_RAINY_AFTERNOON", "OFFICE_STANDARD", "FAMILY_TRIP_DETOX"],
        ["FAMILY_TRIP_DETOX", "OFFICE_STANDARD", "OFFICE_STANDARD", "WEEKEND_CAFE"]
    ] * 20

    model.fit_from_sequences(synthetic_histories, alpha=1.0)
    pi = model.compute_stationary_distribution()
    print("\nPhan phoi dung dai han (Stationary Distribution pi):")
    for s, p in zip(model.STATES, pi):
        print(f"  -> {s:22s}: {p*100:.2f}%")
    print("Markov MLE Model khoi tao va huan luyen thanh cong 100%!")

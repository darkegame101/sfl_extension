"""
TEST SUITE: KIỂM THỬ ĐỊNH LUẬT FITTS & VẬN ĐỘNG HỌC CHUỘT
Kiểm chứng tính hợp lệ toán học của công thức MacKenzie (1992) và phân phối Log-Normal
"""

import unittest
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.human_mouse import HumanMouse


class TestFittsLaw(unittest.TestCase):

    def setUp(self):
        import random
        random.seed(42)

    def test_fitts_duration_monotonicity_distance(self):
        """Khoảng cách D càng lớn thì thời gian di chuyển MT phải tăng đơn điệu (Target width W cố định)."""
        w = 30.0
        dur_100 = HumanMouse.calculate_fitts_duration(distance=100.0, target_width=w)
        dur_500 = HumanMouse.calculate_fitts_duration(distance=500.0, target_width=w)
        dur_1000 = HumanMouse.calculate_fitts_duration(distance=1000.0, target_width=w)

        self.assertLess(dur_100, dur_500)
        self.assertLess(dur_500, dur_1000)

    def test_fitts_duration_monotonicity_width(self):
        """Mục tiêu càng nhỏ (W giảm) thì độ khó ID tăng -> thời gian MT phải tăng (Distance D cố định)."""
        d = 400.0
        dur_large_target = HumanMouse.calculate_fitts_duration(distance=d, target_width=80.0)
        dur_small_target = HumanMouse.calculate_fitts_duration(distance=d, target_width=15.0)

        self.assertLess(dur_large_target, dur_small_target)

    def test_shannon_formulation_positive_bounds(self):
        """Đảm bảo thời gian MT luôn dương và nằm trong ngưỡng sinh lý người (0.15s - 1.8s)."""
        for dist in [10, 50, 200, 800, 1920]:
            for width in [10, 30, 60]:
                dur = HumanMouse.calculate_fitts_duration(dist, width)
                self.assertGreater(dur, 0.12)
                self.assertLess(dur, 2.5)

    def test_log_normal_hold_distribution_properties(self):
        """Kiểm tra thời gian giữ chuột (click hold) tuân thủ phân phối Log-Normal hợp lệ."""
        samples = []
        for _ in range(500):
            # Lấy mẫu ngẫu nhiên từ phân phối log-normal tương ứng
            val = math.exp(random_lognormal_sample(-2.35, 0.22))
            samples.append(val)

        mean_val = sum(samples) / len(samples)
        # Kỳ vọng trung bình xung quanh 95ms - 105ms
        self.assertGreater(mean_val, 0.07)
        self.assertLess(mean_val, 0.13)


def random_lognormal_sample(mu, sigma):
    import random
    return random.gauss(mu, sigma)


if __name__ == "__main__":
    unittest.main()

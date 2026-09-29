import unittest

from percentile_threshold import RunningPercentileThreshold


class RunningPercentileThresholdTests(unittest.TestCase):
    def test_uses_fallback_during_warmup(self) -> None:
        tracker = RunningPercentileThreshold(
            resolution=1.0,
            warmup_frames=100,
        )
        for score in range(50):
            tracker.observe(float(score))

        self.assertEqual(
            tracker.threshold(top_percent=10.0, fallback=18.0),
            18.0,
        )

    def test_estimates_upper_tail_after_warmup(self) -> None:
        tracker = RunningPercentileThreshold(
            resolution=1.0,
            warmup_frames=100,
        )
        for score in range(100):
            tracker.observe(float(score))

        threshold = tracker.threshold(
            top_percent=10.0,
            fallback=18.0,
        )

        self.assertGreaterEqual(threshold, 89.0)
        self.assertLessEqual(threshold, 91.0)


if __name__ == "__main__":
    unittest.main()

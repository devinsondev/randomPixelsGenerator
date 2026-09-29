import unittest

import numpy as np

from analyzers import MvpAnalyzer, RobustAnalyzer


class AnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(12345)
        self.noise = rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)

        x = np.linspace(0, 255, 64, dtype=np.uint8)
        gradient = np.tile(x, (64, 1))
        self.structured = np.stack(
            [gradient, np.flipud(gradient), gradient],
            axis=2,
        )
        self.structured[::8, :, :] = 255
        self.structured[:, ::8, :] = 0

    def test_mvp_prefers_structured_image(self) -> None:
        analyzer = MvpAnalyzer()
        noise = analyzer.analyze(self.noise)
        structured = analyzer.analyze(self.structured)

        self.assertGreater(structured.score, noise.score + 20.0)

    def test_robust_prefers_structured_image(self) -> None:
        analyzer = RobustAnalyzer(control_count=3)
        noise = analyzer.analyze(self.noise)
        structured = analyzer.analyze(self.structured)

        self.assertGreater(structured.score, noise.score + 20.0)

    def test_robust_is_deterministic(self) -> None:
        analyzer = RobustAnalyzer(control_count=3)
        first = analyzer.analyze(self.noise)
        second = analyzer.analyze(self.noise)

        self.assertAlmostEqual(first.score, second.score, places=10)
        self.assertEqual(first.metrics, second.metrics)

    def test_rejects_wrong_shape(self) -> None:
        analyzer = MvpAnalyzer()

        with self.assertRaises(ValueError):
            analyzer.analyze(np.zeros((16, 16), dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()

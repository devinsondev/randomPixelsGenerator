import unittest
from unittest.mock import Mock

import numpy as np

from analysis_pipeline import AnalysisPipeline
from analyzers import AnalysisResult


class AnalysisPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.image = np.zeros((8, 8, 3), dtype=np.uint8)

    def test_skips_robust_when_mvp_rejects(self) -> None:
        mvp = Mock()
        robust = Mock()
        mvp.analyze.return_value = AnalysisResult(
            analyzer="mvp",
            score=5.0,
            threshold=18.0,
            metrics={},
        )

        result = AnalysisPipeline(mvp=mvp, robust=robust).analyze(self.image)

        self.assertIsNone(result.robust)
        robust.analyze.assert_not_called()

    def test_runs_robust_when_mvp_accepts(self) -> None:
        mvp = Mock()
        robust = Mock()
        mvp.analyze.return_value = AnalysisResult(
            analyzer="mvp",
            score=40.0,
            threshold=18.0,
            metrics={},
        )
        robust.analyze.return_value = AnalysisResult(
            analyzer="robust",
            score=31.0,
            threshold=24.0,
            metrics={},
        )

        result = AnalysisPipeline(mvp=mvp, robust=robust).analyze(self.image)

        self.assertTrue(result.is_candidate)
        robust.analyze.assert_called_once_with(self.image)

    def test_mvp_threshold_can_change_at_runtime(self) -> None:
        pipeline = AnalysisPipeline()

        pipeline.set_mvp_threshold(7.5)

        self.assertEqual(pipeline.mvp_threshold, 7.5)
        result = pipeline.analyze(self.image)
        self.assertEqual(result.mvp.threshold, 7.5)


if __name__ == "__main__":
    unittest.main()

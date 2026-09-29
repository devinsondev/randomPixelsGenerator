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


if __name__ == "__main__":
    unittest.main()

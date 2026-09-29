import tempfile
import unittest
from pathlib import Path

import numpy as np

from analysis_pipeline import PipelineResult
from analyzers import AnalysisResult
from candidate_store import CandidateStore


class CandidateStoreTests(unittest.TestCase):
    def test_saves_mvp_passing_frame_as_png(self) -> None:
        image = np.zeros((8, 8, 3), dtype=np.uint8)
        analysis = PipelineResult(
            mvp=AnalysisResult(
                analyzer="mvp",
                score=21.5,
                threshold=18.0,
                metrics={},
            ),
            robust=AnalysisResult(
                analyzer="robust",
                score=11.0,
                threshold=24.0,
                metrics={},
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            store = CandidateStore(Path(directory))
            path = store.save(image, frame_index=42, analysis=analysis)

            self.assertTrue(path.exists())
            self.assertIn("frame_000000042_mvp_21.5_robust_11.0", path.name)
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_rejects_frame_that_failed_mvp(self) -> None:
        image = np.zeros((8, 8, 3), dtype=np.uint8)
        analysis = PipelineResult(
            mvp=AnalysisResult(
                analyzer="mvp",
                score=3.0,
                threshold=18.0,
                metrics={},
            ),
            robust=None,
        )

        with tempfile.TemporaryDirectory() as directory:
            store = CandidateStore(Path(directory))
            with self.assertRaises(ValueError):
                store.save(image, frame_index=1, analysis=analysis)


if __name__ == "__main__":
    unittest.main()

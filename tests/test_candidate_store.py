import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from analysis_pipeline import PipelineResult
from analyzers import AnalysisResult
from candidate_store import CandidateStore


def analysis(mvp_score: float, robust_score: float | None) -> PipelineResult:
    robust = None
    if robust_score is not None:
        robust = AnalysisResult(
            analyzer="robust",
            score=robust_score,
            threshold=24.0,
            metrics={"edge": 0.75},
        )

    return PipelineResult(
        mvp=AnalysisResult(
            analyzer="mvp",
            score=mvp_score,
            threshold=18.0,
            metrics={"correlation": 0.25},
        ),
        robust=robust,
    )


class CandidateStoreTests(unittest.TestCase):
    def test_saves_mvp_and_robust_with_json_sidecars(self) -> None:
        image = np.zeros((8, 8, 3), dtype=np.uint8)

        with tempfile.TemporaryDirectory() as directory:
            store = CandidateStore(Path(directory), worker_id=3)
            saved = store.save(
                image,
                frame_index=42,
                worker_seed=111,
                frame_seed=222,
                analysis=analysis(21.5, 31.0),
                threshold_mode="auto",
                top_percent=0.01,
            )

            self.assertTrue(saved.mvp_png.exists())
            self.assertIsNotNone(saved.robust_png)
            self.assertTrue(saved.robust_png.exists())

            sidecar = saved.mvp_png.with_suffix(".json")
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(payload["worker_seed"], "111")
            self.assertEqual(payload["frame_seed"], "222")
            self.assertEqual(payload["frame_id"], 42)
            self.assertEqual(payload["mvp"]["metrics"]["correlation"], 0.25)
            self.assertEqual(payload["robust"]["metrics"]["edge"], 0.75)
            self.assertEqual(payload["threshold_policy"]["mode"], "auto")
            self.assertEqual(payload["threshold_policy"]["top_percent"], 0.01)
            self.assertEqual(len(payload["pixel_sha256"]), 64)

    def test_robust_folder_is_only_for_robust_passes(self) -> None:
        image = np.zeros((8, 8, 3), dtype=np.uint8)

        with tempfile.TemporaryDirectory() as directory:
            store = CandidateStore(Path(directory), worker_id=1)
            saved = store.save(
                image,
                frame_index=1,
                worker_seed=1,
                frame_seed=2,
                analysis=analysis(20.0, 10.0),
                threshold_mode="fixed",
                top_percent=0.01,
            )

            self.assertTrue(saved.mvp_png.exists())
            self.assertIsNone(saved.robust_png)

    def test_rejects_frame_that_failed_mvp(self) -> None:
        image = np.zeros((8, 8, 3), dtype=np.uint8)

        with tempfile.TemporaryDirectory() as directory:
            store = CandidateStore(Path(directory), worker_id=1)
            with self.assertRaises(ValueError):
                store.save(
                    image,
                    frame_index=1,
                    worker_seed=1,
                    frame_seed=2,
                    analysis=analysis(3.0, None),
                    threshold_mode="fixed",
                    top_percent=0.01,
                )


if __name__ == "__main__":
    unittest.main()

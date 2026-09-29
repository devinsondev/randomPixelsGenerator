import tempfile
import unittest
from pathlib import Path

from analysis_pipeline import PipelineResult
from analyzers import AnalysisResult
from candidate_store import CandidateStore
from random_frame import generate_rgb_frame
from reproduce_candidate import reproduce


class ReproduceCandidateTests(unittest.TestCase):
    def test_reproduces_hash_verified_candidate(self) -> None:
        frame_seed = 123456789
        image = generate_rgb_frame(12, 10, frame_seed)
        analysis = PipelineResult(
            mvp=AnalysisResult(
                analyzer="mvp",
                score=25.0,
                threshold=18.0,
                metrics={"x": 1.0},
            ),
            robust=None,
        )

        with tempfile.TemporaryDirectory() as directory:
            store = CandidateStore(Path(directory), worker_id=1)
            saved = store.save(
                image,
                frame_index=7,
                worker_seed=999,
                frame_seed=frame_seed,
                analysis=analysis,
                threshold_mode="fixed",
                top_percent=0.01,
            )

            sidecar = saved.mvp_png.with_suffix(".json")
            output = Path(directory) / "reproduced.png"
            reproduced = reproduce(sidecar, output)

            self.assertEqual(reproduced, output)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()

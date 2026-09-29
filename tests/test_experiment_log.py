import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from analysis_pipeline import PipelineResult
from analyzers import AnalysisResult
from experiment_log import FrameLogger


class FrameLoggerTests(unittest.TestCase):
    def test_records_full_metrics_to_sqlite(self) -> None:
        result = PipelineResult(
            mvp=AnalysisResult(
                analyzer="mvp",
                score=2.5,
                threshold=2.0,
                metrics={"corr": 0.42},
            ),
            robust=AnalysisResult(
                analyzer="robust",
                score=30.0,
                threshold=24.0,
                metrics={"fft": 0.73},
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "worker.sqlite3"
            logger = FrameLogger(
                database,
                worker_id=2,
                worker_seed=123456,
                batch_size=1,
            )
            logger.record(
                frame_index=7,
                frame_seed=888,
                width=64,
                height=64,
                analysis=result,
                threshold_mode="auto",
                top_percent=0.01,
            )
            logger.close()

            connection = sqlite3.connect(database)
            try:
                row = connection.execute(
                    """
                    SELECT worker_seed, frame_seed, mvp_score,
                           mvp_metrics_json, robust_metrics_json
                    FROM frames
                    WHERE frame_index = 7
                    """
                ).fetchone()
            finally:
                connection.close()

            self.assertEqual(row[0], "123456")
            self.assertEqual(row[1], "888")
            self.assertEqual(row[2], 2.5)
            self.assertEqual(json.loads(row[3])["corr"], 0.42)
            self.assertEqual(json.loads(row[4])["fft"], 0.73)


if __name__ == "__main__":
    unittest.main()

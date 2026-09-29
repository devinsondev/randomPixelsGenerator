from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from analysis_pipeline import PipelineResult


class FrameLogger:
    """Buffered per-worker SQLite logger for every analyzed frame."""

    def __init__(
        self,
        path: Path,
        worker_id: int,
        worker_seed: int,
        batch_size: int = 256,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive.")

        path.parent.mkdir(parents=True, exist_ok=True)
        self._worker_id = int(worker_id)
        self._worker_seed = str(int(worker_seed))
        self._batch_size = int(batch_size)
        self._buffer: list[tuple[object, ...]] = []
        self._last_flush = time.monotonic()

        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA temp_store=MEMORY")
        self._create_schema()

    def record(
        self,
        *,
        frame_index: int,
        frame_seed: int,
        width: int,
        height: int,
        analysis: PipelineResult,
        threshold_mode: str,
        top_percent: float,
    ) -> None:
        robust = analysis.robust

        self._buffer.append(
            (
                frame_index,
                self._worker_id,
                self._worker_seed,
                str(int(frame_seed)),
                width,
                height,
                time.time_ns(),
                threshold_mode,
                top_percent,
                analysis.mvp.score,
                analysis.mvp.threshold,
                int(analysis.mvp.is_interesting),
                _metrics_json(analysis.mvp.metrics),
                None if robust is None else robust.score,
                None if robust is None else robust.threshold,
                None if robust is None else int(robust.is_interesting),
                None if robust is None else _metrics_json(robust.metrics),
            )
        )

        if (
            len(self._buffer) >= self._batch_size
            or time.monotonic() - self._last_flush >= 1.0
        ):
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return

        self._connection.executemany(
            """
            INSERT INTO frames (
                frame_index, worker_id, worker_seed, frame_seed,
                width, height, timestamp_ns, threshold_mode, top_percent,
                mvp_score, mvp_threshold, mvp_passed, mvp_metrics_json,
                robust_score, robust_threshold, robust_passed,
                robust_metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._buffer,
        )
        self._connection.commit()
        self._buffer.clear()
        self._last_flush = time.monotonic()

    def close(self) -> None:
        self.flush()
        self._connection.close()

    def _create_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS frames (
                frame_index INTEGER PRIMARY KEY,
                worker_id INTEGER NOT NULL,
                worker_seed TEXT NOT NULL,
                frame_seed TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                timestamp_ns INTEGER NOT NULL,
                threshold_mode TEXT NOT NULL,
                top_percent REAL NOT NULL,
                mvp_score REAL NOT NULL,
                mvp_threshold REAL NOT NULL,
                mvp_passed INTEGER NOT NULL,
                mvp_metrics_json TEXT NOT NULL,
                robust_score REAL,
                robust_threshold REAL,
                robust_passed INTEGER,
                robust_metrics_json TEXT
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_frames_mvp_score "
            "ON frames(mvp_score DESC)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_frames_robust_score "
            "ON frames(robust_score DESC)"
        )
        self._connection.commit()


def _metrics_json(metrics) -> str:
    normalized = {str(key): float(value) for key, value in metrics.items()}
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))

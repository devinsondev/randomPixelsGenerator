from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    width: int
    height: int
    interval_ms: int
    mvp_threshold: float
    auto_threshold: bool
    top_percent: float
    threshold_warmup: int
    auto_save: bool
    send_image: bool

    def validated(self) -> "WorkerConfig":
        if not 2 <= self.width <= 4096:
            raise ValueError("width must be in the range 2..4096.")
        if not 2 <= self.height <= 4096:
            raise ValueError("height must be in the range 2..4096.")
        if not 1 <= self.interval_ms <= 60_000:
            raise ValueError("interval_ms must be in the range 1..60000.")
        if not 0.0 <= self.mvp_threshold <= 100.0:
            raise ValueError("mvp_threshold must be in the range 0..100.")
        if not 0.0001 <= self.top_percent <= 50.0:
            raise ValueError("top_percent must be in the range 0.0001..50.")
        if not 100 <= self.threshold_warmup <= 100_000_000:
            raise ValueError(
                "threshold_warmup must be in the range 100..100000000."
            )
        return self


@dataclass(frozen=True, slots=True)
class WorkerSnapshot:
    worker_id: int
    frame_index: int
    width: int
    height: int
    fps: float
    current_mvp: float
    average_mvp: float
    max_mvp: float
    max_mvp_frame: int
    mvp_threshold: float
    threshold_mode: str
    top_percent: float
    percentile_samples: int
    mvp_passed: int
    robust_score: float | None
    robust_threshold: float | None
    robust_runs: int
    robust_candidates: int
    saved_mvp: int
    saved_robust: int
    top_scores: tuple[tuple[int, float], ...]
    image_rgb: bytes | None
    error: str | None = None

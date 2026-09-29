from __future__ import annotations

import heapq
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RankedScore:
    frame_index: int
    score: float


class ScoreStats:
    """Streaming score statistics with a bounded top-N list."""

    def __init__(self, top_size: int = 10) -> None:
        if top_size < 1:
            raise ValueError("top_size must be positive.")

        self._top_size = top_size
        self._count = 0
        self._sum = 0.0
        self._maximum: RankedScore | None = None
        self._top: list[tuple[float, int]] = []

    @property
    def count(self) -> int:
        return self._count

    @property
    def average(self) -> float:
        return self._sum / self._count if self._count else 0.0

    @property
    def maximum(self) -> RankedScore | None:
        return self._maximum

    @property
    def top(self) -> tuple[RankedScore, ...]:
        ordered = sorted(self._top, reverse=True)
        return tuple(
            RankedScore(frame_index=frame_index, score=score)
            for score, frame_index in ordered
        )

    def record(self, frame_index: int, score: float) -> None:
        if frame_index < 1:
            raise ValueError("frame_index must be positive.")

        numeric_score = float(score)
        self._count += 1
        self._sum += numeric_score

        ranked = RankedScore(frame_index=frame_index, score=numeric_score)
        if self._maximum is None or numeric_score > self._maximum.score:
            self._maximum = ranked

        item = (numeric_score, frame_index)
        if len(self._top) < self._top_size:
            heapq.heappush(self._top, item)
        elif item > self._top[0]:
            heapq.heapreplace(self._top, item)


class SessionStats:
    """Counters and streaming statistics for one generator run."""

    def __init__(self) -> None:
        self.mvp = ScoreStats(top_size=10)
        self.mvp_passed = 0
        self.saved_mvp = 0
        self.saved_robust = 0
        self.robust_runs = 0
        self.robust_candidates = 0

from __future__ import annotations

import numpy as np


class RunningPercentileThreshold:
    """Constant-memory histogram used to estimate extreme MVP percentiles."""

    def __init__(
        self,
        resolution: float = 0.01,
        warmup_frames: int = 10_000,
    ) -> None:
        if not 0.001 <= resolution <= 1.0:
            raise ValueError("resolution must be in the range 0.001..1.0.")
        if warmup_frames < 1:
            raise ValueError("warmup_frames must be positive.")

        self._resolution = float(resolution)
        self._warmup_frames = int(warmup_frames)
        self._bin_count = int(round(100.0 / self._resolution)) + 1
        self._counts = np.zeros(self._bin_count, dtype=np.int64)
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    @property
    def warmup_frames(self) -> int:
        return self._warmup_frames

    @property
    def is_ready(self) -> bool:
        return self._count >= self._warmup_frames

    def reset(self, warmup_frames: int | None = None) -> None:
        if warmup_frames is not None:
            if warmup_frames < 1:
                raise ValueError("warmup_frames must be positive.")
            self._warmup_frames = int(warmup_frames)

        self._counts.fill(0)
        self._count = 0

    def observe(self, score: float) -> None:
        clipped = float(np.clip(score, 0.0, 100.0))
        index = int(round(clipped / self._resolution))
        index = min(max(index, 0), self._bin_count - 1)
        self._counts[index] += 1
        self._count += 1

    def threshold(
        self,
        top_percent: float,
        fallback: float,
    ) -> float:
        """
        Return the lower boundary of the requested upper-tail percentage.

        Example: top_percent=0.01 approximates the 99.99th percentile.
        """
        if not 0.0001 <= top_percent <= 50.0:
            raise ValueError("top_percent must be in the range 0.0001..50.")
        if not self.is_ready:
            return float(fallback)

        tail_count = max(
            1,
            int(np.ceil(self._count * top_percent / 100.0)),
        )
        cumulative = 0

        for index in range(self._bin_count - 1, -1, -1):
            cumulative += int(self._counts[index])
            if cumulative >= tail_count:
                return index * self._resolution

        return float(fallback)

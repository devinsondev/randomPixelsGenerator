from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tools.clipboard_resizer.resizer import ResizeFilter, ResizeMode


@dataclass(frozen=True, slots=True)
class BatchConfig:
    root: Path
    width: int
    height: int
    preview_size: int
    resize_mode: ResizeMode
    resize_filter: ResizeFilter
    recursive: bool = True

    def validated(self) -> "BatchConfig":
        if not self.root.is_dir():
            raise ValueError("root must be an existing directory.")
        if not 2 <= self.width <= 4096:
            raise ValueError("width must be in the range 2..4096.")
        if not 2 <= self.height <= 4096:
            raise ValueError("height must be in the range 2..4096.")
        if self.preview_size not in (8, 16):
            raise ValueError("preview_size must be 8 or 16.")
        return self


@dataclass(frozen=True, slots=True)
class ScorePair:
    mvp: float
    mvp_passed: bool
    robust: float
    robust_passed: bool


@dataclass(frozen=True, slots=True)
class BatchResult:
    path: Path
    source_width: int
    source_height: int
    target_width: int
    target_height: int
    preview_size: int
    preview_rgb: bytes
    real: ScorePair
    shuffled: ScorePair
    random: ScorePair


@dataclass(frozen=True, slots=True)
class BatchSummary:
    discovered: int
    analyzed: int
    failed: int
    cancelled: bool
    real_mvp_average: float
    real_robust_average: float
    shuffled_mvp_average: float
    shuffled_robust_average: float
    random_mvp_average: float
    random_robust_average: float

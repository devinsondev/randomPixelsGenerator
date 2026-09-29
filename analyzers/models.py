from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Normalized output shared by all procedural analyzers."""

    analyzer: str
    score: float
    threshold: float
    metrics: Mapping[str, float]

    @property
    def is_interesting(self) -> bool:
        """Whether the image should pass to the next analysis stage."""
        return self.score >= self.threshold

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from analyzers import AnalysisResult, MvpAnalyzer, RobustAnalyzer


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Result of the two-stage procedural analysis pipeline."""

    mvp: AnalysisResult
    robust: AnalysisResult | None

    @property
    def is_candidate(self) -> bool:
        return self.robust is not None and self.robust.is_interesting


class AnalysisPipeline:
    """Run the cheap analyzer first and spend CPU on robust analysis selectively."""

    def __init__(
        self,
        mvp: MvpAnalyzer | None = None,
        robust: RobustAnalyzer | None = None,
    ) -> None:
        self._mvp = mvp or MvpAnalyzer()
        self._robust = robust or RobustAnalyzer()

    def analyze(self, image: NDArray[np.generic]) -> PipelineResult:
        mvp_result = self._mvp.analyze(image)

        if not mvp_result.is_interesting:
            return PipelineResult(mvp=mvp_result, robust=None)

        robust_result = self._robust.analyze(image)
        return PipelineResult(mvp=mvp_result, robust=robust_result)

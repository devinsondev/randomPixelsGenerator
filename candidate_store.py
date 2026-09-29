from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from analysis_pipeline import PipelineResult
from image_io import save_rgb_png


class CandidateStore:
    """Persist frames that passed the first procedural filter."""

    def __init__(self, root: Path = Path("candidates")) -> None:
        self._root = root

    def save(
        self,
        image: NDArray[np.generic],
        frame_index: int,
        analysis: PipelineResult,
    ) -> Path:
        if not analysis.mvp.is_interesting:
            raise ValueError("Only MVP-passing frames may be auto-saved.")

        robust_suffix = "robust_na"
        if analysis.robust is not None:
            robust_suffix = f"robust_{analysis.robust.score:.1f}"

        filename = (
            f"frame_{frame_index:09d}_"
            f"mvp_{analysis.mvp.score:.1f}_"
            f"{robust_suffix}.png"
        )
        path = self._root / filename
        save_rgb_png(image, path)
        return path

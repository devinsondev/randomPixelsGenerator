from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from analysis_pipeline import PipelineResult
from image_io import save_rgb_png


@dataclass(frozen=True, slots=True)
class SavedCandidate:
    mvp_png: Path
    robust_png: Path | None


class CandidateStore:
    """Persist MVP and robust candidates with reproducibility sidecars."""

    def __init__(self, root: Path, worker_id: int) -> None:
        self._root = root
        self._worker_id = int(worker_id)

    def save(
        self,
        image: NDArray[np.generic],
        *,
        frame_index: int,
        worker_seed: int,
        frame_seed: int,
        analysis: PipelineResult,
    ) -> SavedCandidate:
        if not analysis.mvp.is_interesting:
            raise ValueError("Only MVP-passing frames may be auto-saved.")

        base_name = (
            f"frame_{frame_index:09d}_"
            f"mvp_{analysis.mvp.score:.2f}"
        )
        mvp_png = self._save_stage(
            stage="mvp",
            base_name=base_name,
            image=image,
            frame_index=frame_index,
            worker_seed=worker_seed,
            frame_seed=frame_seed,
            analysis=analysis,
        )

        robust_png: Path | None = None
        if analysis.is_candidate:
            robust_name = (
                f"{base_name}_robust_{analysis.robust.score:.2f}"
            )
            robust_png = self._save_stage(
                stage="robust",
                base_name=robust_name,
                image=image,
                frame_index=frame_index,
                worker_seed=worker_seed,
                frame_seed=frame_seed,
                analysis=analysis,
            )

        return SavedCandidate(mvp_png=mvp_png, robust_png=robust_png)

    def _save_stage(
        self,
        *,
        stage: str,
        base_name: str,
        image: NDArray[np.generic],
        frame_index: int,
        worker_seed: int,
        frame_seed: int,
        analysis: PipelineResult,
    ) -> Path:
        directory = self._root / stage / f"worker_{self._worker_id:02d}"
        png_path = directory / f"{base_name}.png"
        json_path = directory / f"{base_name}.json"

        save_rgb_png(image, png_path)
        json_path.write_text(
            json.dumps(
                self._metadata(
                    stage=stage,
                    image=image,
                    frame_index=frame_index,
                    worker_seed=worker_seed,
                    frame_seed=frame_seed,
                    analysis=analysis,
                ),
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return png_path

    def _metadata(
        self,
        *,
        stage: str,
        image: NDArray[np.generic],
        frame_index: int,
        worker_seed: int,
        frame_seed: int,
        analysis: PipelineResult,
    ) -> dict[str, object]:
        robust = analysis.robust
        return {
            "stage": stage,
            "worker_id": self._worker_id,
            "worker_seed": str(int(worker_seed)),
            "frame_seed": str(int(frame_seed)),
            "frame_id": int(frame_index),
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
            "saved_utc": datetime.now(timezone.utc).isoformat(),
            "mvp": _analysis_payload(analysis.mvp),
            "robust": (
                None if robust is None else _analysis_payload(robust)
            ),
        }


def _analysis_payload(result) -> dict[str, object]:
    return {
        "analyzer": result.analyzer,
        "score": float(result.score),
        "threshold": float(result.threshold),
        "passed": bool(result.is_interesting),
        "metrics": {
            str(key): float(value)
            for key, value in result.metrics.items()
        },
    }

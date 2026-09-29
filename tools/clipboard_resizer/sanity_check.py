from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PySide6.QtGui import QImage

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analyzers import AnalysisResult, MvpAnalyzer, RobustAnalyzer


@dataclass(frozen=True, slots=True)
class SanitySample:
    name: str
    mvp: AnalysisResult
    robust: AnalysisResult


@dataclass(frozen=True, slots=True)
class SanityCheckResult:
    original: SanitySample
    shuffled: SanitySample
    random: SanitySample


class SanityChecker:
    """Compare an image against spatially destroyed and IID-random controls."""

    def __init__(self) -> None:
        self._mvp = MvpAnalyzer()
        self._robust = RobustAnalyzer()

    def analyze(self, image: QImage) -> SanityCheckResult:
        rgb = qimage_to_rgb(image)
        shuffled = _shuffle_pixels(rgb, seed=1)
        random = np.random.default_rng(2).integers(
            0,
            256,
            size=rgb.shape,
            dtype=np.uint8,
        )

        return SanityCheckResult(
            original=self._sample("Изображение", rgb),
            shuffled=self._sample("Shuffled", shuffled),
            random=self._sample("Random", random),
        )

    def _sample(
        self,
        name: str,
        image: NDArray[np.uint8],
    ) -> SanitySample:
        # Robust is intentionally run regardless of the MVP gate: this tool is
        # diagnostic and must expose both scores for every control sample.
        return SanitySample(
            name=name,
            mvp=self._mvp.analyze(image),
            robust=self._robust.analyze(image),
        )


def qimage_to_rgb(image: QImage) -> NDArray[np.uint8]:
    """Copy a QImage into a contiguous H×W×3 uint8 RGB NumPy array."""
    if image.isNull():
        raise ValueError("image must not be null.")

    rgb = image.convertToFormat(QImage.Format_RGB888)
    height = rgb.height()
    width = rgb.width()
    bytes_per_line = rgb.bytesPerLine()

    buffer = np.frombuffer(
        rgb.constBits(),
        dtype=np.uint8,
        count=height * bytes_per_line,
    )
    rows = buffer.reshape(height, bytes_per_line)
    pixels = rows[:, : width * 3].reshape(height, width, 3)
    return np.ascontiguousarray(pixels)


def format_sample(sample: SanitySample) -> str:
    mvp_state = "PASS" if sample.mvp.is_interesting else "fail"
    robust_state = "PASS" if sample.robust.is_interesting else "fail"

    return (
        f"{sample.name}: "
        f"MVP {sample.mvp.score:.2f}/{sample.mvp.threshold:.0f} {mvp_state} | "
        f"Robust {sample.robust.score:.2f}/"
        f"{sample.robust.threshold:.0f} {robust_state}"
    )


def format_original_metrics(sample: SanitySample) -> str:
    mvp = sample.mvp.metrics
    robust = sample.robust.metrics

    return (
        "Метрики изображения: "
        f"corr={mvp['raw_spatial_correlation']:.3f}, "
        f"neighbor={mvp['raw_neighbor_similarity_excess']:.3f}, "
        f"compression={mvp['raw_compression_gain']:.3f}, "
        f"entropy_deficit={mvp['raw_entropy_deficit']:.3f} | "
        "Robust z: "
        f"corr={robust['z_spatial_correlation']:.2f}, "
        f"neighbor={robust['z_neighbor_coherence']:.2f}, "
        f"fft={robust['z_spectral_concentration']:.2f}, "
        f"edges={robust['z_edge_coherence']:.2f}, "
        f"compression={robust['z_compression_efficiency']:.2f}"
    )


def _shuffle_pixels(
    image: NDArray[np.uint8],
    seed: int,
) -> NDArray[np.uint8]:
    pixels = image.reshape(-1, 3)
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(len(pixels))
    return np.ascontiguousarray(pixels[permutation].reshape(image.shape))

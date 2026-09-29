from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .common import (
    channel_entropy,
    clamp01,
    quantized_compression_efficiency,
    rgb_to_luma,
    safe_correlation,
    shuffled_pixels,
    validate_rgb,
)
from .models import AnalysisResult


class MvpAnalyzer:
    """Cheap first-pass detector for non-random spatial structure."""

    def __init__(self, threshold: float = 18.0) -> None:
        if not 0.0 <= threshold <= 100.0:
            raise ValueError("threshold must be in the range 0..100.")
        self.threshold = float(threshold)

    def analyze(self, image: NDArray[np.generic]) -> AnalysisResult:
        rgb = validate_rgb(image)
        luma = rgb_to_luma(rgb)

        correlation = self._adjacent_correlation(luma)
        similarity_excess = self._neighbor_similarity_excess(rgb)
        compression_gain = self._compression_gain(rgb)
        entropy_deficit = 1.0 - channel_entropy(rgb)

        pair_count = max(
            luma.shape[0] * (luma.shape[1] - 1)
            + (luma.shape[0] - 1) * luma.shape[1],
            1,
        )
        correlation_noise_floor = min(0.35, 2.0 / np.sqrt(pair_count))

        components = {
            "spatial_correlation": clamp01(
                (correlation - correlation_noise_floor) / 0.55
            ),
            "neighbor_similarity": clamp01((similarity_excess - 0.025) / 0.22),
            "compression_gain": clamp01((compression_gain - 0.015) / 0.18),
            "entropy_deficit": clamp01((entropy_deficit - 0.015) / 0.18),
        }

        score = 100.0 * (
            0.36 * components["spatial_correlation"]
            + 0.34 * components["neighbor_similarity"]
            + 0.20 * components["compression_gain"]
            + 0.10 * components["entropy_deficit"]
        )

        metrics = {
            "raw_spatial_correlation": correlation,
            "raw_neighbor_similarity_excess": similarity_excess,
            "raw_compression_gain": compression_gain,
            "raw_entropy_deficit": entropy_deficit,
            **components,
        }

        return AnalysisResult(
            analyzer="mvp",
            score=float(np.clip(score, 0.0, 100.0)),
            threshold=self.threshold,
            metrics=metrics,
        )

    @staticmethod
    def _adjacent_correlation(luma: NDArray[np.float32]) -> float:
        horizontal = abs(safe_correlation(luma[:, :-1], luma[:, 1:]))
        vertical = abs(safe_correlation(luma[:-1, :], luma[1:, :]))
        return float((horizontal + vertical) / 2.0)

    @staticmethod
    def _neighbor_similarity_excess(image: NDArray[np.uint8]) -> float:
        rgb = image.astype(np.float32)

        horizontal = np.linalg.norm(rgb[:, 1:] - rgb[:, :-1], axis=2)
        vertical = np.linalg.norm(rgb[1:, :] - rgb[:-1, :], axis=2)
        actual_distance = float(
            (horizontal.sum() + vertical.sum())
            / max(horizontal.size + vertical.size, 1)
        )

        pixels = rgb.reshape(-1, 3)
        offset = max(1, len(pixels) // 2 + 1)
        baseline_distance = float(
            np.linalg.norm(pixels - np.roll(pixels, offset, axis=0), axis=1).mean()
        )

        if baseline_distance <= 1e-9:
            return 0.0
        return (baseline_distance - actual_distance) / baseline_distance

    @staticmethod
    def _compression_gain(image: NDArray[np.uint8]) -> float:
        original = quantized_compression_efficiency(image, bits=4)
        shuffled = quantized_compression_efficiency(
            shuffled_pixels(image, seed=0),
            bits=4,
        )
        return original - shuffled

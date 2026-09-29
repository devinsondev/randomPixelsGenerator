from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class _Signature:
    spatial_correlation: float
    neighbor_coherence: float
    spectral_concentration: float
    edge_coherence: float
    compression_efficiency: float


class RobustAnalyzer:
    """
    Second-pass detector.

    It compares the real image with pixel-shuffled controls. The controls keep
    the exact color histogram but destroy spatial structure, so a high score
    means "more spatial organization than expected from these same pixels".
    """

    _FLOORS = {
        "spatial_correlation": 0.010,
        "neighbor_coherence": 0.004,
        "spectral_concentration": 0.003,
        "edge_coherence": 0.010,
        "compression_efficiency": 0.004,
    }

    _WEIGHTS = {
        "spatial_correlation": 0.25,
        "neighbor_coherence": 0.24,
        "spectral_concentration": 0.20,
        "edge_coherence": 0.21,
        "compression_efficiency": 0.10,
    }

    def __init__(
        self,
        threshold: float = 24.0,
        control_count: int = 5,
    ) -> None:
        if not 0.0 <= threshold <= 100.0:
            raise ValueError("threshold must be in the range 0..100.")
        if not 3 <= control_count <= 12:
            raise ValueError("control_count must be in the range 3..12.")

        self.threshold = float(threshold)
        self.control_count = int(control_count)

    def analyze(self, image: NDArray[np.generic]) -> AnalysisResult:
        rgb = validate_rgb(image)
        original = self._signature(rgb)

        controls = [
            self._signature(shuffled_pixels(rgb, seed=seed))
            for seed in range(1, self.control_count + 1)
        ]

        components: dict[str, float] = {}
        metrics: dict[str, float] = {}

        for name in self._WEIGHTS:
            original_value = float(getattr(original, name))
            control_values = np.array(
                [getattr(control, name) for control in controls],
                dtype=np.float64,
            )
            control_mean = float(control_values.mean())
            control_std = float(control_values.std(ddof=1))

            scale = max(
                control_std,
                self._FLOORS[name],
                abs(control_mean) * 0.015,
            )
            z_score = (original_value - control_mean) / scale
            component = clamp01(max(z_score, 0.0) / 4.0)

            components[name] = component
            metrics[f"raw_{name}"] = original_value
            metrics[f"control_{name}"] = control_mean
            metrics[f"z_{name}"] = z_score

        weighted_score = sum(
            self._WEIGHTS[name] * components[name]
            for name in self._WEIGHTS
        )

        # Histogram entropy is deliberately weak: it is not spatial evidence,
        # but a very low entropy image is unlikely to be full RGB white noise.
        entropy_deficit = 1.0 - channel_entropy(rgb)
        entropy_prior = clamp01((entropy_deficit - 0.02) / 0.25)

        score = 100.0 * (0.95 * weighted_score + 0.05 * entropy_prior)

        metrics.update(
            {f"component_{name}": value for name, value in components.items()}
        )
        metrics["raw_entropy_deficit"] = entropy_deficit
        metrics["entropy_prior"] = entropy_prior

        return AnalysisResult(
            analyzer="robust",
            score=float(np.clip(score, 0.0, 100.0)),
            threshold=self.threshold,
            metrics=metrics,
        )

    def _signature(self, image: NDArray[np.uint8]) -> _Signature:
        luma = rgb_to_luma(image)

        return _Signature(
            spatial_correlation=self._multiscale_correlation(luma),
            neighbor_coherence=self._neighbor_coherence(image),
            spectral_concentration=self._spectral_concentration(luma),
            edge_coherence=self._edge_coherence(luma),
            compression_efficiency=quantized_compression_efficiency(
                image,
                bits=4,
            ),
        )

    @staticmethod
    def _multiscale_correlation(luma: NDArray[np.float32]) -> float:
        values: list[float] = []
        height, width = luma.shape

        for offset in (1, 2, 4):
            if width > offset:
                values.append(
                    abs(safe_correlation(luma[:, :-offset], luma[:, offset:]))
                )
            if height > offset:
                values.append(
                    abs(safe_correlation(luma[:-offset, :], luma[offset:, :]))
                )

        return float(np.mean(values)) if values else 0.0

    @staticmethod
    def _neighbor_coherence(image: NDArray[np.uint8]) -> float:
        rgb = image.astype(np.float32) / 255.0

        horizontal = np.linalg.norm(rgb[:, 1:] - rgb[:, :-1], axis=2)
        vertical = np.linalg.norm(rgb[1:, :] - rgb[:-1, :], axis=2)

        mean_distance = float(
            (horizontal.sum() + vertical.sum())
            / max(horizontal.size + vertical.size, 1)
        )

        max_rgb_distance = np.sqrt(3.0)
        return clamp01(1.0 - mean_distance / max_rgb_distance)

    @staticmethod
    def _spectral_concentration(luma: NDArray[np.float32]) -> float:
        centered = luma.astype(np.float64) - float(luma.mean())
        power = np.abs(np.fft.fftshift(np.fft.fft2(centered))) ** 2
        total = float(power.sum())
        if total <= 1e-12:
            return 1.0

        height, width = luma.shape
        yy, xx = np.ogrid[:height, :width]
        cy = (height - 1) / 2.0
        cx = (width - 1) / 2.0

        radius = np.sqrt(
            ((yy - cy) / max(height, 1)) ** 2
            + ((xx - cx) / max(width, 1)) ** 2
        )
        low_frequency_mask = radius <= 0.18
        return float(power[low_frequency_mask].sum() / total)

    @staticmethod
    def _edge_coherence(luma: NDArray[np.float32]) -> float:
        if min(luma.shape) < 3:
            return 0.0

        gx = (
            -luma[:-2, :-2]
            + luma[:-2, 2:]
            - 2.0 * luma[1:-1, :-2]
            + 2.0 * luma[1:-1, 2:]
            - luma[2:, :-2]
            + luma[2:, 2:]
        )
        gy = (
            luma[:-2, :-2]
            + 2.0 * luma[:-2, 1:-1]
            + luma[:-2, 2:]
            - luma[2:, :-2]
            - 2.0 * luma[2:, 1:-1]
            - luma[2:, 2:]
        )

        magnitude = np.hypot(gx, gy)
        if not np.any(magnitude > 1e-9):
            return 1.0

        threshold = float(np.quantile(magnitude, 0.70))
        edge = magnitude >= max(threshold, 1e-9)
        angle = np.arctan2(gy, gx)

        agreements: list[NDArray[np.float32]] = []

        h_mask = edge[:, :-1] & edge[:, 1:]
        if np.any(h_mask):
            delta = angle[:, :-1] - angle[:, 1:]
            agreements.append(np.cos(2.0 * delta)[h_mask])

        v_mask = edge[:-1, :] & edge[1:, :]
        if np.any(v_mask):
            delta = angle[:-1, :] - angle[1:, :]
            agreements.append(np.cos(2.0 * delta)[v_mask])

        if not agreements:
            return 0.0

        combined = np.concatenate(agreements)
        # Map [-1, 1] to [0, 1]. Shuffled controls establish the real baseline.
        return float((combined.mean() + 1.0) / 2.0)

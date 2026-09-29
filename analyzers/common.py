from __future__ import annotations

import zlib

import numpy as np
from numpy.typing import NDArray

RgbImage = NDArray[np.uint8]


def validate_rgb(image: NDArray[np.generic]) -> RgbImage:
    """Return a C-contiguous uint8 RGB array or raise a useful error."""
    array = np.asarray(image)

    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("Expected image with shape (height, width, 3).")
    if array.shape[0] < 2 or array.shape[1] < 2:
        raise ValueError("Image must be at least 2x2 pixels.")
    if array.dtype != np.uint8:
        raise TypeError("Expected image dtype uint8.")

    return np.ascontiguousarray(array)


def rgb_to_luma(image: RgbImage) -> NDArray[np.float32]:
    """Convert uint8 RGB to luminance in [0, 1]."""
    rgb = image.astype(np.float32) / 255.0
    return (
        rgb[..., 0] * 0.2126
        + rgb[..., 1] * 0.7152
        + rgb[..., 2] * 0.0722
    )


def channel_entropy(image: RgbImage) -> float:
    """Average Shannon entropy of R, G and B, normalized to [0, 1]."""
    entropies: list[float] = []

    for channel in range(3):
        counts = np.bincount(image[..., channel].ravel(), minlength=256)
        probabilities = counts[counts > 0].astype(np.float64)
        probabilities /= probabilities.sum()
        entropy = -np.sum(probabilities * np.log2(probabilities))
        entropies.append(float(entropy / 8.0))

    return float(np.mean(entropies))


def safe_correlation(a: NDArray[np.floating], b: NDArray[np.floating]) -> float:
    """Pearson correlation with stable behavior for nearly constant arrays."""
    x = np.asarray(a, dtype=np.float64).ravel().copy()
    y = np.asarray(b, dtype=np.float64).ravel().copy()

    x -= x.mean()
    y -= y.mean()

    denominator = float(np.sqrt(np.dot(x, x) * np.dot(y, y)))
    if denominator <= 1e-12:
        return 1.0 if np.allclose(a, b) else 0.0

    return float(np.dot(x, y) / denominator)


def shuffled_pixels(image: RgbImage, seed: int) -> RgbImage:
    """Deterministically shuffle whole RGB pixels while preserving the histogram."""
    pixels = image.reshape(-1, 3)
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(len(pixels))
    return np.ascontiguousarray(pixels[permutation].reshape(image.shape))


def quantized_compression_efficiency(image: RgbImage, bits: int = 4) -> float:
    """Return how much zlib compresses a quantized RGB byte stream."""
    if not 1 <= bits <= 8:
        raise ValueError("bits must be in the range 1..8.")

    shift = 8 - bits
    quantized = np.right_shift(image, shift).astype(np.uint8, copy=False)
    raw = quantized.tobytes(order="C")
    compressed_size = len(zlib.compress(raw, level=1))

    return 1.0 - compressed_size / max(len(raw), 1)


def clamp01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))

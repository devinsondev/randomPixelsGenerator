from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

_MASK_64 = (1 << 64) - 1


def derive_frame_seed(worker_seed: int, frame_index: int) -> int:
    """Derive an independent reproducible 64-bit seed for one frame."""
    if not 0 <= worker_seed <= _MASK_64:
        raise ValueError("worker_seed must fit in uint64.")
    if frame_index < 1:
        raise ValueError("frame_index must be positive.")

    value = (worker_seed + frame_index * 0x9E3779B97F4A7C15) & _MASK_64
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9 & _MASK_64
    value = (value ^ (value >> 27)) * 0x94D049BB133111EB & _MASK_64
    return (value ^ (value >> 31)) & _MASK_64


def generate_rgb_frame(
    width: int,
    height: int,
    frame_seed: int,
) -> NDArray[np.uint8]:
    """Generate one RGB frame that can be reproduced from frame_seed alone."""
    rng = np.random.default_rng(frame_seed)
    return rng.integers(
        0,
        256,
        size=(height, width, 3),
        dtype=np.uint8,
    )

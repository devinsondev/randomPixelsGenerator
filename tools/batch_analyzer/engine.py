from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analyzers import MvpAnalyzer, RobustAnalyzer
from tools.batch_analyzer.models import BatchConfig, BatchResult, ScorePair
from tools.clipboard_resizer.resizer import (
    ResizeFilter,
    ResizeMode,
    resize_image,
)
from tools.clipboard_resizer.sanity_check import qimage_to_rgb

_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".gif",
    ".tif",
    ".tiff",
}


class BatchImageAnalyzer:
    """Analyze real, shuffled, and IID-random versions of one image."""

    def __init__(self) -> None:
        self._mvp = MvpAnalyzer()
        self._robust = RobustAnalyzer()

    def analyze_file(
        self,
        path: Path,
        config: BatchConfig,
    ) -> BatchResult:
        source = QImage(str(path))
        if source.isNull():
            raise ValueError(f"Unsupported or unreadable image: {path}")

        target = resize_image(
            source,
            width=config.width,
            height=config.height,
            mode=config.resize_mode,
            resize_filter=config.resize_filter,
        )
        rgb = qimage_to_rgb(target)

        seed = _stable_seed(path)
        shuffled = _shuffle_pixels(rgb, seed)
        random = np.random.default_rng(seed ^ 0xA5A5A5A5).integers(
            0,
            256,
            size=rgb.shape,
            dtype=np.uint8,
        )

        preview = resize_image(
            source,
            width=config.preview_size,
            height=config.preview_size,
            mode=ResizeMode.COVER,
            resize_filter=ResizeFilter.NEAREST,
        )

        return BatchResult(
            path=path,
            source_width=source.width(),
            source_height=source.height(),
            target_width=config.width,
            target_height=config.height,
            preview_size=config.preview_size,
            preview_rgb=qimage_to_rgb(preview).tobytes(order="C"),
            real=self._score(rgb),
            shuffled=self._score(shuffled),
            random=self._score(random),
        )

    def _score(self, image: np.ndarray) -> ScorePair:
        mvp = self._mvp.analyze(image)
        robust = self._robust.analyze(image)
        return ScorePair(
            mvp=mvp.score,
            mvp_passed=mvp.is_interesting,
            robust=robust.score,
            robust_passed=robust.is_interesting,
        )


def discover_images(config: BatchConfig) -> list[Path]:
    config.validated()
    iterator = config.root.rglob("*") if config.recursive else config.root.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in _IMAGE_EXTENSIONS
    )


def _stable_seed(path: Path) -> int:
    digest = hashlib.blake2b(
        str(path.resolve()).encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "little", signed=False)


def _shuffle_pixels(image: np.ndarray, seed: int) -> np.ndarray:
    pixels = image.reshape(-1, 3)
    permutation = np.random.default_rng(seed).permutation(len(pixels))
    return np.ascontiguousarray(pixels[permutation].reshape(image.shape))

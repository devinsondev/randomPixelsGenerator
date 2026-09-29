import tempfile
import unittest
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

from tools.batch_analyzer.engine import BatchImageAnalyzer, discover_images
from tools.batch_analyzer.models import BatchConfig
from tools.clipboard_resizer.resizer import ResizeFilter, ResizeMode


def save_rgb(path: Path, rgb: np.ndarray) -> None:
    height, width, _ = rgb.shape
    raw = np.ascontiguousarray(rgb).tobytes(order="C")
    image = QImage(
        raw,
        width,
        height,
        width * 3,
        QImage.Format_RGB888,
    ).copy()
    if not image.save(str(path), "PNG"):
        raise RuntimeError("Could not save test image.")


class BatchAnalyzerTests(unittest.TestCase):
    def test_discovers_supported_images_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()

            save_rgb(root / "a.png", np.zeros((8, 8, 3), dtype=np.uint8))
            save_rgb(nested / "b.png", np.zeros((8, 8, 3), dtype=np.uint8))
            (root / "ignore.txt").write_text("not an image", encoding="utf-8")

            config = BatchConfig(
                root=root,
                width=64,
                height=64,
                preview_size=16,
                resize_mode=ResizeMode.COVER,
                resize_filter=ResizeFilter.NEAREST,
                recursive=True,
            )

            found = discover_images(config)

            self.assertEqual(
                {path.name for path in found},
                {"a.png", "b.png"},
            )

    def test_structured_image_beats_batch_controls(self) -> None:
        size = 64
        x = np.linspace(0, 255, size, dtype=np.uint8)
        gradient = np.tile(x, (size, 1))
        structured = np.stack(
            [gradient, np.flipud(gradient), gradient],
            axis=2,
        )
        structured[::8, :, :] = 255
        structured[:, ::8, :] = 0

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "structured.png"
            save_rgb(path, structured)

            config = BatchConfig(
                root=root,
                width=64,
                height=64,
                preview_size=16,
                resize_mode=ResizeMode.COVER,
                resize_filter=ResizeFilter.NEAREST,
                recursive=True,
            )
            result = BatchImageAnalyzer().analyze_file(path, config)

            self.assertEqual(
                len(result.preview_rgb),
                16 * 16 * 3,
            )
            self.assertGreater(
                result.real.mvp,
                result.shuffled.mvp + 20.0,
            )
            self.assertGreater(
                result.real.mvp,
                result.random.mvp + 20.0,
            )
            self.assertGreater(
                result.real.robust,
                result.shuffled.robust + 20.0,
            )
            self.assertGreater(
                result.real.robust,
                result.random.robust + 20.0,
            )


if __name__ == "__main__":
    unittest.main()

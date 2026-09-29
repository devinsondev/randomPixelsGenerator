import unittest

import numpy as np
from PySide6.QtGui import QColor, QImage

from tools.clipboard_resizer.sanity_check import (
    SanityChecker,
    qimage_to_rgb,
)


def qimage_from_rgb(rgb: np.ndarray) -> QImage:
    height, width, _ = rgb.shape
    image = QImage(width, height, QImage.Format_RGB888)
    for y in range(height):
        for x in range(width):
            red, green, blue = (int(value) for value in rgb[y, x])
            image.setPixelColor(x, y, QColor(red, green, blue))
    return image


class SanityCheckerTests(unittest.TestCase):
    def test_qimage_conversion_preserves_pixels(self) -> None:
        rgb = np.zeros((8, 12, 3), dtype=np.uint8)
        rgb[..., 0] = 17
        rgb[..., 1] = 91
        rgb[..., 2] = 203

        converted = qimage_to_rgb(qimage_from_rgb(rgb))

        np.testing.assert_array_equal(converted, rgb)

    def test_structured_image_beats_spatial_controls(self) -> None:
        size = 64
        x = np.linspace(0, 255, size, dtype=np.uint8)
        gradient = np.tile(x, (size, 1))
        structured = np.stack(
            [gradient, np.flipud(gradient), gradient],
            axis=2,
        )
        structured[::8, :, :] = 255
        structured[:, ::8, :] = 0

        result = SanityChecker().analyze(qimage_from_rgb(structured))

        self.assertGreater(
            result.original.mvp.score,
            result.shuffled.mvp.score + 20.0,
        )
        self.assertGreater(
            result.original.mvp.score,
            result.random.mvp.score + 20.0,
        )
        self.assertGreater(
            result.original.robust.score,
            result.shuffled.robust.score + 20.0,
        )
        self.assertGreater(
            result.original.robust.score,
            result.random.robust.score + 20.0,
        )


if __name__ == "__main__":
    unittest.main()

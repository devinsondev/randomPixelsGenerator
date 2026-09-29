import unittest

from PySide6.QtGui import QColor, QImage

from tools.clipboard_resizer.resizer import (
    ResizeFilter,
    ResizeMode,
    resize_image,
)


class ClipboardResizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.image = QImage(200, 100, QImage.Format_RGB888)
        self.image.fill(QColor("white"))

    def test_stretch_produces_exact_dimensions(self) -> None:
        result = resize_image(
            self.image,
            64,
            64,
            ResizeMode.STRETCH,
            ResizeFilter.NEAREST,
        )

        self.assertEqual((result.width(), result.height()), (64, 64))

    def test_fit_produces_exact_canvas_with_letterbox(self) -> None:
        result = resize_image(
            self.image,
            64,
            64,
            ResizeMode.FIT,
            ResizeFilter.NEAREST,
        )

        self.assertEqual((result.width(), result.height()), (64, 64))
        self.assertEqual(result.pixelColor(0, 0), QColor("black"))
        self.assertEqual(result.pixelColor(32, 32), QColor("white"))

    def test_cover_produces_exact_dimensions_without_letterbox(self) -> None:
        result = resize_image(
            self.image,
            64,
            64,
            ResizeMode.COVER,
            ResizeFilter.NEAREST,
        )

        self.assertEqual((result.width(), result.height()), (64, 64))
        self.assertEqual(result.pixelColor(0, 0), QColor("white"))


if __name__ == "__main__":
    unittest.main()

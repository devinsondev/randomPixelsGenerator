from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter


class ResizeMode(str, Enum):
    STRETCH = "stretch"
    FIT = "fit"
    COVER = "cover"


class ResizeFilter(str, Enum):
    NEAREST = "nearest"
    SMOOTH = "smooth"


def resize_image(
    image: QImage,
    width: int,
    height: int,
    mode: ResizeMode,
    resize_filter: ResizeFilter,
) -> QImage:
    """Resize a QImage to an exact output canvas size."""
    if image.isNull():
        raise ValueError("image must not be null.")
    if width < 1 or height < 1:
        raise ValueError("width and height must be positive.")

    transform = (
        Qt.FastTransformation
        if resize_filter == ResizeFilter.NEAREST
        else Qt.SmoothTransformation
    )

    if mode == ResizeMode.STRETCH:
        return image.scaled(
            width,
            height,
            Qt.IgnoreAspectRatio,
            transform,
        )

    aspect_mode = (
        Qt.KeepAspectRatio
        if mode == ResizeMode.FIT
        else Qt.KeepAspectRatioByExpanding
    )
    scaled = image.scaled(
        width,
        height,
        aspect_mode,
        transform,
    )

    if mode == ResizeMode.COVER:
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        return scaled.copy(x, y, width, height)

    canvas = QImage(width, height, QImage.Format_RGB888)
    canvas.fill(QColor("black"))

    painter = QPainter(canvas)
    try:
        x = (width - scaled.width()) // 2
        y = (height - scaled.height()) // 2
        painter.drawImage(x, y, scaled)
    finally:
        painter.end()

    return canvas

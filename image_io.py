from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def save_rgb_png(image: NDArray[np.generic], path: Path) -> None:
    """Save a uint8 RGB NumPy array as a PNG using only the standard library."""
    rgb = np.asarray(image)

    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("Expected image with shape (height, width, 3).")
    if rgb.dtype != np.uint8:
        raise TypeError("Expected image dtype uint8.")

    rgb = np.ascontiguousarray(rgb)
    height, width, _ = rgb.shape
    path.parent.mkdir(parents=True, exist_ok=True)

    scanlines = bytearray()
    for row in rgb:
        scanlines.append(0)
        scanlines.extend(row.tobytes(order="C"))

    payload = (
        _PNG_SIGNATURE
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(scanlines), level=3))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    checksum = zlib.crc32(body) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + body + struct.pack(">I", checksum)

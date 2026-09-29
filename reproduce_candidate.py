from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from image_io import save_rgb_png
from random_frame import generate_rgb_frame


def reproduce(sidecar: Path, output: Path | None = None) -> Path:
    payload = json.loads(sidecar.read_text(encoding="utf-8"))

    width = int(payload["width"])
    height = int(payload["height"])
    frame_seed = int(payload["frame_seed"])

    image = generate_rgb_frame(
        width=width,
        height=height,
        frame_seed=frame_seed,
    )
    digest = hashlib.sha256(
        np.ascontiguousarray(image).tobytes(order="C")
    ).hexdigest()

    expected = str(payload["pixel_sha256"])
    if digest != expected:
        raise RuntimeError(
            f"Reproduction hash mismatch: expected {expected}, got {digest}."
        )

    target = output or sidecar.with_name(
        f"{sidecar.stem}_reproduced.png"
    )
    save_rgb_png(image, target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce a saved candidate from its JSON sidecar."
    )
    parser.add_argument("sidecar", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    target = reproduce(args.sidecar, args.output)
    print(f"Reproduced and hash-verified: {target}")


if __name__ == "__main__":
    main()

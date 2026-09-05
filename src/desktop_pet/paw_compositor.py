"""Alpha-exact, independently transformed forepaw presentation."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from PIL import Image

from .model import Rect


def load_rle_masks(path: Path) -> tuple[Image.Image, Image.Image]:
    """Reconstruct exact alpha masks from the reviewable row-RLE document."""
    definition = json.loads(path.read_text(encoding="utf-8"))
    if definition.get("encoding") != "row-rle-v1":
        raise ValueError("unsupported paw mask encoding")
    try:
        width, height = (int(value) for value in definition["source_size"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid paw mask source size") from error
    if (width, height) != (512, 768):
        raise ValueError("paw masks must use 512x768 source coordinates")
    decoded = []
    for name in ("left", "right"):
        image = Image.new("L", (width, height))
        occupied: set[tuple[int, int]] = set()
        try:
            runs = definition["masks"][name]
        except (KeyError, TypeError) as error:
            raise ValueError(f"missing {name} paw RLE") from error
        for run in runs:
            if not isinstance(run, list) or len(run) != 4:
                raise ValueError(f"invalid {name} paw RLE run")
            y, start, length, alpha = (int(value) for value in run)
            if not (0 <= y < height and 0 <= start < width and length > 0
                    and start + length <= width and 1 <= alpha <= 255):
                raise ValueError(f"out-of-bounds {name} paw RLE run")
            for x in range(start, start + length):
                if (x, y) in occupied:
                    raise ValueError(f"overlapping {name} paw RLE run")
                occupied.add((x, y))
                image.putpixel((x, y), alpha)
        if image.getbbox() is None:
            raise ValueError(f"empty {name} paw mask")
        expected = definition.get("decoded_alpha_sha256", {}).get(name)
        actual = hashlib.sha256(image.tobytes()).hexdigest()
        if expected != actual:
            raise ValueError(f"{name} paw decoded Alpha SHA-256 mismatch")
        decoded.append(image)
    return decoded[0], decoded[1]


class PawCompositor:
    def __init__(self, left_mask: Image.Image, right_mask: Image.Image) -> None:
        self.masks = {"left": left_mask.convert("L"), "right": right_mask.convert("L")}
        if left_mask.size != right_mask.size:
            raise ValueError("paw masks must share source coordinates")
        self.source_size = left_mask.size

    def hit_test(self, paw: str, point: tuple[int, int], window: Rect) -> bool:
        if window.width <= 0 or window.height <= 0:
            return False
        x = int((point[0] - window.x) * self.source_size[0] / window.width)
        y = int((point[1] - window.y) * self.source_size[1] / window.height)
        return (0 <= x < self.source_size[0] and 0 <= y < self.source_size[1]
                and self.masks[paw].getpixel((x, y)) > 0)

    def compose(self, source: Image.Image, *, left_offset=(0, 0),
                right_offset=(0, 0)) -> Image.Image:
        result = source.convert("RGBA").copy()
        for paw, offset in (("left", left_offset), ("right", right_offset)):
            mask = self.masks[paw]
            if mask.size != result.size:
                mask = mask.resize(result.size, Image.Resampling.NEAREST)
            layer = Image.new("RGBA", result.size)
            layer.paste(result, mask=mask)
            moved = Image.new("RGBA", result.size)
            moved.alpha_composite(layer, dest=(int(offset[0]), int(offset[1])))
            result.alpha_composite(moved)
        return result

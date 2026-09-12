"""Alpha-exact, independently transformed forepaw presentation."""

from __future__ import annotations

import json
import hashlib
import base64
from pathlib import Path
import zlib
from dataclasses import dataclass

from PIL import Image

from .model import Rect


@dataclass(frozen=True)
class GeneratedPawFrames:
    layers: dict[str, tuple[Image.Image, ...]]
    replacement_masks: dict[str, tuple[Image.Image, ...]]


def load_generated_paw_frames(path: Path, *, source_sha256: str) -> GeneratedPawFrames:
    payload = json.loads(path.read_text(encoding="utf-8"))
    full_cat = payload.get("encoding") == "generated-full-cat-zlib-base85-v1"
    if not full_cat and payload.get("encoding") != "generated-local-replacement-zlib-base85-v1":
        raise ValueError("unsupported generated paw encoding")
    if payload.get("source_size") != [512, 768] or payload.get("source_sha256") != source_sha256:
        raise ValueError("generated paw source identity mismatch")
    frame_map = payload["frame_map"]
    if len(frame_map) != 15 or frame_map[0] is not None or frame_map[-1] is not None:
        raise ValueError("generated paw must restore default at both timeline endpoints")
    layers, masks = {}, {}
    for side in ("left", "right"):
        definition = payload["sides"][side]
        if full_cat:
            # Complete images, including transparent pixels, replace the whole
            # canonical canvas. Never cut/feather generated legs onto old fur.
            images = []
            for frame in definition["frames"]:
                raw = zlib.decompress(base64.b85decode(frame["rgba_zlib_base85"]))
                if len(raw) != 512 * 768 * 4 or hashlib.sha256(raw).hexdigest() != frame["rgba_sha256"]:
                    raise ValueError("generated full-cat frame size or hash mismatch")
                image = Image.frombytes("RGBA", (512, 768), raw)
                alpha = image.getchannel("A")
                box = alpha.getbbox()
                if box is None or alpha.getextrema()[0] != 0:
                    raise ValueError("full-cat frame requires a nonempty transparent background")
                if box[0] == 0 or box[1] == 0 or box[2] == 512 or box[3] == 768:
                    raise ValueError("full-cat frame touches canvas boundary")
                images.append(image)
            if any(index is not None and (type(index) is not int or not 0 <= index < len(images)) for index in frame_map):
                raise ValueError("generated paw timeline references a missing pose")
            layers[side] = tuple(Image.new("RGBA", (512, 768)) if index is None else images[index] for index in frame_map)
            masks[side] = tuple(Image.new("L", (512, 768), 0 if index is None else 255) for index in frame_map)
            continue
        left, top, right, bottom = definition["bbox"]
        if not (0 <= left < right <= 512 and 440 <= top < bottom <= 768):
            raise ValueError("paw patch crosses the locked head or canvas boundary")
        size = (right - left, bottom - top)
        local_layers, local_masks = [], []
        for patch in definition["patches"]:
            decoded = []
            for prefix, mode, channels in (("rgba", "RGBA", 4), ("mask", "L", 1)):
                raw = zlib.decompress(base64.b85decode(patch[prefix + "_zlib_base85"]))
                if len(raw) != size[0] * size[1] * channels or hashlib.sha256(raw).hexdigest() != patch[prefix + "_sha256"]:
                    raise ValueError("generated paw patch size or hash mismatch")
                image = Image.frombytes(mode, size, raw)
                canvas = Image.new(mode, (512, 768))
                canvas.paste(image, (left, top))
                decoded.append(canvas)
            local_layers.append(decoded[0]); local_masks.append(decoded[1])
        if any(index is not None and (type(index) is not int or not 0 <= index < len(local_layers)) for index in frame_map):
            raise ValueError("generated paw timeline references a missing pose")
        empty_layer = Image.new("RGBA", (512, 768))
        empty_mask = Image.new("L", (512, 768))
        layers[side] = tuple(empty_layer if index is None else local_layers[index] for index in frame_map)
        masks[side] = tuple(empty_mask if index is None else local_masks[index] for index in frame_map)
    return GeneratedPawFrames(layers, masks)


def disjoint_paw_masks(
    left: Image.Image, right: Image.Image
) -> tuple[Image.Image, Image.Image]:
    """Resolve hand-authored edge overlap to exactly one cat-own forepaw."""
    left, right = left.copy(), right.copy()
    left_box, right_box = left.getbbox(), right.getbbox()
    if left_box is None or right_box is None:
        raise ValueError("empty paw mask")
    left_center = (left_box[0] + left_box[2] - 1) / 2
    right_center = (right_box[0] + right_box[2] - 1) / 2
    overlap = []
    for y in range(max(left_box[1], right_box[1]), min(left_box[3], right_box[3])):
        for x in range(max(left_box[0], right_box[0]), min(left_box[2], right_box[2])):
            if left.getpixel((x, y)) and right.getpixel((x, y)):
                overlap.append((x, y))
    for x, y in overlap:
        if abs(x - left_center) <= abs(x - right_center):
            right.putpixel((x, y), 0)
        else:
            left.putpixel((x, y), 0)
    return left, right


def load_paw_frames(
    path: Path, *, source_sha256: str | None = None
) -> dict[str, tuple[Image.Image, ...]]:
    """Restore authored RGBA keyframes losslessly from the text frame pack."""
    definition = json.loads(path.read_text(encoding="utf-8"))
    if definition.get("encoding") != "rgba-crop-zlib-base85-v1":
        raise ValueError("unsupported paw frame encoding")
    if source_sha256 is not None and definition.get("source_sha256") != source_sha256:
        raise ValueError("paw frame source SHA-256 mismatch")
    if definition.get("timeline_ms") != [
        0, 40, 80, 120, 200, 240, 280, 320, 360,
        400, 440, 480, 520, 560, 600,
    ]:
        raise ValueError("invalid paw frame timeline")
    restored: dict[str, tuple[Image.Image, ...]] = {}
    for side in ("left", "right"):
        frames = []
        for item in definition.get("frames", {}).get(side, ()):
            left, top, right, bottom = (int(value) for value in item["bbox"])
            width, height = right - left, bottom - top
            rgba = zlib.decompress(base64.b85decode(item["rgba_zlib_base85"]))
            if len(rgba) != width * height * 4:
                raise ValueError(f"invalid {side} paw frame size")
            if hashlib.sha256(rgba).hexdigest() != item["rgba_sha256"]:
                raise ValueError(f"invalid {side} paw frame SHA-256")
            crop = Image.frombytes("RGBA", (width, height), rgba)
            layer = Image.new("RGBA", tuple(definition["source_size"]))
            layer.alpha_composite(crop, (left, top))
            frames.append(layer)
        if len(frames) != 15:
            raise ValueError(f"{side} paw must contain exactly 15 keyframes")
        restored[side] = tuple(frames)
    return restored


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
    def __init__(self, left_mask: Image.Image, right_mask: Image.Image,
                 frames: dict[str, tuple[Image.Image, ...]] | GeneratedPawFrames | None = None) -> None:
        left_mask, right_mask = disjoint_paw_masks(
            left_mask.convert("L"), right_mask.convert("L")
        )
        self.masks = {"left": left_mask, "right": right_mask}
        if left_mask.size != right_mask.size:
            raise ValueError("paw masks must share source coordinates")
        self.source_size = left_mask.size
        self.replacement_masks = frames.replacement_masks if isinstance(frames, GeneratedPawFrames) else None
        self.frames = frames.layers if isinstance(frames, GeneratedPawFrames) else frames or {}

    def hit_test(self, paw: str, point: tuple[int, int], window: Rect) -> bool:
        if window.width <= 0 or window.height <= 0:
            return False
        rendered_width = round(self.source_size[1] * window.width / window.height)
        inset_x = max(0, (rendered_width - self.source_size[0]) // 2)
        x = int((point[0] - window.x) * rendered_width / window.width) - inset_x
        y = int((point[1] - window.y) * self.source_size[1] / window.height)
        return (0 <= x < self.source_size[0] and 0 <= y < self.source_size[1]
                and self.masks[paw].getpixel((x, y)) > 0)

    def compose_frame(self, source: Image.Image, side: str, index: int) -> Image.Image:
        """Composite one pre-authored photo keyframe; no runtime deformation."""
        if index in (0, 14):
            return source.convert("RGBA").copy()
        layer = self.frames[side][index]
        result = source.convert("RGBA").copy()
        inset_x = (result.width - self.source_size[0]) // 2
        if inset_x < 0 or result.height != self.source_size[1]:
            raise ValueError("paw frame canvas is incompatible with rendered pose")
        aligned_layer = Image.new("RGBA", result.size)
        aligned_layer.alpha_composite(layer, (inset_x, 0))
        if self.replacement_masks is not None:
            replacement = Image.new("L", result.size)
            replacement.paste(self.replacement_masks[side][index], (inset_x, 0))
            # Generated pixels contain the exposed belly as well as the limb.
            # Replacement clears the old limb instead of alpha-overlapping it.
            result.paste(aligned_layer, mask=replacement)
            return result
        mask = Image.new("L", result.size)
        mask.paste(
            self.masks[side].point(lambda value: 255 if value else 0),
            (inset_x, 0),
        )
        presence = aligned_layer.getchannel("A").point(
            lambda value: 255 if value else 0
        )
        clear = Image.new("L", result.size)
        clear.paste(255, mask=mask)
        clear.paste(255, mask=presence)
        result.paste((0, 0, 0, 0), mask=clear)
        result.paste(aligned_layer, mask=presence)
        other = "right" if side == "left" else "left"
        other_mask = Image.new("L", result.size)
        other_mask.paste(
            self.masks[other].point(lambda value: 255 if value else 0),
            (inset_x, 0),
        )
        result.paste(source.convert("RGBA"), mask=other_mask)
        return result

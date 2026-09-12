"""Build deterministic, reviewable text-packed PAWS photo frames."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
import zlib

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.paw_compositor import disjoint_paw_masks, load_rle_masks


AUTHORING = ROOT / "assets" / "paws" / "v1" / "authoring.json"
SOURCE = ROOT / "assets" / "rig" / "v1" / "source" / "eye-neutral-v1" / "body-backplate.png"
OUTPUT = ROOT / "assets" / "paws" / "v1" / "frames.json"
KEYFRAMES = (
    (0, "default", 0),
    (40, "lift", -2),
    (80, "lift", -4),
    (120, "prepare", -6),
    (200, "press", -6),
    (240, "press", -4),
    (280, "press", -1),
    (320, "press", 2),
    (360, "pressed", 5),
    (400, "release", 4),
    (440, "release", 3),
    (480, "return", 2),
    (520, "return", 1),
    (560, "return", 0),
    (600, "default", 0),
)


def _frame_layer(source: Image.Image, mask: Image.Image, distal_y: int) -> tuple[tuple[int, int, int, int], bytes]:
    binary = mask.point(lambda value: 255 if value else 0)
    bbox = binary.getbbox()
    if bbox is None:
        raise ValueError("empty paw mask")
    left, top, right, bottom = bbox
    padding = 8
    out_bbox = (
        max(0, left - padding),
        max(0, top + min(0, distal_y) - padding),
        min(source.width, right + padding),
        min(source.height, bottom + max(0, distal_y) + padding),
    )
    width, height = out_bbox[2] - out_bbox[0], out_bbox[3] - out_bbox[1]
    layer = Image.new("RGBA", (width, height))
    pixels = source.load()
    alpha = binary.load()
    target = layer.load()
    span = max(1, bottom - top - 1)
    mapped_rows = []
    for source_y in range(top, bottom):
        progress = (source_y - top) / span
        y_offset = distal_y * progress * progress * (3.0 - 2.0 * progress)
        mapped_rows.append(source_y + y_offset)
    for absolute_target_y in range(out_bbox[1], out_bbox[3]):
        source_y = min(
            range(top, bottom),
            key=lambda candidate: abs(mapped_rows[candidate - top] - absolute_target_y),
        )
        if abs(mapped_rows[source_y - top] - absolute_target_y) > 0.75:
            continue
        target_y = absolute_target_y - out_bbox[1]
        for source_x in range(left, right):
            pixel = pixels[source_x, source_y]
            if (alpha[source_x, source_y] and pixel[3] > 0
                    and 0 <= target_y < height):
                target[source_x - out_bbox[0], target_y] = pixel
    return out_bbox, layer.tobytes()


def build(output: Path = OUTPUT) -> dict:
    source = Image.open(SOURCE).convert("RGBA")
    masks = dict(zip(
        ("left", "right"), disjoint_paw_masks(*load_rle_masks(AUTHORING))
    ))
    payload = {
        "version": 1,
        "encoding": "rgba-crop-zlib-base85-v1",
        "source_size": list(source.size),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "timeline_ms": [item[0] for item in KEYFRAMES],
        "frames": {},
    }
    for side, mask in masks.items():
        frames = []
        for time_ms, phase, distal_y in KEYFRAMES:
            bbox, rgba = _frame_layer(source, mask, distal_y)
            frames.append({
                "time_ms": time_ms,
                "phase": phase,
                "distal_y": distal_y,
                "bbox": list(bbox),
                "rgba_sha256": hashlib.sha256(rgba).hexdigest(),
                "rgba_zlib_base85": base64.b85encode(zlib.compress(rgba, 9)).decode("ascii"),
            })
        payload["frames"][side] = frames
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    build()

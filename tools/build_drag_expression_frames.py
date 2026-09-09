"""Author deterministic drag-expression frames from approved V2.1 layers.

The generated PNGs are review artifacts. Git stores only the lossless ASCII pack.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/rig/v1/source/eye-neutral-v1"
CANONICAL = ROOT / "assets/rig/v1/source/canonical-idle.png"
OUTPUT = ROOT / "assets/drag-expectation/v1"
APPROVED = {
    "canonical-idle.png": "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7",
    "underlay.png": "d83230b60fe753b7344ae0b349d0c1409b47dc2002df66c5689765fcb0ca2495",
    "eye-left.png": "6140a3a4085d8514795ea2c17ee2173964553c604f0d096a120a508fa9f7308c",
    "eye-right.png": "9528b5f3c985b8366003fd77d413ff564b50ae547c705e5e6aee85fc86542906",
    "eye-left-mask.png": "27bee30342e67cab45d77a14ad7eebb0125f72d4b19039b5c3c1bf506623a81c",
    "eye-right-mask.png": "fba54f4eb10884d5a284ea6c16cd762d0786f61e09ddc5297e99d793c3a092e4",
    "head-cutout.png": "6e57c1be03db1a97a484576f6f88be8639d8f01bbfe5b0d792c68e3d985864e6",
}
FRAME_SPECS = (
    ("neutral", 1.0, 0, 0, 50),
    ("enter-1", 1.067, 0, 0, 50),
    ("enter-2", 1.133, 0, 0, 50),
    ("hold-left", 1.20, -1, 1, 100),
    ("hold-right", 1.20, 1, -1, 100),
)


def _read(name: str, path: Path) -> bytes:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != APPROVED[name]:
        raise ValueError(f"approved source hash mismatch: {name}")
    return data


def _image(name: str, path: Path) -> Image.Image:
    with Image.open(BytesIO(_read(name, path))) as opened:
        result = opened.copy()
        result.load()
        return result


def _scaled_layer(layer: Image.Image, scale: float, dx: int) -> Image.Image:
    bbox = layer.getchannel("A").getbbox()
    assert bbox is not None
    crop = layer.crop(bbox)
    size = (round(crop.width * scale), round(crop.height * scale))
    crop = crop.resize(size, Image.Resampling.LANCZOS)
    x = round((bbox[0] + bbox[2] - size[0]) / 2) + dx
    y = round((bbox[1] + bbox[3] - size[1]) / 2)
    result = Image.new("RGBA", layer.size)
    result.alpha_composite(crop, (x, y))
    return result


def author_frames() -> list[tuple[tuple, Image.Image]]:
    canonical = _image("canonical-idle.png", CANONICAL)
    underlay = _image("underlay.png", SOURCE / "underlay.png")
    eyes = [_image(f"eye-{side}.png", SOURCE / f"eye-{side}.png") for side in ("left", "right")]
    masks = [_image(f"eye-{side}-mask.png", SOURCE / f"eye-{side}-mask.png") for side in ("left", "right")]
    cleanup = ImageChops.lighter(*masks).filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(2))
    cleaned = Image.composite(underlay, canonical, cleanup)
    head = _image("head-cutout.png", SOURCE / "head-cutout.png")
    head_mask = Image.new("L", canonical.size)
    head_mask.paste(head.getchannel("A"), (24, 204))
    contour = ImageChops.subtract(head_mask.filter(ImageFilter.MaxFilter(5)), head_mask.filter(ImageFilter.MinFilter(5)))
    authored = []
    for index, spec in enumerate(FRAME_SPECS):
        frame_id, scale, left_dx, right_dx, _duration = spec
        if index == 0:
            frame = canonical.copy()
        else:
            frame = cleaned.copy()
            frame.alpha_composite(_scaled_layer(eyes[0], scale, left_dx))
            frame.alpha_composite(_scaled_layer(eyes[1], scale, right_dx))
            glow = Image.new("RGBA", frame.size, (255, 232, 112, min(44, index * 15)))
            frame = Image.composite(Image.alpha_composite(frame, glow), frame, contour)
        authored.append((spec, frame))
    return authored


def build(output: Path, preview: Path | None = None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    records, encoded = [], {}
    frames = author_frames()
    for spec, frame in frames:
        frame_id, scale, left_dx, right_dx, duration = spec
        if frame_id == "neutral":
            png = _read("canonical-idle.png", CANONICAL)
        else:
            stream = BytesIO()
            frame.save(stream, format="PNG", compress_level=9, optimize=False)
            png = stream.getvalue()
        sha = hashlib.sha256(png).hexdigest()
        records.append({"id": frame_id, "eye_scale": scale, "left_dx": left_dx, "right_dx": right_dx, "duration_ms": duration, "png_sha256": sha})
        encoded[frame_id] = base64.b85encode(png).decode("ascii")
        if preview is not None:
            preview.mkdir(parents=True, exist_ok=True)
            (preview / f"{frame_id}.png").write_bytes(png)
    manifest = {
        "schema": 1,
        "canvas": [512, 768],
        "approved_default_sha256": APPROVED["canonical-idle.png"],
        "source_sha256": APPROVED,
        "enter_duration_ms": 150,
        "hold_duration_ms": 100,
        "exit_duration_ms": 150,
        "refresh_hz": 30,
        "frames": records,
        "sequence": {"enter": ["neutral", "enter-1", "enter-2", "hold-left"], "hold": ["hold-left", "hold-right"], "exit": ["enter-2", "enter-1", "neutral"]},
        "acceptance": "pending-user-windows",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "frames.pack.json").write_text(json.dumps({"encoding": "base85-png", "frames": encoded}, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    build(args.output, args.preview)

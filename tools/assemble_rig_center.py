from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageChops


CANVAS = (512, 768)


def _clean_hidden_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    rgba.putdata(
        [(0, 0, 0, 0) if a == 0 else (r, g, b, a) for r, g, b, a in rgba.getdata()]
    )
    return rgba


def normalize_fill(generated: Image.Image, mask: Image.Image) -> Image.Image:
    rgba = generated.convert("RGBA")
    if rgba.size != CANVAS:
        if rgba.width * CANVAS[1] != rgba.height * CANVAS[0]:
            raise ValueError("generated fill must keep the canonical 2:3 aspect ratio")
        rgba = rgba.resize(CANVAS, Image.Resampling.LANCZOS)
    clipped = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    clipped.paste(rgba, (0, 0), mask)
    return _clean_hidden_rgb(clipped)


def _masked(image: Image.Image, mask: Image.Image) -> Image.Image:
    layer = image.convert("RGBA").copy()
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return _clean_hidden_rgb(layer)


def _composite(*layers: Image.Image) -> Image.Image:
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer in layers:
        result.alpha_composite(layer)
    return _clean_hidden_rgb(result)


def assemble_center(source_root: Path, sample_root: Path) -> dict[str, object]:
    source_root, sample_root = Path(source_root), Path(sample_root)
    layers_root = source_root / "layers"
    layers_root.mkdir(parents=True, exist_ok=True)
    sample_root.mkdir(parents=True, exist_ok=True)
    with Image.open(source_root / "canonical-idle.png") as opened:
        canonical = opened.convert("RGBA")
    masks = {}
    for stem in ("dynamic-head-neck", "body-fill", "eye-left", "eye-right"):
        with Image.open(source_root / "masks" / f"{stem}-mask.png") as opened:
            masks[stem] = opened.convert("L")
    with Image.open(source_root / "ai" / "body-fill-raw.png") as opened:
        body_fill = normalize_fill(opened, masks["body-fill"])
    with Image.open(source_root / "ai" / "eye-fill-raw.png") as opened:
        eye_fill = normalize_fill(
            opened, ImageChops.lighter(masks["eye-left"], masks["eye-right"])
        )
    static_mask = ImageChops.invert(masks["dynamic-head-neck"])
    body_base = _composite(
        _masked(canonical, static_mask), _masked(body_fill, static_mask)
    )
    eye_mask = ImageChops.lighter(masks["eye-left"], masks["eye-right"])
    solid_eye_mask = eye_mask.point(lambda value: 255 if value == 255 else 0)
    eye_underlay = Image.composite(eye_fill, canonical, solid_eye_mask)
    head_neck = _masked(eye_underlay, masks["dynamic-head-neck"])
    eye_left = _masked(canonical, masks["eye-left"])
    eye_right = _masked(canonical, masks["eye-right"])
    composite = _composite(body_base, head_neck, eye_left, eye_right)
    difference = ImageChops.difference(composite, canonical)
    changed = sum(1 for pixel in difference.getdata() if pixel != (0, 0, 0, 0))
    maximum = max(max(pixel) for pixel in difference.getdata())
    if changed or maximum:
        raise RuntimeError(f"center recomposition drift: {changed} pixels, max {maximum}")
    outputs = {
        "body_base.png": body_base,
        "head_neck_base.png": head_neck,
        "eye_left.png": eye_left,
        "eye_right.png": eye_right,
        "eye_left_mask.png": masks["eye-left"],
        "eye_right_mask.png": masks["eye-right"],
    }
    for name, image in outputs.items():
        image.save(layers_root / name, optimize=True)
    composite.save(sample_root / "composite.png", optimize=True)
    return {
        "changed_pixels": changed,
        "maximum_channel_delta": maximum,
        "composite_sha256": hashlib.sha256(
            (sample_root / "composite.png").read_bytes()
        ).hexdigest(),
    }

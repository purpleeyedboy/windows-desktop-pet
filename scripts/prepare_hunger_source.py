#!/usr/bin/env python3
"""Recover the supplied checker-backed art with its supplied mask, without redrawing.

This authoring-only command needs Pillow and NumPy (requirements-assets.txt).
Windows builds consume the resulting lossless text source and do not run it.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import textwrap

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "assets/hunger/source"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _grow(value: np.ndarray) -> np.ndarray:
    result = value.copy()
    result[1:] |= value[:-1]
    result[:-1] |= value[1:]
    result[:, 1:] |= value[:, :-1]
    result[:, :-1] |= value[:, 1:]
    return result


def _shrink(value: np.ndarray) -> np.ndarray:
    result = value.copy()
    result[1:] &= value[:-1]
    result[:-1] &= value[1:]
    result[:, 1:] &= value[:, :-1]
    result[:, :-1] &= value[:, 1:]
    result[[0, -1], :] = False
    result[:, [0, -1]] = False
    return result


def _propagate(seed: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    current = seed & allowed
    while True:
        following = _grow(current) & allowed
        if np.array_equal(current, following):
            return current
        current = following


def recover_alpha(rgb: np.ndarray, supplied_mask: np.ndarray) -> Image.Image:
    """Remove only border-connected checker pixels in an uncertainty band.

    The mask's interior is immutable. Eroded/dilated masks define confidence
    regions only; neither becomes the output silhouette. Dark bells and narrow
    connections are retained whenever the RGB art differs from the checker.
    """
    mask = supplied_mask >= 128
    inside, outer = mask.copy(), mask.copy()
    for _ in range(10):
        inside = _shrink(inside)
    for _ in range(3):
        outer = _grow(outer)
    color = rgb.astype(np.float32)
    # Both sampled scanlines are entirely empty background in these supplied
    # sheets. Their signs and transition ramps identify the checker phase.
    x_phase = np.clip((color[5].mean(axis=1) - 230) / 23, -1, 1)
    y_phase = np.clip((color[:, 5].mean(axis=1) - 230) / 23, -1, 1)
    weight = (x_phase[None, :] * y_phase[:, None] + 1) / 2
    background = (
        np.array([207, 206, 209]) * (1 - weight[:, :, None])
        + np.array([253, 253, 253]) * weight[:, :, None]
    )
    checker = (
        (np.max(np.abs(color - background), axis=2) < 18)
        & ((color.max(axis=2) - color.min(axis=2)) < 9)
    )
    removed = _propagate(~outer, (checker & ~inside) | ~outer)
    candidate = outer & ~removed
    # Discard disconnected background crumbs, keeping all details connected to
    # the original solid body. No pose is resized or shifted here.
    retained = _propagate(inside, candidate)
    alpha = Image.fromarray((retained * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.35))
    result = np.dstack((rgb.copy(), np.asarray(alpha))).astype(np.uint8)
    result[result[:, :, 3] == 0, :3] = 0
    return Image.fromarray(result, "RGBA")


def prepare(color_path: Path, mask_path: Path) -> dict:
    manifest_path = SOURCE_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    color_bytes, mask_bytes = color_path.read_bytes(), mask_path.read_bytes()
    with Image.open(io.BytesIO(color_bytes)) as opened:
        rgb = np.asarray(opened.convert("RGB"))
    with Image.open(io.BytesIO(mask_bytes)) as opened:
        mask = np.asarray(opened.convert("L"))
    if rgb.shape[:2] != mask.shape or list(rgb.shape[1::-1]) != manifest["source_canvas"]:
        raise ValueError("the supplied color and mask must match the declared source canvas")
    previous_bytes = base64.b64decode(b"".join((SOURCE_ROOT / manifest["source_file"]).read_bytes().split()), validate=True)
    with Image.open(io.BytesIO(previous_bytes)) as opened:
        previous = np.asarray(opened.convert("RGBA"))
    core = previous[:, :, 3] >= 240
    if not core.any() or not np.array_equal(previous[:, :, :3][core], rgb[core]):
        raise ValueError("recovered source RGB does not match the previously committed cat interior")
    result = recover_alpha(rgb, mask)
    rgba = np.asarray(result)
    # Bell ROI is source-space, before normalization, and excludes most neck.
    bell_roi = (slice(273, 301), slice(165, 194))
    before = int(np.count_nonzero(mask[bell_roi] >= 128))
    after = int(np.count_nonzero(rgba[bell_roi][..., 3] >= 128))
    if after < before * 0.75:
        raise ValueError("alpha preparation would cut away the original bell")
    encoded = io.BytesIO()
    result.save(encoded, "WEBP", lossless=True, exact=True, method=6)
    webp = encoded.getvalue()
    with Image.open(io.BytesIO(webp)) as opened:
        if opened.convert("RGBA").tobytes() != result.tobytes():
            raise ValueError("WebP encoding did not preserve exact RGBA pixels")
    manifest.setdefault("previous_alpha_processing", manifest["alpha_processing"])
    manifest.setdefault("previous_source_webp_sha256", manifest["source_webp_sha256"])
    manifest.setdefault("previous_input_color_sha256", manifest["input_color_sha256"])
    manifest["input_color_sha256"] = _sha(color_bytes)
    manifest["input_alpha_sha256"] = _sha(mask_bytes)
    manifest["input_color_rgb_sha256"] = _sha(rgb.tobytes())
    manifest["input_alpha_luma_sha256"] = _sha(mask.tobytes())
    manifest["source_webp_sha256"] = _sha(webp)
    manifest["source_rgba_sha256"] = _sha(result.tobytes())
    manifest["matte_revision"] = 2
    manifest["alpha_processing"] = {
        "method": "border-connected-checker-removal-with-protected-mask-interior",
        "mask_threshold": 128,
        "uncertainty_inner_pixels": 10,
        "uncertainty_outer_pixels": 3,
        "edge_contract_source_pixels": 0,
        "edge_feather_sigma": 0.35,
        "checker_rgb_tolerance": 18,
        "checker_chroma_tolerance": 9,
        "bell_original_mask_opaque_pixels": before,
        "bell_recovered_opaque_pixels": after,
        "previous_solid_rgb_match_pixels": manifest.get("alpha_processing", {}).get("previous_solid_rgb_match_pixels", int(core.sum())),
    }
    text = "\n".join(textwrap.wrap(base64.b64encode(webp).decode("ascii"), 120)) + "\n"
    (SOURCE_ROOT / manifest["source_file"]).write_text(text, "ascii")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", "utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--color", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.color, args.mask)
    print(json.dumps({key: manifest[key] for key in ("source_webp_sha256", "source_rgba_sha256", "alpha_processing")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

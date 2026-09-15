"""Recover the delivered right-paw atlas using its mask and magenta backdrop."""
from __future__ import annotations

import argparse
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import textwrap

from PIL import Image, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from desktop_pet.groom_import import RIGHT_SHEET_SIZE, build_alpha

COLOR_SHA256 = "d0241556bdb3ab2c0def893b1a7c08f54972a4d1d49342ccd8c49ee201cb1e56"
MASK_SHA256 = "a1b58e4e492739b024088e74a50dda47123fca0092abb72d327629cf41bfacaa"
UNDERBELLY_SHA256 = "58b4a5c48257c0c29639b58c0db3f935a85bbc81a42070f653ba7efcf46867fe"
UNDERBELLY_BOX = (232, 606, 423, 762)


def recover_sheet(color_path: Path, mask_path: Path) -> Image.Image:
    for path, expected in ((color_path, COLOR_SHA256), (mask_path, MASK_SHA256)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"right-paw input differs from the reviewed original: {path.name}")
    color = Image.open(color_path).convert("RGB")
    mask = Image.open(mask_path).convert("L")
    if color.size != RIGHT_SHEET_SIZE or mask.size != RIGHT_SHEET_SIZE:
        raise ValueError("right-paw inputs must share the reviewed 1180x1333 canvas")
    return remove_magenta_backdrop(color, build_alpha(mask))


def remove_magenta_backdrop(color: Image.Image, alpha: Image.Image) -> Image.Image:
    red, green, blue = color.split()
    magenta = ImageChops.subtract(ImageChops.darker(red, blue), green)
    # The supplied silhouette fills some true gaps between the front paw and
    # hindquarters. Recover those holes from the source's solid magenta color;
    # never shrink the whole silhouette to remove a few background pixels.
    backdrop = magenta.point(lambda value: 255 if value >= 180 else 0)
    edge = backdrop.filter(ImageFilter.MaxFilter(7))
    pixels, alphas = color.load(), alpha.load()
    spill, near_backdrop = magenta.load(), edge.load()
    for y in range(color.height):
        for x in range(color.width):
            original_alpha = alphas[x, y]
            excess = spill[x, y]
            if near_backdrop[x, y] and excess > 0:
                opacity = min(original_alpha, max(0, 255 - excess))
                if excess >= 240 or opacity < 8:
                    opacity = 0
                if opacity:
                    r, g, b = pixels[x, y]
                    # Remove only the known backdrop contribution at this edge.
                    pixels[x, y] = (
                        min(255, max(0, round((r - (255 - opacity)) * 255 / opacity))),
                        min(255, max(0, round(g * 255 / opacity))),
                        min(255, max(0, round((b - (255 - opacity)) * 255 / opacity))),
                    )
                alphas[x, y] = opacity
            if alphas[x, y] == 0:
                pixels[x, y] = (0, 0, 0)
    color.putalpha(alpha)
    return color


def prepare_underbelly(path: Path) -> Image.Image:
    """Keep only the generated inner-leg repair, at its reviewed uniform scale."""
    if hashlib.sha256(path.read_bytes()).hexdigest() != UNDERBELLY_SHA256:
        raise ValueError("underbelly input differs from the reviewed generated repair")
    color = Image.open(path).convert("RGB")
    if color.size != (1145, 1374):
        raise ValueError("unexpected underbelly repair dimensions")
    rgba = remove_magenta_backdrop(color, Image.new("L", color.size, 255))
    rgba = rgba.resize((640, 768), Image.Resampling.LANCZOS)
    aligned = Image.new("RGBA", (640, 768))
    aligned.alpha_composite(rgba, (0, 22))
    return aligned.crop(UNDERBELLY_BOX)


def save_encoded(image: Image.Image, target: Path) -> dict[str, str]:
    encoded = BytesIO()
    image.save(encoded, "PNG", optimize=True, compress_level=9)
    data = encoded.getvalue()
    target.write_text("\n".join(textwrap.wrap(base64.b64encode(data).decode("ascii"), 120)) + "\n", encoding="ascii")
    return {"decoded_png_sha256": hashlib.sha256(data).hexdigest(),
            "decoded_rgba_sha256": hashlib.sha256(image.tobytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--color", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--underbelly", type=Path, required=True)
    args = parser.parse_args()
    image = recover_sheet(args.color, args.mask)
    root = ROOT / "assets/groom/v2.1"
    target = root / "source/groom-right-approved.png.b64"
    source_hashes = save_encoded(image, target)
    underbelly = prepare_underbelly(args.underbelly)
    repair_source = "source/groom-right-underbelly.png.b64"
    repair_hashes = save_encoded(underbelly, root / repair_source)
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    manifest.update(
        side="cat-right-paw", visual_side="screen-right orange forearm raised; screen-left white forepaw grounded; no whole-cat mirroring",
        source="source/groom-right-approved.png.b64", sheet_size=list(RIGHT_SHEET_SIZE),
        delivered_color_sha256=COLOR_SHA256, delivered_alpha_sha256=MASK_SHA256,
        **source_hashes,
        alpha_recovery="supplied silhouette, color-confirmed magenta gaps and local edge unmatting; no whole-mask erosion",
        composition={
            "mode": "right-local-limb-and-mouth-v1",
            "neutral_rgba_sha256": "e02f052cb970d2ebed4946ad0f09038adbce4d41da3a730e09e56783054e5eb0",
            "source_translation": [-44, 0],
            "underbelly": {"source": repair_source, **repair_hashes,
                "generated_input_sha256": UNDERBELLY_SHA256,
                "generated_input_size": [1145, 1374],
                "uniform_resize": [640, 768], "translation": [0, 22],
                "crop": list(UNDERBELLY_BOX)},
            "description": "Actual neutral head, ears, back and hindquarters remain fixed. Generated mouth and lifted orange forelimb replace the old limb. One generated inner-leg repair fills its revealed body; never mirror or stretch the whole cat.",
        },
    )
    (root / "manifest-right.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source": str(target), "png_sha256": manifest["decoded_png_sha256"], "rgba_sha256": manifest["decoded_rgba_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

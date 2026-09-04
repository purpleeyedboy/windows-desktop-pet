"""Generate review-only ear feedback evidence outside the source tree."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.ear_interaction import deform_ear  # noqa: E402


def build_preview(output: Path) -> Path:
    source = Image.open(
        ROOT / "assets/rig/v1/source/canonical-idle.png"
    ).convert("RGBA")
    frames = (
        ("neutral", source),
        ("left pressed", deform_ear(source, "left", 1.0)),
        ("right pressed", deform_ear(source, "right", 1.0)),
    )
    sheet = Image.new(
        "RGBA",
        (source.width * len(frames), source.height),
        (38, 38, 38, 255),
    )
    draw = ImageDraw.Draw(sheet)
    for index, (label, frame) in enumerate(frames):
        x = index * source.width
        sheet.alpha_composite(frame, (x, 0))
        draw.text((x + 8, 8), label, fill=(255, 255, 255, 255))
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.resize(
        (sheet.width * 2, sheet.height * 2),
        Image.Resampling.NEAREST,
    ).save(output, optimize=False)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(build_preview(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

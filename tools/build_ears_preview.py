"""Restore every authored ear frame and generate review evidence outside Git."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.ear_interaction import EAR_KEYFRAMES, apply_ear_keyframe  # noqa: E402


def restored_frames(side: str) -> tuple[tuple[str, int, Image.Image], ...]:
    source = Image.open(ROOT / "assets/rig/v1/source/canonical-idle.png").convert("RGBA")
    return tuple(
        (frame.frame_id, frame.duration_ms, apply_ear_keyframe(source, side, index))
        for index, frame in enumerate(EAR_KEYFRAMES[side].frames)
    )


def build_preview(output: Path) -> Path:
    rows = {side: restored_frames(side) for side in ("left", "right")}
    thumb_size = (256, 384)
    sheet = Image.new("RGBA", (thumb_size[0] * 12, thumb_size[1] * 2), (38, 38, 38, 255))
    draw = ImageDraw.Draw(sheet)
    for row, side in enumerate(("left", "right")):
        for column, (frame_id, duration, frame) in enumerate(rows[side]):
            x, y = column * thumb_size[0], row * thumb_size[1]
            sheet.alpha_composite(frame.resize(thumb_size, Image.Resampling.LANCZOS), (x, y))
            draw.rectangle((x, y, x + 256, y + 30), fill=(20, 20, 20, 210))
            draw.text((x + 5, y + 5), f"{side} {frame_id} {duration}ms", fill="white")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=False)
    return output


def build_animation(output: Path) -> Path:
    source = Image.open(ROOT / "assets/rig/v1/source/canonical-idle.png").convert("RGBA")
    frames: list[Image.Image] = []
    durations: list[int] = []
    for side in ("left", "right"):
        for index, frame in enumerate(EAR_KEYFRAMES[side].frames):
            restored = apply_ear_keyframe(source, side, index)
            preview = Image.new("RGBA", restored.size, (38, 38, 38, 255))
            preview.alpha_composite(restored)
            frames.append(preview.convert("RGB"))
            durations.append(frame.duration_ms)
        frames.append(Image.new("RGB", source.size, (38, 38, 38)))
        frames[-1].paste(source, mask=source.getchannel("A"))
        durations.append(500)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Contact-sheet PNG path")
    parser.add_argument("--animation", type=Path, help="Optional continuous GIF path")
    args = parser.parse_args(argv)
    print(build_preview(args.output))
    if args.animation is not None:
        print(build_animation(args.animation))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

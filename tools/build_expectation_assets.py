"""Reconstruct real source frames and bake their local changes onto runtime neutral.

Source frames are verified against the recovered cloud manifest. No approved
image is overwritten. Generated runtime PNGs are packaged but not committed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from desktop_pet.assets import load_head_neck_compositor
from desktop_pet.drag_expression_frames import load_drag_expression_sequence
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.expectation_assets import load_expectation_frames


def build(output: Path, preview: Path | None = None):
    source = load_drag_expression_sequence(ROOT / "assets/drag-expectation/v1")
    compositor = load_head_neck_compositor()
    neutral = compositor.compose(0, 0, HeadPose(0, 0))
    assert neutral.size == (640, 768)
    original = source.frames[0].image
    offset = ((neutral.width - original.width) // 2, 0)
    output.mkdir(parents=True, exist_ok=True)
    records, frames = [], []
    for index, source_frame in enumerate(source.frames):
        delta = ImageChops.difference(source_frame.image, original)
        channels = delta.split()
        changed = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), ImageChops.lighter(channels[2], channels[3]))
        changed = changed.point(lambda value: 255 if value else 0)
        frame = neutral.copy()
        frame.paste(source_frame.image, offset, changed)
        # No body geometry is resized; only the authored changed pixels replace neutral.
        untouched = Image.new("L", frame.size, 255)
        untouched.paste(ImageChops.invert(changed), offset)
        difference = ImageChops.difference(frame, neutral)
        assert all(not ImageChops.multiply(channel, untouched).getbbox() for channel in difference.split())
        filename = f"{index:02d}.png"
        frame.save(output / filename, optimize=False, compress_level=9)
        records.append({"file": filename, "id": source_frame.frame_id,
                        "duration_ms": source_frame.duration_ms,
                        "source_png_sha256": source_frame.sha256,
                        "rgba_sha256": hashlib.sha256(frame.tobytes()).hexdigest()})
        frames.append(frame)
    assert frames[0].tobytes() == neutral.tobytes(), "neutral frame must equal real runtime neutral"
    manifest = {"schema": 1, "canvas": list(neutral.size), "source_offset": list(offset),
                "method": "baked authored delta over the unchanged runtime neutral",
                "frames": records, "enter": [0, 1, 2, 3], "hold": [3, 4], "exit": [2, 1, 0]}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    restored = load_expectation_frames(output)
    assert all(a.tobytes() == b.tobytes() for a, b in zip(frames, restored, strict=True))
    if preview is not None:
        preview.mkdir(parents=True, exist_ok=True)
        order = [0, 1, 2, 3, 4, 3, 4, 2, 1, 0]
        durations = [500, 50, 50, 100, 100, 100, 100, 50, 50, 400]
        for theme, color in (("black", (22, 24, 28)), ("white", (255, 255, 255))):
            cells = []
            for frame in frames:
                background = Image.new("RGB", frame.size, color)
                background.paste(frame, mask=frame.getchannel("A"))
                cells.append(background)
            sheet = Image.new("RGB", (320 * 5, 410), color)
            draw = ImageDraw.Draw(sheet)
            for index, cell in enumerate(cells):
                sheet.paste(cell.resize((320, 384)), (index * 320, 0))
                draw.text((index * 320 + 8, 389), source.frames[index].frame_id,
                          fill="white" if theme == "black" else "black")
            sheet.save(preview / f"contact-{theme}.png")
            playback = [cells[i] for i in order]
            playback[0].save(preview / f"preview-{theme}.png", save_all=True, append_images=playback[1:], duration=durations, loop=0)
            gif = [frame.resize((320, 384)) for frame in playback]
            gif[0].save(preview / f"preview-{theme}.gif", save_all=True, append_images=gif[1:], duration=durations, loop=0)
        (preview / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("PASS: five source-verified frames; exact neutral; 640x768 canvas; untouched body; runtime decode")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "assets/expectation/runtime")
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    build(args.output, args.preview)

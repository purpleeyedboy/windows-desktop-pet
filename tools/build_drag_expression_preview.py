"""Decode the committed frame pack into temporary review evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from desktop_pet.drag_expression_frames import load_drag_expression_sequence


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    sequence = load_drag_expression_sequence()
    thumb_size = (256, 384)
    sheet = Image.new("RGBA", (thumb_size[0] * len(sequence.frames), 420), "white")
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(sequence.frames):
        thumb = frame.image.resize(thumb_size, Image.Resampling.LANCZOS)
        sheet.alpha_composite(thumb, (index * thumb_size[0], 0))
        draw.text((index * thumb_size[0] + 8, 390), f"{frame.frame_id} {frame.duration_ms}ms", fill="black")
    sheet.convert("RGB").save(output / "contact-sheet.png")
    order = [0, 1, 2, 3, 4, 3, 4, 2, 1, 0]
    images = [sequence.frames[i].image.convert("P", palette=Image.Palette.ADAPTIVE) for i in order]
    durations = [50, 50, 50, 100, 100, 100, 100, 50, 50, 50]
    images[0].save(output / "continuous-preview.gif", save_all=True, append_images=images[1:], duration=durations, loop=0, disposal=2, transparency=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    build(parser.parse_args().output_dir)

"""Generate PAWS visual evidence at an explicit disposable output path."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from desktop_pet.assets import load_paw_compositor, neutral_eye_source_probe_root


def generate_preview(output: Path) -> None:
    source_path = neutral_eye_source_probe_root() / "body-backplate.png"
    with Image.open(source_path) as opened:
        source = opened.convert("RGBA")
        source.load()
    compositor = load_paw_compositor()
    frames = (
        source,
        compositor.compose(source, left_offset=(0, 2), right_offset=(0, 2)),
        compositor.compose(source, left_offset=(0, 5), right_offset=(0, 5)),
        source,
    )
    preview = Image.new("RGBA", (source.width * len(frames), source.height))
    for index, frame in enumerate(frames):
        preview.alpha_composite(frame, (index * source.width, 0))
    output.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    generate_preview(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

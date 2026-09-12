"""Generate PAWS visual evidence at an explicit disposable output path."""

from __future__ import annotations

import argparse
from pathlib import Path
import hashlib
import json

from PIL import Image

from desktop_pet.assets import load_head_neck_compositor, load_paw_compositor
from desktop_pet.head_neck_deformation import HeadPose


def generate_preview(output: Path) -> None:
    source = load_head_neck_compositor().compose(
        0.0, 0.0, HeadPose(0.0, 0.0)
    ).convert("RGBA")
    compositor = load_paw_compositor()
    scale = 0.5
    thumb_size = (round(source.width * scale), round(source.height * scale))
    frames = [
        compositor.compose_frame(source, side, index)
        for side in ("left", "right") for index in range(15)
    ]
    columns = 5
    rows = (len(frames) + columns - 1) // columns
    preview = Image.new("RGBA", (thumb_size[0] * columns, thumb_size[1] * rows))
    for index, frame in enumerate(frames):
        preview.alpha_composite(
            frame.resize(thumb_size, Image.Resampling.LANCZOS),
            ((index % columns) * thumb_size[0], (index // columns) * thumb_size[1]),
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output)
    paired = [
        Image.new("RGBA", (source.width * 2, source.height))
        for _index in range(15)
    ]
    for index, canvas in enumerate(paired):
        canvas.alpha_composite(compositor.compose_frame(source, "left", index))
        canvas.alpha_composite(
            compositor.compose_frame(source, "right", index), (source.width, 0)
        )
    durations = [40, 40, 40, 80, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 600]
    paired[0].save(
        output.with_name(output.stem + "-continuous.gif"),
        save_all=True,
        append_images=paired[1:],
        duration=durations,
        loop=0,
        disposal=2,
    )
    report = {"canvas": list(source.size), "display_height": 280,
              "timeline_durations_ms": durations, "default_sha256": hashlib.sha256(source.tobytes()).hexdigest(),
              "sides": {}}
    for side in ("left", "right"):
        report["sides"][side] = [hashlib.sha256(compositor.compose_frame(source, side, index).tobytes()).hexdigest()
                                   for index in range(15)]
    for label, color in (("black", (0, 0, 0, 255)), ("white", (255, 255, 255, 255))):
        opaque = []
        for frame in paired:
            background = Image.new("RGBA", frame.size, color)
            background.alpha_composite(frame)
            opaque.append(background.resize((round(source.width * 2 * 280 / source.height), 280), Image.Resampling.LANCZOS))
        opaque[0].save(output.with_name(f"preview-{label}.png"), save_all=True,
                       append_images=opaque[1:], duration=durations, loop=0,
                       disposal=0, blend=0)
        opaque[0].save(output.with_name(f"preview-{label}.gif"), save_all=True,
                       append_images=opaque[1:], duration=durations, loop=0, disposal=2)
    output.with_name("verification.json").write_text(json.dumps(report, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    generate_preview(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

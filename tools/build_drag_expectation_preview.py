"""Generate deterministic V2.1-DRAG visual QA evidence outside the source tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EYE_ASSETS = ROOT / "assets/rig/v1/source/eye-neutral-v1"

if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.drag_expectation import DragVisualConfig, decorate_drag_expectation
from desktop_pet.neutral_eye_compositor import NeutralEyeCompositor


def build_preview(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    compositor = NeutralEyeCompositor.load(EYE_ASSETS)
    base = compositor.compose(0.0, 0.0)
    boxes = tuple(compositor.eye_interaction_boxes)
    head_box = (
        max(0, min(box[0] for box in boxes) - 28),
        max(0, min(box[1] for box in boxes) - 90),
        min(base.width, max(box[2] for box in boxes) + 28),
        min(base.height, max(box[3] for box in boxes) + 40),
    )
    decorated = decorate_drag_expectation(base, 1, DragVisualConfig(eye_boxes=boxes, head_box=head_box))
    canvas = Image.new("RGBA", (base.width * 2, base.height), (32, 36, 44, 255))
    canvas.alpha_composite(base, (0, 0))
    canvas.alpha_composite(decorated, (base.width, 0))
    preview = output_dir / "before-after.png"
    canvas.save(preview, format="PNG", optimize=False, compress_level=9)
    stats = output_dir / "stats.json"
    stats.write_text(
        json.dumps(
            {
                "preview": preview.name,
                "sha256": hashlib.sha256(preview.read_bytes()).hexdigest(),
                "size": list(canvas.size),
                "mode": canvas.mode,
                "phase": 1,
                "visual_acceptance": "pending",
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    return preview, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    preview, stats = build_preview(args.output_dir)
    print(f"preview: {preview}")
    print(f"stats: {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

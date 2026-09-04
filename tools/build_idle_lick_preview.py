"""Generate deterministic V2.1-LICK QA evidence in a caller-owned directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:  # Direct checkout CLI use.
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from desktop_pet.idle_lick import LickPose
from desktop_pet.lick_compositor import compose_lick


def build_preview(source_path: Path, output_dir: Path) -> dict[str, object]:
    source_path = Path(source_path).resolve()
    output_dir = Path(output_dir).resolve()
    if not source_path.is_file():
        raise ValueError("preview source must be an existing file")
    if output_dir == source_path.parent or source_path.is_relative_to(output_dir):
        raise ValueError("preview output must be separate from source assets")
    source = Image.open(source_path).convert("RGBA")
    poses = tuple(
        LickPose(side, phase, arm, tongue)
        for side in ("left", "right")
        for phase, arm, tongue in (
            ("raise", 0.5, 0.0),
            ("raise", 1.0, 0.0),
            ("lick", 1.0, 0.5),
            ("contact", 1.0, 1.0),
            ("lower", 0.5, 0.0),
        )
    )
    frames = tuple(compose_lick(source, pose) for pose in poses)
    sheet = Image.new("RGBA", (source.width * 5, source.height * 2), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.paste(frame, ((index % 5) * source.width, (index // 5) * source.height))
    output_dir.mkdir(parents=True, exist_ok=False)
    sheet_path = output_dir / "idle-lick-contact-sheet.png"
    sheet.save(sheet_path)
    report: dict[str, object] = {
        "frames": len(frames),
        "sides": ["left", "right"],
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "sheet_sha256": hashlib.sha256(sheet_path.read_bytes()).hexdigest(),
    }
    (output_dir / "idle-lick-preview.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build_preview(args.source, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

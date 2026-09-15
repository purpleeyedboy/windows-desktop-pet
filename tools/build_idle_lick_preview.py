"""Generate grooming QA only from a reviewed local-layer asset pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from desktop_pet.idle_lick import LickPose
from desktop_pet.lick_compositor import compose_lick, load_groom_assets


def build_preview(asset_root: Path, output_dir: Path) -> dict[str, object]:
    assets = load_groom_assets(asset_root)
    source_path = Path(asset_root) / "canonical.png"
    if not source_path.is_file():
        raise ValueError("reviewed grooming pack is missing canonical.png")
    source = Image.open(source_path).convert("RGBA")
    poses = tuple(
        LickPose(side, phase, arm, tongue)
        for side in ("left", "right")
        for phase, arm, tongue in (
            ("raise", 0.5, 0.0), ("raise", 1.0, 0.0),
            ("upstroke", 1.0, 1.0), ("downstroke", 1.0, 1.0),
            ("lower", 0.5, 0.0),
        )
    )
    frames = tuple(compose_lick(source, pose, assets, lambda point: point) for pose in poses)
    sheet = Image.new("RGBA", (source.width * 5, source.height * 2))
    for index, frame in enumerate(frames):
        sheet.paste(frame, ((index % 5) * source.width, (index // 5) * source.height))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    sheet_path = output_dir / "groom-contact-sheet.png"
    sheet.save(sheet_path)
    report = {
        "frames": 10,
        "asset_manifest_sha256": hashlib.sha256(
            (Path(asset_root) / "manifest.json").read_bytes()
        ).hexdigest(),
        "sheet_sha256": hashlib.sha256(sheet_path.read_bytes()).hexdigest(),
    }
    (output_dir / "groom-preview.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build_preview(args.asset_root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

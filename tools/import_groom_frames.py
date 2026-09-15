"""CLI wrapper for the packaged deterministic grooming importer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desktop_pet.groom_import import (ART_SIZE, RUNTIME_OFFSET, RUNTIME_SIZE, build_alpha, combine_delivered_sheets, import_groom_frames, primary_subject_box)

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("assets/groom/v2.1/manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frames = import_groom_frames(args.manifest, args.output)
    from desktop_pet.assets import load_head_neck_compositor
    from desktop_pet.head_neck_deformation import HeadPose
    neutral = load_head_neck_compositor().compose(0.0, 0.0, HeadPose(0.0, 0.0))
    if any(frame.size != neutral.size for frame in frames):
        raise ValueError("Groom canvas differs from the actual head-follow canvas")
    if frames[0].tobytes() != neutral.tobytes():
        raise ValueError("Groom endpoint differs from the actual neutral head-follow image")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

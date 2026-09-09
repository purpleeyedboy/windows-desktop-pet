"""Check real hunger frame loading, canonical restoration and archive inputs."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.assets import load_head_neck_compositor
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.hunger_graphic_assets import load_hunger_graphic_assets
from desktop_pet.main import main as application_entrypoint


def main() -> int:
    neutral = load_head_neck_compositor().compose(0.0, 0.0, HeadPose(0.0, 0.0))
    artwork = load_hunger_graphic_assets(neutral)
    assert len(artwork.clips) == 2
    for name, (frames, sequence) in artwork.clips.items():
        assert sum(step.duration_ms for step in sequence.steps) == 1700, name
        assert frames[0].tobytes() == neutral.tobytes(), name
        assert frames[-1].tobytes() == neutral.tobytes(), name
        assert frames[1].tobytes() != neutral.tobytes(), name
    assert len(artwork.critical_frames) == 2
    assert artwork.critical_frames[0].tobytes() != artwork.critical_frames[1].tobytes()
    assert artwork.critical_durations == (240, 240)
    files = list((ROOT / "assets/hunger/v1").rglob("*.png"))
    assert len(files) == 5, "runtime artwork must deduplicate repeated hold poses"
    print("hunger graphic source hashes, live canvas, canonical restore and five-file package checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

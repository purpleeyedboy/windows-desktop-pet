from pathlib import Path
from typing import Sequence

from PIL import Image

from .model import ACTIONS
from .paths import asset_path


EXPECTED_SIZE = (512, 768)


def find_frame_paths(root: Path, action: str) -> list[Path]:
    paths = sorted((root / action).glob("*.png"))
    expected = [f"{index:02d}.png" for index in range(6)]
    if [path.name for path in paths] != expected:
        raise RuntimeError(
            f"{action} must contain exactly 6 frames named 00.png through 05.png"
        )
    return paths


def validate_frame_file(path: Path) -> None:
    with Image.open(path) as image:
        if image.mode != "RGBA" or image.size != EXPECTED_SIZE:
            raise RuntimeError(f"{path.name} must be 512x768 RGBA")
        minimum, maximum = image.getchannel("A").getextrema()
        if minimum != 0 or maximum != 255:
            raise RuntimeError(
                f"{path.name} must contain transparent background and opaque subject pixels"
            )


def load_frames(root: Path | None = None) -> dict[str, Sequence[Image.Image]]:
    frame_root = root or asset_path("assets", "pet")
    loaded: dict[str, Sequence[Image.Image]] = {}
    for action in ACTIONS:
        frames: list[Image.Image] = []
        for path in find_frame_paths(frame_root, action):
            validate_frame_file(path)
            with Image.open(path) as image:
                frames.append(image.copy())
        loaded[action] = tuple(frames)
    return loaded

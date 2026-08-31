from pathlib import Path
import sys
from typing import Sequence

from PIL import Image

from .head_neck_deformation import ContinuousHeadNeckCompositor
from .model import ACTIONS
from .neutral_eye_compositor import NeutralEyeCompositor
from .paths import asset_path


EXPECTED_SIZE = (512, 768)
FRAME_COUNT = 6
EXPECTED_NAMES = tuple(f"{index:02d}.png" for index in range(FRAME_COUNT))


def runtime_frame_root() -> Path:
    return asset_path("assets", "keyframes")


def neutral_eye_source_probe_root() -> Path:
    """Return the source-checkout-only neutral-eye authoring directory."""
    return (
        Path(__file__).resolve().parents[2]
        / "assets"
        / "rig"
        / "v1"
        / "source"
        / "eye-neutral-v1"
    )


def neutral_eye_runtime_root() -> Path:
    """Return the bundled neutral-eye runtime directory."""
    return asset_path("assets", "rig", "v1", "runtime", "eye-neutral-v1")


def load_neutral_eye_compositor(
    root: Path | None = None,
) -> NeutralEyeCompositor:
    """Load the neutral-eye compositor from an explicit, runtime, or source root."""
    if root is not None:
        return NeutralEyeCompositor.load(root)

    runtime_root = neutral_eye_runtime_root()
    if getattr(sys, "_MEIPASS", None) or runtime_root.exists():
        return NeutralEyeCompositor.load(runtime_root)
    return NeutralEyeCompositor.load(neutral_eye_source_probe_root())


def load_head_neck_compositor() -> ContinuousHeadNeckCompositor:
    """Wrap the selected neutral-eye compositor with head deformation."""
    return ContinuousHeadNeckCompositor(load_neutral_eye_compositor())


def load_neutral_eye_source_probe(
    root: Path | None = None,
) -> NeutralEyeCompositor:
    """Load the validated source-checkout-only eye-follow probe.

    This deliberately does not use the bundled asset resolver and therefore
    makes no packaging or frozen-application resource guarantee.
    """
    return NeutralEyeCompositor.load(root or neutral_eye_source_probe_root())


def find_frame_paths(root: Path, action: str) -> list[Path]:
    paths = sorted((root / action).glob("*.png"))
    if tuple(path.name for path in paths) != EXPECTED_NAMES:
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
    frame_root = root or runtime_frame_root()
    loaded: dict[str, Sequence[Image.Image]] = {}
    for action in ACTIONS:
        frames: list[Image.Image] = []
        for path in find_frame_paths(frame_root, action):
            validate_frame_file(path)
            with Image.open(path) as image:
                frames.append(image.copy())
        loaded[action] = tuple(frames)
    return loaded

"""V2.1-EARS local feature adapter; shared coordination is supplied by PR5."""
from __future__ import annotations

from dataclasses import dataclass, replace
import base64
from io import BytesIO
import json
import math
from pathlib import Path
import zlib
from typing import Literal, Protocol
from PIL import Image, ImageChops, ImageDraw

from .paths import asset_path

EarSide = Literal["left", "right"]  # The cat's own left/right, not screen-left/right.

@dataclass(frozen=True)
class EarAsset:
    polygon: tuple[tuple[float, float], ...]
    root: tuple[float, float]
    outward_sign: float

@dataclass(frozen=True)
class EarRasterPose:
    frame_index: int | None = None


@dataclass(frozen=True)
class EarActionContext:
    """Compatibility context for dependency-injected windows without PR5 services."""

    action_id: str
    state_version: int
    cancel_token: object


@dataclass(frozen=True)
class EarMotionConfig:
    total_seconds: float = 1.0
    shake_seconds: float = 0.18
    throw_seconds: float = 0.12
    recovery_seconds: float = 0.25
    maximum_throw_degrees: float = 11.0
    shake_degrees: float = 2.8
    rebound_ratio: float = 0.05
    cooldown_seconds: float = 0.0
    frame_ms: int = 16

EAR_MOTION = EarMotionConfig()
_ASSET_FILE = Path(__file__).with_name("ear_asset_manifest.json")
_KEYFRAME_FILE = "ear_keyframes.json"


@dataclass(frozen=True)
class EarRasterFrame:
    frame_id: str
    duration_ms: int
    angle_degrees: float
    image: Image.Image
    change_mask: Image.Image


@dataclass(frozen=True)
class EarRasterSequence:
    roi: tuple[int, int, int, int]
    frames: tuple[EarRasterFrame, ...]


def load_ear_keyframes(path: Path | None = None) -> dict[EarSide, EarRasterSequence]:
    resource = path or asset_path("desktop_pet", _KEYFRAME_FILE)
    if not resource.is_file():
        resource = Path(__file__).with_name(_KEYFRAME_FILE)
    data = json.loads(resource.read_text(encoding="utf-8"))
    if data.get("sequence_total_ms") != 550 or data.get("canvas") != [512, 768]:
        raise ValueError("invalid V2.1-EARS raster sequence contract")
    sequences: dict[EarSide, EarRasterSequence] = {}
    for side in ("left", "right"):
        item = data["sides"][side]
        frames = []
        for encoded in item["frames"]:
            png = zlib.decompress(base64.b85decode("".join(encoded["png_zlib_base85"])))
            with Image.open(BytesIO(png)) as opened:
                image = opened.convert("RGBA")
                image.load()
            mask_png = zlib.decompress(base64.b85decode("".join(encoded["mask_png_zlib_base85"])))
            with Image.open(BytesIO(mask_png)) as opened:
                change_mask = opened.convert("L")
                change_mask.load()
            frames.append(EarRasterFrame(
                str(encoded["id"]),
                int(encoded["duration_ms"]),
                float(encoded["angle_degrees"]),
                image,
                change_mask,
            ))
        sequence = EarRasterSequence(tuple(int(v) for v in item["roi"]), tuple(frames))
        if sum(frame.duration_ms for frame in sequence.frames) != 550:
            raise ValueError(f"invalid {side} ear frame durations")
        if sequence.frames[-1].frame_id != "neutral-end":
            raise ValueError(f"{side} ear sequence must end at neutral")
        sequences[side] = sequence
    return sequences


# Reuse the lossless source poses, but retire the three-shake choreography.
# Fast recoil (160 ms to peak), then a single slower return. The source JSON
# remains intact for provenance; these are the authoritative runtime timings.
_TOUCH_TIMELINE = (
    ("neutral-start", 20), ("shake-1-out", 60),
    ("throw-approach", 80), ("throw-maximum", 120),
    ("throw-approach", 150), ("recover-ease", 200),
    ("shake-1-out", 200), ("neutral-end", 170),
)


def touch_recoil_sequence(source: EarRasterSequence) -> EarRasterSequence:
    poses = {frame.frame_id: frame for frame in source.frames}
    return EarRasterSequence(source.roi, tuple(
        replace(poses[frame_id], duration_ms=duration)
        for frame_id, duration in _TOUCH_TIMELINE
    ))


EAR_KEYFRAMES = {side: touch_recoil_sequence(sequence)
                 for side, sequence in load_ear_keyframes().items()}


def apply_ear_keyframe(source: Image.Image, side: EarSide, frame_index: int) -> Image.Image:
    """Composite one authored lossless RGBA crop before existing head deformation."""
    sequence = EAR_KEYFRAMES[side]
    if not 0 <= frame_index < len(sequence.frames):
        raise IndexError("ear frame index is outside the authored sequence")
    frame = sequence.frames[frame_index]
    output = source.convert("RGBA").copy()
    if frame.frame_id in {"neutral-start", "neutral-end"}:
        return output
    output.paste(frame.image, sequence.roi[:2], frame.change_mask)
    return output

def load_ear_assets(path: Path = _ASSET_FILE) -> dict[EarSide, EarAsset]:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for side in ("left", "right"):
        item = data["ears"][side]
        result[side] = EarAsset(
            tuple(tuple(float(v) for v in point) for point in item["mask_polygon"]),
            tuple(float(v) for v in item["root"]),
            float(item["outward_sign"]),
        )
    return result

EAR_ASSETS = load_ear_assets()

class HeadPointMapper(Protocol):
    def __call__(self, point: tuple[float, float]) -> tuple[float, float]: ...

class EarHitMasks:
    def __init__(self, masks: dict[EarSide, Image.Image]) -> None:
        self._masks = masks
        self.source_size = next(iter(masks.values())).size

    @classmethod
    def from_frame(cls, frame: Image.Image, map_head_point: HeadPointMapper | None = None) -> "EarHitMasks":
        mapper = map_head_point or (lambda point: point)
        alpha = frame.convert("RGBA").getchannel("A")
        masks = {}
        for side, asset in EAR_ASSETS.items():
            region = Image.new("L", frame.size, 0)
            ImageDraw.Draw(region).polygon(tuple(mapper(point) for point in asset.polygon), fill=255)
            masks[side] = ImageChops.multiply(alpha, region).point(lambda value: 255 if value else 0)
        return cls(masks)

    def mask(self, side: EarSide) -> Image.Image:
        return self._masks[side]

    def hit_source(self, point: tuple[float, float]) -> EarSide | None:
        x, y = math.floor(point[0]), math.floor(point[1])
        if not (0 <= x < self.source_size[0] and 0 <= y < self.source_size[1]):
            return None
        return next((side for side in ("left", "right") if self._masks[side].getpixel((x, y))), None)

    def hit_display(self, point: tuple[float, float], display_size: tuple[int, int]) -> EarSide | None:
        width, height = display_size
        if width <= 0 or height <= 0:
            return None
        return self.hit_source((point[0] * self.source_size[0] / width, point[1] * self.source_size[1] / height))

class EarFeatureAdapter:
    """Local ear renderer. PR5's ActivityCoordinator owns approval and tokens."""
    def __init__(self, schedule, cancel, clock, display, complete) -> None:
        self._schedule, self._cancel, self._clock = schedule, cancel, clock
        self._display, self._complete = display, complete
        self._active: tuple[EarSide, object, float] | None = None
        self._timer = None
        self._frame_index = 0

    @property
    def active(self) -> bool:
        return self._active is not None

    def start_approved(self, side: EarSide, context: object) -> bool:
        if self._active is not None:
            return False
        self._active = (side, context, self._clock())
        self._frame_index = 0
        self._show_current_frame()
        return True

    def _show_current_frame(self) -> None:
        active = self._active
        if active is None:
            return
        side, _context, _started = active
        sequence = EAR_KEYFRAMES[side]
        self._display(side, EarRasterPose(self._frame_index))
        self._timer = self._schedule(
            sequence.frames[self._frame_index].duration_ms,
            lambda: self._advance_frame(active),
        )

    def _advance_frame(self, expected_active: object) -> None:
        active = self._active
        if active is None or active is not expected_active:
            return
        side, context, _started = active
        self._frame_index += 1
        if self._frame_index >= len(EAR_KEYFRAMES[side].frames):
            self._active = None
            self._timer = None
            self._complete(context, True)
            return
        self._show_current_frame()

    def cancel_active(self) -> bool:
        if self._active is None:
            return False
        if self._timer is not None:
            self._cancel(self._timer)
        side = self._active[0]
        self._active = None
        self._timer = None
        self._frame_index = 0
        self._display(side, EarRasterPose())
        return True

    def cancel_and_recover(self, context: object) -> bool:
        """Compatibility path for callers without the shared coordinator."""
        if self._active is None or self._active[1] != context:
            return False
        if not self.cancel_active():
            return False
        self._complete(context, True)
        return True

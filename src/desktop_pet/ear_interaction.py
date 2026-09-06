"""V2.1-EARS local feature adapter; shared coordination is supplied by PR5."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Callable, Literal, Protocol
from PIL import Image, ImageChops, ImageDraw

EarSide = Literal["left", "right"]  # The cat's own left/right, not screen-left/right.

@dataclass(frozen=True)
class EarAsset:
    polygon: tuple[tuple[float, float], ...]
    root: tuple[float, float]
    outward_sign: float

@dataclass(frozen=True)
class EarPose:
    angle_degrees: float = 0.0

@dataclass(frozen=True)
class EarActionContext:
    action_id: str
    state_version: int
    cancel_token: object

@dataclass(frozen=True)
class EarMotionConfig:
    total_seconds: float = 0.55
    shake_seconds: float = 0.18
    throw_seconds: float = 0.12
    recovery_seconds: float = 0.25
    maximum_throw_degrees: float = 11.0
    shake_degrees: float = 2.8
    rebound_ratio: float = 0.05
    cooldown_seconds: float = 0.5
    frame_ms: int = 16

EAR_MOTION = EarMotionConfig()
_ASSET_FILE = Path(__file__).with_name("ear_asset_manifest.json")

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

def render_ear_pose(frame: Image.Image, side: EarSide, pose: EarPose, *, map_head_point: HeadPointMapper | None = None) -> Image.Image:
    if pose.angle_degrees == 0.0:
        return frame
    rgba = frame.convert("RGBA")
    mapper = map_head_point or (lambda point: point)
    masks = EarHitMasks.from_frame(rgba, mapper)
    mask = masks.mask(side)
    layer = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    layer.paste(rgba, mask=mask)
    root = mapper(EAR_ASSETS[side].root)
    bbox = mask.getbbox()
    if bbox is None:
        return rgba

    def inverse(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        root_blend = min(1.0, max(0.0, (root[1] - 8.0 - y) / 42.0))
        angle = math.radians(-pose.angle_degrees * _minimum_jerk(root_blend))
        dx, dy = x - root[0], y - root[1]
        cosine, sine = math.cos(angle), math.sin(angle)
        return root[0] + cosine * dx - sine * dy, root[1] + sine * dx + cosine * dy

    left, top, right, bottom = bbox
    mesh = []
    step = 12
    for y0 in range(max(0, top - step), min(rgba.height, bottom + step), step):
        y1 = min(rgba.height, y0 + step)
        for x0 in range(max(0, left - step), min(rgba.width, right + step), step):
            x1 = min(rgba.width, x0 + step)
            points = (
                inverse((x0, y0)),
                inverse((x0, y1)),
                inverse((x1, y1)),
                inverse((x1, y0)),
            )
            mesh.append(
                (
                    (x0, y0, x1, y1),
                    tuple(value for point in points for value in point),
                )
            )
    rotated = layer.transform(rgba.size, Image.Transform.MESH, mesh, Image.Resampling.BICUBIC)
    moved_mask = mask.transform(rgba.size, Image.Transform.MESH, mesh, Image.Resampling.BICUBIC)
    output = rgba.copy()
    hole_fill = rgba.transform(
        rgba.size,
        Image.Transform.AFFINE,
        (1.0, 0.0, 0.0, 0.0, 1.0, 18.0),
        Image.Resampling.BICUBIC,
    )
    output.paste(Image.new("RGBA", rgba.size, (0, 0, 0, 0)), mask=mask)
    root_support = Image.new("L", rgba.size, 0)
    ImageDraw.Draw(root_support).rectangle(
        (left, round(root[1] - 38.0), right, bottom), fill=255
    )
    root_support = ImageChops.multiply(mask, root_support)
    output.paste(hole_fill, mask=root_support)
    output.paste(rotated, mask=moved_mask)
    return output

def _minimum_jerk(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value ** 3 * (10.0 + value * (-15.0 + 6.0 * value))

def sample_ear_pose(side: EarSide, elapsed: float, config: EarMotionConfig = EAR_MOTION) -> EarPose:
    sign = EAR_ASSETS[side].outward_sign
    t = min(config.total_seconds, max(0.0, elapsed))
    if t < config.shake_seconds:
        phase = t / config.shake_seconds
        return EarPose(sign * config.shake_degrees * math.sin(phase * math.tau * 3.0) * math.sin(math.pi * phase))
    t -= config.shake_seconds
    if t < config.throw_seconds:
        return EarPose(sign * config.maximum_throw_degrees * _minimum_jerk(t / config.throw_seconds))
    t -= config.throw_seconds
    phase = min(1.0, t / config.recovery_seconds)
    if phase <= 0.8:
        angle = sign * config.maximum_throw_degrees * (
            1.0 - _minimum_jerk(phase / 0.8)
        )
    else:
        rebound_phase = (phase - 0.8) / 0.2
        angle = -sign * config.maximum_throw_degrees * config.rebound_ratio * math.sin(
            math.pi * rebound_phase
        )
    return EarPose(0.0 if elapsed >= config.total_seconds else angle)

class EarFeatureAdapter:
    """Local ear renderer. PR5's ActivityCoordinator owns approval and tokens."""
    def __init__(self, schedule, cancel, clock, display, complete) -> None:
        self._schedule, self._cancel, self._clock = schedule, cancel, clock
        self._display, self._complete = display, complete
        self._active: tuple[EarSide, EarActionContext, float] | None = None
        self._timer = None
        self._cooldown_until = 0.0

    @property
    def active(self) -> bool:
        return self._active is not None

    def start_approved(self, side: EarSide, context: EarActionContext) -> bool:
        if self._active is not None or self._clock() < self._cooldown_until:
            return False
        self._active = (side, context, self._clock())
        self._tick()
        return True

    def _tick(self) -> None:
        active = self._active
        if active is None:
            return
        side, context, started = active
        elapsed = self._clock() - started
        self._display(side, sample_ear_pose(side, elapsed))
        if elapsed >= EAR_MOTION.total_seconds:
            self._active = None
            self._timer = None
            self._cooldown_until = self._clock() + EAR_MOTION.cooldown_seconds
            self._complete(context, True)
            return
        self._timer = self._schedule(EAR_MOTION.frame_ms, self._tick)

    def cancel_and_recover(self, context: EarActionContext) -> bool:
        if self._active is None or self._active[1] != context:
            return False
        if self._timer is not None:
            self._cancel(self._timer)
        side = self._active[0]
        self._active = None
        self._timer = None
        self._display(side, EarPose())
        self._complete(context, True)
        return True

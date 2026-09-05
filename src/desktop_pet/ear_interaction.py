"""Pixel-precise, reversible feedback for the two ears."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Literal

from PIL import Image, ImageChops, ImageDraw


EarSide = Literal["left", "right"]
_EAR_POLYGONS = {
    "left": ((28, 211), (43, 218), (94, 286), (89, 333), (43, 324)),
    "right": ((166, 290), (198, 218), (227, 207), (245, 252), (235, 326)),
}


@dataclass(frozen=True)
class EarFeedbackConfig:
    """Conservative values pending visual acceptance on the Windows build."""

    press_amount: float = 0.55
    hold_amount: float = 0.72
    press_to_hold_ms: int = 90
    release_mid_ms: int = 45
    release_end_ms: int = 120
    maximum_tip_displacement_px: float = 5.0


EAR_FEEDBACK = EarFeedbackConfig()


class EarHitMasks:
    def __init__(self, masks: dict[EarSide, Image.Image]) -> None:
        self._masks = masks
        self.source_size = next(iter(masks.values())).size

    @classmethod
    def from_frame(cls, frame: Image.Image) -> "EarHitMasks":
        alpha = frame.convert("RGBA").getchannel("A")
        masks: dict[EarSide, Image.Image] = {}
        for side, polygon in _EAR_POLYGONS.items():
            region = Image.new("L", frame.size, 0)
            ImageDraw.Draw(region).polygon(polygon, fill=255)
            masks[side] = ImageChops.multiply(alpha, region).point(
                lambda value: 255 if value else 0
            )
        return cls(masks)

    def mask(self, side: EarSide) -> Image.Image:
        return self._masks[side]

    def hit_source(self, point: tuple[float, float]) -> EarSide | None:
        x, y = math.floor(point[0]), math.floor(point[1])
        width, height = self.source_size
        if x < 0 or y < 0 or x >= width or y >= height:
            return None
        for side in ("left", "right"):
            if self._masks[side].getpixel((x, y)):
                return side
        return None

    def hit_display(
        self,
        point: tuple[float, float],
        display_size: tuple[int, int],
    ) -> EarSide | None:
        width, height = display_size
        if width <= 0 or height <= 0:
            return None
        return self.hit_source(
            (
                point[0] * self.source_size[0] / width,
                point[1] * self.source_size[1] / height,
            )
        )


def deform_ear(
    frame: Image.Image,
    side: EarSide,
    amount: float,
    *,
    masks: EarHitMasks | None = None,
) -> Image.Image:
    amount = min(1.0, max(0.0, float(amount)))
    if amount == 0.0:
        return frame
    rgba = frame.convert("RGBA")
    masks = masks or EarHitMasks.from_frame(rgba)
    mask = masks.mask(side)
    bbox = mask.getbbox()
    if bbox is None:
        return rgba
    left, top, right, bottom = bbox
    displacement = round(EAR_FEEDBACK.maximum_tip_displacement_px * amount)
    if displacement <= 0 or bottom - top <= displacement:
        return rgba
    crop = rgba.crop(bbox)
    crop_mask = mask.crop(bbox)
    compressed = crop.resize(
        (crop.width, crop.height - displacement), Image.Resampling.BICUBIC
    )
    compressed_mask = crop_mask.resize(
        compressed.size, Image.Resampling.NEAREST
    )
    output = rgba.copy()
    transparent = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    output.paste(transparent, (left, top), crop_mask)
    output.paste(compressed, (left, top + displacement), compressed_mask)
    return output


class EarMotionController:
    def __init__(
        self,
        schedule: Callable[[int, Callable[[], None]], object],
        cancel: Callable[[object], None],
        display: Callable[[tuple[EarSide, float]], None],
    ) -> None:
        self._schedule = schedule
        self._cancel = cancel
        self._display = display
        self._tokens: list[object] = []
        self._generation = 0
        self.active_side: EarSide | None = None

    def _clear_callbacks(self) -> None:
        self._generation += 1
        for token in self._tokens:
            self._cancel(token)
        self._tokens.clear()

    def _later(self, delay: int, side: EarSide, amount: float) -> None:
        generation = self._generation

        def apply() -> None:
            if generation != self._generation:
                return
            self._display((side, amount))
            if amount == 0.0:
                self.active_side = None

        self._tokens.append(self._schedule(delay, apply))

    def press(self, side: EarSide) -> None:
        if self.active_side is not None:
            self.reset()
        self._clear_callbacks()
        self.active_side = side
        self._display((side, EAR_FEEDBACK.press_amount))
        self._later(EAR_FEEDBACK.press_to_hold_ms, side, EAR_FEEDBACK.hold_amount)

    def release(self, side: EarSide) -> None:
        if self.active_side != side:
            return
        self._clear_callbacks()
        self._later(EAR_FEEDBACK.release_mid_ms, side, EAR_FEEDBACK.press_amount * 0.45)
        self._later(EAR_FEEDBACK.release_end_ms, side, 0.0)

    def reset(self) -> None:
        side = self.active_side
        self._clear_callbacks()
        self.active_side = None
        if side is not None:
            self._display((side, 0.0))

    pointer_left = reset
    focus_lost = reset
    interrupt = reset
    stop = reset

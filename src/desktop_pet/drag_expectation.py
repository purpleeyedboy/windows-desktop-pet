"""Non-destructive drag-expectation state and transient visual composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageDraw, ImageEnhance


DROPEFFECT_NONE = 0
DROPEFFECT_COPY = 1


@dataclass(frozen=True)
class DragVisualConfig:
    """Candidate values are centralized until real-desktop visual acceptance."""

    # V2.1 does not prescribe these values: all remain pending visual acceptance.
    tick_ms: int = 45
    eye_scale: float = 1.16
    tremble_pixels: int = 1
    highlight_opacity: int = 44
    particle_radius: int = 3
    eye_boxes: tuple[tuple[int, int, int, int], ...] = ()
    head_box: tuple[int, int, int, int] | None = None


class DragExpectationController:
    """Idempotent closed loop for enter/over/leave/drop/cancellation."""

    def __init__(
        self,
        *,
        schedule: Callable[[int, Callable[[], None]], object],
        cancel: Callable[[object], None],
        show_phase: Callable[[int], None],
        restore: Callable[[], None],
        config: DragVisualConfig | None = None,
    ) -> None:
        self._schedule = schedule
        self._cancel = cancel
        self._show_phase = show_phase
        self._restore = restore
        self.config = config or DragVisualConfig()
        self.active = False
        self._phase = 0
        self._token: object | None = None
        self._generation = 0

    @property
    def phase(self) -> int:
        return self._phase

    def drag_enter(self, is_file: bool, in_region: bool) -> int:
        if not is_file or not in_region:
            self._stop()
            return DROPEFFECT_NONE
        if not self.active:
            self.active = True
            self._phase = 0
            self._generation += 1
            try:
                self._show_phase(self._phase)
                self._arm(self._generation)
            except Exception:
                self._stop()
                raise
        return DROPEFFECT_COPY

    def drag_over(self, is_file: bool, in_region: bool) -> int:
        return self.drag_enter(is_file, in_region)

    def drag_leave(self) -> None:
        self._stop()

    def drop(self) -> int:
        self._stop()
        return DROPEFFECT_NONE

    def cancel(self) -> None:
        self._stop()

    def focus_lost(self) -> None:
        self._stop()

    def exception(self) -> None:
        self._stop()

    def _arm(self, generation: int) -> None:
        self._token = self._schedule(
            self.config.tick_ms,
            lambda: self._tick(generation),
        )

    def _tick(self, generation: int) -> None:
        if not self.active or generation != self._generation:
            return
        self._token = None
        self._phase = (self._phase + 1) % 8
        try:
            self._show_phase(self._phase)
            self._arm(generation)
        except Exception:
            try:
                self._stop()
            except Exception:
                pass

    def _stop(self) -> None:
        if not self.active:
            return
        self.active = False
        self._generation += 1
        token, self._token = self._token, None
        try:
            if token is not None:
                self._cancel(token)
        finally:
            self._restore()


def decorate_drag_expectation(
    image: Image.Image,
    phase: int,
    config: DragVisualConfig,
) -> Image.Image:
    """Decorate a copy while preserving the approved frame's Alpha byte-for-byte."""

    base = image.convert("RGBA")
    alpha = base.getchannel("A")
    result = base.copy()
    direction = -1 if phase % 2 else 1
    for box in config.eye_boxes:
        crop = base.crop(box)
        width = max(1, round(crop.width * config.eye_scale))
        height = max(1, round(crop.height * config.eye_scale))
        enlarged = crop.resize((width, height), Image.Resampling.LANCZOS)
        x = (box[0] + box[2] - width) // 2 + direction * config.tremble_pixels
        y = (box[1] + box[3] - height) // 2
        result.paste(enlarged, (x, y), enlarged)

    overlay = Image.new("RGBA", base.size)
    draw = ImageDraw.Draw(overlay)
    if config.head_box is not None:
        draw.rounded_rectangle(
            config.head_box,
            radius=max(2, (config.head_box[2] - config.head_box[0]) // 8),
            fill=(255, 224, 92, config.highlight_opacity),
            outline=(255, 247, 185, min(255, config.highlight_opacity * 3)),
            width=2,
        )
        left, top, right, bottom = config.head_box
        positions = (
            (left + (phase * 7) % max(1, right - left), top + 5),
            (right - 6, top + (phase * 5) % max(1, bottom - top)),
            (left + 7, bottom - 6 - (phase * 3) % max(1, bottom - top)),
        )
        for x, y in positions:
            r = config.particle_radius
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 244, 150, 220))
    result = Image.alpha_composite(result, overlay)
    result = ImageEnhance.Color(result).enhance(1.03)
    result.putalpha(alpha)
    return result

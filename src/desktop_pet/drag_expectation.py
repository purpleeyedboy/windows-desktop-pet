"""Non-destructive drag-expectation state and transient visual composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter


DROPEFFECT_NONE = 0
DROPEFFECT_COPY = 1


@dataclass(frozen=True)
class DragVisualConfig:
    """Candidate values are centralized until real-desktop visual acceptance."""

    # V2.1 does not prescribe these values: all remain pending visual acceptance.
    tick_ms: int = 50
    eye_scale: float = 1.20
    tremble_ratio: float = 0.015
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
    """Add local transient layers without mutating the approved source image."""

    base = image.convert("RGBA")
    result = base.copy()
    transition = min(1.0, max(0.0, phase / 3.0))
    for eye_index, box in enumerate(config.eye_boxes):
        crop = base.crop(box)
        scale = 1.0 + (config.eye_scale - 1.0) * transition
        width = max(1, round(crop.width * scale))
        height = max(1, round(crop.height * scale))
        enlarged = crop.resize((width, height), Image.Resampling.LANCZOS)
        eye_mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(eye_mask).ellipse(
            (1, 1, max(1, width - 2), max(1, height - 2)),
            fill=255,
        )
        eye_mask = eye_mask.filter(ImageFilter.GaussianBlur(max(1.0, width * 0.08)))
        direction = -1 if (phase + eye_index) % 2 else 1
        tremble = max(1, round(crop.width * config.tremble_ratio))
        x = (box[0] + box[2] - width) // 2 + direction * tremble
        y = (box[1] + box[3] - height) // 2
        result.paste(enlarged, (x, y), ImageChops.multiply(enlarged.getchannel("A"), eye_mask))

    overlay = Image.new("RGBA", base.size)
    draw = ImageDraw.Draw(overlay)
    if config.head_box is not None:
        left, top, right, bottom = config.head_box
        head_alpha = base.getchannel("A").crop(config.head_box)
        contour = ImageChops.subtract(
            head_alpha.filter(ImageFilter.MaxFilter(3)),
            head_alpha.filter(ImageFilter.MinFilter(3)),
        )
        contour_layer = Image.new(
            "RGBA", contour.size, (255, 235, 120, config.highlight_opacity * 3)
        )
        overlay.paste(contour_layer, (left, top), contour)
        positions = (
            (left + 20, top - 6),
            (right + 6, top + 50),
            (left - 6, bottom - 40),
        )
        for index, (x, y) in enumerate(positions):
            scale = (0.6, 0.8, 1.0, 1.25, 1.4, 1.25, 1.0, 0.8)[(phase + index * 2) % 8]
            r = max(2, round(config.particle_radius * 2 * scale))
            inner = max(1, r // 3)
            draw.polygon(((x, y-r), (x+inner, y-inner), (x+r, y),
                          (x+inner, y+inner), (x, y+r), (x-inner, y+inner),
                          (x-r, y), (x-inner, y-inner)), fill=(255, 226, 95, 230))
    result = Image.alpha_composite(result, overlay)
    return result

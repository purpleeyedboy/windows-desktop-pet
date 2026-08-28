from __future__ import annotations

import tkinter as tk
from typing import Callable, Protocol

from PIL import Image, ImageDraw

from .bubble_layout import (
    BUBBLE_BODY_SIZE,
    BUBBLE_FONT_SIZE,
    BUBBLE_KAOMOJI_FONT_SIZE,
    BUBBLE_SOURCE_BODY_SIZE,
    BUBBLE_SOURCE_TAIL_OVERLAP,
    BUBBLE_SOURCE_TAIL_SIZE,
    BUBBLE_TEXT_COLOR,
    BUBBLE_TEXT_SAFE_RECT,
)
from .dialogue import is_kaomoji_phrase
from .font_runs import FontRunResolver, draw_layout
from .layered_window import LayeredWindowRenderer
from .model import (
    BubblePlacement,
    Rect,
    TailDirection,
    format_position,
    place_oriented_bubble,
)
from .paths import asset_path


DIRECTIONS: tuple[TailDirection, ...] = ("down", "up", "left", "right")


class Renderer(Protocol):
    def render(self, image: Image.Image, x: int, y: int) -> None: ...

    def set_topmost(self, enabled: bool) -> None: ...


RendererFactory = Callable[[int], Renderer]


class BubbleComposer:
    """Compose the approved image skin, directional tail, and runtime text."""

    def __init__(self) -> None:
        self._resolvers: dict[tuple[str, int], FontRunResolver] = {}
        self._body = self._load_rgba("cat-ear-bow-body.png")
        self._tails = {
            direction: self._load_rgba(f"tail-{direction}.png")
            for direction in DIRECTIONS
        }
        if self._body.size != BUBBLE_SOURCE_BODY_SIZE:
            raise ValueError(
                f"bubble body must be {BUBBLE_SOURCE_BODY_SIZE}, found {self._body.size}"
            )
        for direction, tail in self._tails.items():
            if tail.size != BUBBLE_SOURCE_TAIL_SIZE:
                raise ValueError(
                    f"bubble {direction} tail must be {BUBBLE_SOURCE_TAIL_SIZE}, found {tail.size}"
                )

    @staticmethod
    def _load_rgba(name: str) -> Image.Image:
        with Image.open(asset_path("assets", "bubble", name)) as source:
            return source.convert("RGBA")

    @staticmethod
    def _validated_scale(scale: float) -> float:
        value = float(scale)
        if value <= 0:
            raise ValueError("bubble scale must be positive")
        return value

    def _dimensions(
        self, tail_direction: TailDirection, scale: float
    ) -> tuple[tuple[int, int], tuple[int, int], int, tuple[int, int]]:
        scale = self._validated_scale(scale)
        body_width = max(1, round(BUBBLE_BODY_SIZE[0] * scale))
        body_height = max(
            1,
            round(
                body_width
                * BUBBLE_SOURCE_BODY_SIZE[1]
                / BUBBLE_SOURCE_BODY_SIZE[0]
            ),
        )
        source_scale = body_width / BUBBLE_SOURCE_BODY_SIZE[0]
        tail_size = (
            max(1, round(BUBBLE_SOURCE_TAIL_SIZE[0] * source_scale)),
            max(1, round(BUBBLE_SOURCE_TAIL_SIZE[1] * source_scale)),
        )
        overlap = min(
            tail_size[0] - 1 if tail_size[0] > 1 else 0,
            max(1, round(BUBBLE_SOURCE_TAIL_OVERLAP * source_scale)),
        )
        if tail_direction == "down":
            output_size = (body_width, body_height + tail_size[1] - overlap)
        else:
            output_size = (body_width, body_height)
        return (body_width, body_height), tail_size, overlap, output_size

    def size_for(
        self, tail_direction: TailDirection, scale: float = 1.0
    ) -> tuple[int, int]:
        if tail_direction not in DIRECTIONS:
            raise ValueError(f"unsupported tail direction: {tail_direction!r}")
        return self._dimensions(tail_direction, scale)[3]

    def sizes(self, scale: float = 1.0) -> dict[TailDirection, tuple[int, int]]:
        return {direction: self.size_for(direction, scale) for direction in DIRECTIONS}

    def render(
        self,
        text: str,
        tail_direction: TailDirection,
        scale: float = 1.0,
    ) -> Image.Image:
        if tail_direction not in DIRECTIONS:
            raise ValueError(f"unsupported tail direction: {tail_direction!r}")
        body_size, tail_size, overlap, output_size = self._dimensions(
            tail_direction, scale
        )
        body = self._body.resize(body_size, Image.Resampling.LANCZOS)
        tail = self._tails[tail_direction].resize(
            tail_size, Image.Resampling.LANCZOS
        )
        image = Image.new("RGBA", output_size, (0, 0, 0, 0))
        body_offset = [0, 0]
        if tail_direction == "down":
            tail_offset = (
                (body_size[0] - tail_size[0]) // 2,
                body_size[1] - overlap,
            )
        elif tail_direction == "up":
            tail_offset = ((body_size[0] - tail_size[0]) // 2, overlap)
        elif tail_direction == "left":
            tail_offset = (0, (body_size[1] - tail_size[1]) // 2)
        else:
            tail_offset = (
                body_size[0] - tail_size[0],
                (body_size[1] - tail_size[1]) // 2,
            )

        image.alpha_composite(body, tuple(body_offset))
        image.alpha_composite(tail, tail_offset)
        self._draw_text(image, str(text), tuple(body_offset), body_size)
        return image

    def _draw_text(
        self,
        image: Image.Image,
        text: str,
        body_offset: tuple[int, int],
        body_size: tuple[int, int],
    ) -> None:
        if not text:
            return
        body_scale = body_size[0] / BUBBLE_BODY_SIZE[0]
        left, top, right, bottom = (
            round(value * body_scale) for value in BUBBLE_TEXT_SAFE_RECT
        )
        safe_width = right - left
        safe_height = bottom - top
        kind = "kaomoji" if is_kaomoji_phrase(text) else "chinese"
        base_size = (
            BUBBLE_KAOMOJI_FONT_SIZE if kind == "kaomoji" else BUBBLE_FONT_SIZE
        )
        font_size = max(1, round(base_size * body_scale))
        cache_key = (kind, font_size)
        resolver = self._resolvers.get(cache_key)
        if resolver is None:
            factory = (
                FontRunResolver.for_kaomoji
                if kind == "kaomoji"
                else FontRunResolver.for_chinese
            )
            resolver = self._resolvers.setdefault(cache_key, factory(font_size))
        layout = resolver.layout(text, context=kind)
        ink_height = layout.ink_bbox[3] - layout.ink_bbox[1]
        if layout.total_advance > safe_width:
            raise ValueError(
                f"{kind} text width {layout.total_advance:.2f} exceeds safe width {safe_width}"
            )
        if ink_height > safe_height + 1:
            raise ValueError(
                f"{kind} text height {ink_height} exceeds safe height {safe_height} + 1"
            )
        safe_rect = (
            body_offset[0] + left,
            body_offset[1] + top,
            body_offset[0] + right,
            body_offset[1] + bottom,
        )
        draw_layout(
            ImageDraw.Draw(image),
            layout,
            safe_rect,
            BUBBLE_TEXT_COLOR,
        )


class BubbleWindow:
    def __init__(
        self,
        parent: tk.Misc,
        renderer_factory: RendererFactory = LayeredWindowRenderer,
    ) -> None:
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        try:
            self.window.attributes("-toolwindow", True)
        except tk.TclError:
            pass
        self.window.update_idletasks()
        self.renderer = renderer_factory(self.window.winfo_id())
        self.renderer.set_topmost(True)
        self.composer = BubbleComposer()
        self.last_rect: Rect | None = None
        self._text = ""
        self._hide_job: str | None = None
        self.visible = False

    def _placement(
        self, pet_rect: Rect, screen_rect: Rect
    ) -> tuple[BubblePlacement, float] | None:
        sizes = self.composer.sizes()
        placement = place_oriented_bubble(pet_rect, sizes, screen_rect)
        if placement is None:
            return None
        expected = sizes[placement.tail_direction]
        if (
            placement.rect.width == expected[0]
            and placement.rect.height == expected[1]
        ):
            return placement, 1.0
        scale = min(
            placement.rect.width / expected[0],
            placement.rect.height / expected[1],
        )
        scaled = place_oriented_bubble(
            pet_rect, self.composer.sizes(scale), screen_rect
        )
        return (scaled, scale) if scaled is not None else None

    def _render_at(self, placement: BubblePlacement, scale: float) -> None:
        image = self.composer.render(self._text, placement.tail_direction, scale)
        rect = placement.rect
        if image.size != (rect.width, rect.height):
            rect = Rect(rect.x, rect.y, image.width, image.height)
        self.last_rect = rect
        self.window.geometry(
            f"{rect.width}x{rect.height}{format_position(rect.x, rect.y)}"
        )
        self.window.deiconify()
        self.window.lift()
        self.renderer.render(image, rect.x, rect.y)
        self.visible = True

    def show_message(self, text: str, pet_rect: Rect, screen_rect: Rect) -> None:
        self._text = text
        result = self._placement(pet_rect, screen_rect)
        if result is None:
            self.last_rect = None
            self.hide()
            return
        self._render_at(*result)
        self._cancel_hide_job()
        self._hide_job = self.window.after(1800, self._hide_after_timeout)

    def reposition(self, pet_rect: Rect, screen_rect: Rect) -> None:
        if not self.visible or self.last_rect is None:
            return
        result = self._placement(pet_rect, screen_rect)
        if result is None:
            self.last_rect = None
            self.hide()
            return
        self._render_at(*result)

    def set_always_on_top(self, enabled: bool) -> None:
        self.window.attributes("-topmost", enabled)
        self.renderer.set_topmost(bool(enabled))

    def _cancel_hide_job(self) -> None:
        job = self._hide_job
        self._hide_job = None
        if job is None:
            return
        try:
            self.window.after_cancel(job)
        except tk.TclError:
            pass

    def _hide_after_timeout(self) -> None:
        self._hide_job = None
        self.hide()

    def hide(self) -> None:
        self._cancel_hide_job()
        try:
            self.window.withdraw()
        except tk.TclError:
            pass
        self.visible = False

    def destroy(self) -> None:
        self._cancel_hide_job()
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.visible = False

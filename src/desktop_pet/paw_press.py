"""Deterministic dual-forepaw pointer ownership behind an injectable adapter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


@dataclass(frozen=True)
class PointerPoint:
    x: int
    y: int


@dataclass(frozen=True)
class PointerBounds:
    """Half-open physical-pixel bounds; coordinates may be negative."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int: return self.x + self.width

    @property
    def bottom(self) -> int: return self.y + self.height

    def intersection(self, other: "PointerBounds") -> "PointerBounds | None":
        left, top = max(self.x, other.x), max(self.y, other.y)
        right, bottom = min(self.right, other.right), min(self.bottom, other.bottom)
        if left >= right or top >= bottom:
            return None
        return PointerBounds(left, top, right - left, bottom - top)

    def clamp(self, point: PointerPoint) -> PointerPoint:
        return PointerPoint(
            min(max(point.x, self.x), self.right - 1),
            min(max(point.y, self.y), self.bottom - 1),
        )


class PointerInputAdapter(Protocol):
    def cursor_position(self) -> PointerPoint: ...
    def virtual_bounds(self) -> PointerBounds: ...
    def current_clip(self) -> PointerBounds | None: ...
    def button_down(self, name: str) -> bool: ...
    def capture(self) -> None: ...
    def release_capture(self) -> None: ...
    def set_clip(self, bounds: PointerBounds | None) -> None: ...
    def move(self, point: PointerPoint) -> None: ...
    def press_left(self) -> None: ...
    def release_left(self) -> None: ...


class PawState(Enum):
    IDLE = "idle"
    PRESSED = "pressed"
    HOLDING = "holding"
    PUSHING = "pushing"
    CLOSED = "closed"


class PawPressController:
    def __init__(self, adapter: PointerInputAdapter, *, hold_seconds: float = .18,
                 push_pixels: int = 24) -> None:
        self.adapter = adapter
        self.hold_seconds = hold_seconds
        self.push_pixels = push_pixels
        self.state = PawState.IDLE
        self._started = 0.0
        self._expected: PointerPoint | None = None
        self._original_clip: PointerBounds | None = None
        self._owns_left = False
        self._captured = False
        self._clipped = False

    @property
    def paw_progress(self) -> float:
        return 0.0 if self.state in (PawState.IDLE, PawState.CLOSED) else 1.0

    def start(self, now: float) -> bool:
        if self.state is not PawState.IDLE:
            return False
        self._started = now
        self._expected = self.adapter.cursor_position()
        self._original_clip = self.adapter.current_clip()
        clip = self.adapter.virtual_bounds()
        if self._original_clip is not None:
            clip = clip.intersection(self._original_clip) or clip
        try:
            self.adapter.capture(); self._captured = True
            self.adapter.set_clip(clip); self._clipped = True
            self.adapter.press_left(); self._owns_left = True
            self.state = PawState.PRESSED
            return True
        except Exception:
            self._release_all()
            raise

    def tick(self, now: float) -> None:
        if self.state in (PawState.IDLE, PawState.CLOSED):
            return
        try:
            actual = self.adapter.cursor_position()
            if (actual != self._expected or self.adapter.button_down("right")
                    or not self.adapter.button_down("left")):
                self.cancel()
                return
            elapsed = now - self._started
            if elapsed < .04:
                self.state = PawState.PRESSED
            elif elapsed < self.hold_seconds:
                self.state = PawState.HOLDING
            elif elapsed < self.hold_seconds * 2:
                self.state = PawState.PUSHING
                target = self.adapter.virtual_bounds().clamp(
                    PointerPoint(actual.x, actual.y + self.push_pixels)
                )
                self.adapter.move(target)
                self._expected = target
            else:
                self.cancel()
        except Exception:
            self.cancel()

    def cancel(self) -> None:
        if self.state is PawState.CLOSED:
            return
        self._release_all()
        self.state = PawState.IDLE

    def close(self) -> None:
        self._release_all()
        self.state = PawState.CLOSED

    def _release_all(self) -> None:
        if self._owns_left:
            try: self.adapter.release_left()
            except Exception: pass
            self._owns_left = False
        if self._clipped:
            try: self.adapter.set_clip(self._original_clip)
            except Exception: pass
            self._clipped = False
        if self._captured:
            try: self.adapter.release_capture()
            except Exception: pass
            self._captured = False
        self._expected = None

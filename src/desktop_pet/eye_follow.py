"""Continuous cursor sampling and eye-motion smoothing for the Windows pet."""

from __future__ import annotations

import ctypes
import math
import time
from dataclasses import dataclass
from typing import Callable, Final, Protocol


HORIZONTAL_LIMIT: Final = 3.0
VERTICAL_LIMIT: Final = 2.0
SAMPLE_INTERVAL_MS: Final = 33
TIME_CONSTANT_SECONDS: Final = 0.060
MAX_DT_SECONDS: Final = 0.100
STABILITY_THRESHOLD: Final = 0.006
REFERENCE_DISPLAY_HEIGHT: Final = 280.0
REFERENCE_ACTIVATION_RADIUS: Final = 100.0


@dataclass(frozen=True)
class CursorPoint:
    x: int
    y: int


@dataclass(frozen=True)
class EyeGeometry:
    """Current on-screen eye midpoint and displayed pet height."""

    midpoint_x: float
    midpoint_y: float
    display_height: float


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]


class CursorProvider(Protocol):
    def position(self) -> CursorPoint | None: ...


class GeometryProvider(Protocol):
    def __call__(self) -> EyeGeometry: ...


class Win32CursorProvider:
    """Reads the system cursor through ``GetCursorPos`` without a mouse hook."""

    def __init__(self, user32=None) -> None:
        if user32 is None:
            windll = getattr(ctypes, "windll", None)
            user32 = None if windll is None else windll.user32
        self._user32 = user32

    def position(self) -> CursorPoint | None:
        if self._user32 is None:
            return None
        point = _POINT()
        try:
            succeeded = self._user32.GetCursorPos(ctypes.byref(point))
        except (AttributeError, OSError):
            return None
        if not succeeded:
            return None
        return CursorPoint(point.x, point.y)


def cursor_target(
    cursor_dx: float, cursor_dy: float, activation_radius: float
) -> tuple[float, float]:
    """Return radial-clamped, elliptical source-pixel offsets for a cursor vector."""
    if (
        not math.isfinite(cursor_dx)
        or not math.isfinite(cursor_dy)
        or not math.isfinite(activation_radius)
        or activation_radius <= 0.0
    ):
        raise ValueError(
            "cursor coordinates and activation radius must be finite, with positive radius"
        )
    if cursor_dx == 0.0 and cursor_dy == 0.0:
        return (0.0, 0.0)

    scale = max(abs(cursor_dx), abs(cursor_dy))
    scaled_x = cursor_dx / scale
    scaled_y = cursor_dy / scale
    scaled_distance = math.hypot(scaled_x, scaled_y)
    if scale >= activation_radius:
        strength = 1.0
    else:
        strength = min((scale / activation_radius) * scaled_distance, 1.0)
    return (
        HORIZONTAL_LIMIT * scaled_x / scaled_distance * strength,
        VERTICAL_LIMIT * scaled_y / scaled_distance * strength,
    )


class EyeMotionController:
    """Owns one UI-thread scheduler loop and reports meaningful pose changes.

    The scheduler, cancel callback, lifecycle methods, and tick callbacks must
    all run on the Tk UI thread. Generation checks reject stale queued callbacks
    but do not provide general thread safety.
    """

    def __init__(
        self,
        scheduler: Callable[[int, Callable[[], None]], object],
        cancel: Callable[[object], None],
        cursor_provider: CursorProvider,
        geometry_provider: GeometryProvider,
        pose_changed: Callable[[float, float], None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._scheduler = scheduler
        self._cancel = cancel
        self._cursor_provider = cursor_provider
        self._geometry_provider = geometry_provider
        self._pose_changed = pose_changed
        self._clock = clock
        self._pose = (0.0, 0.0)
        self._last_emitted = self._pose
        self._last_time: float | None = None
        self._scheduled: object | None = None
        self._running = False
        self._stopped = False
        self._generation = 0

    @property
    def pose(self) -> tuple[float, float]:
        return self._pose

    def start(self) -> None:
        if self._stopped or self._running:
            return
        self._generation += 1
        self._running = True
        self._last_time = self._clock()
        self._schedule()

    def pause(self) -> None:
        if not self._running:
            return
        self._generation += 1
        self._running = False
        if self._scheduled is not None:
            self._cancel(self._scheduled)
            self._scheduled = None

    def resume(self) -> None:
        self.start()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._generation += 1
        self._running = False
        if self._scheduled is not None:
            self._cancel(self._scheduled)
            self._scheduled = None

    def _schedule(self) -> None:
        if self._running and not self._stopped and self._scheduled is None:
            generation = self._generation
            self._scheduled = self._scheduler(
                SAMPLE_INTERVAL_MS, lambda: self._tick(generation)
            )

    def _tick(self, generation: int) -> None:
        if generation != self._generation:
            return
        self._scheduled = None
        if not self._running or self._stopped:
            return

        now = self._clock()
        previous_time = self._last_time if self._last_time is not None else now
        dt = min(max(now - previous_time, 0.0), MAX_DT_SECONDS)
        self._last_time = now

        geometry = self._current_geometry()
        point = self._cursor_provider.position()
        if point is None:
            target = (0.0, 0.0)
        else:
            target = cursor_target(
                float(point.x) - geometry.midpoint_x,
                float(point.y) - geometry.midpoint_y,
                self._activation_radius(geometry.display_height),
            )
        alpha = 1.0 - math.exp(-dt / TIME_CONSTANT_SECONDS)
        self._pose = tuple(
            current + alpha * (requested - current)
            for current, requested in zip(self._pose, target, strict=True)
        )
        if (
            abs(self._pose[0] - self._last_emitted[0]) >= STABILITY_THRESHOLD
            or abs(self._pose[1] - self._last_emitted[1]) >= STABILITY_THRESHOLD
        ):
            self._last_emitted = self._pose
            self._pose_changed(*self._pose)
        self._schedule()

    def _current_geometry(self) -> EyeGeometry:
        geometry = self._geometry_provider()
        try:
            midpoint_x = float(geometry.midpoint_x)
            midpoint_y = float(geometry.midpoint_y)
            display_height = float(geometry.display_height)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("geometry provider returned invalid eye geometry") from error
        if not math.isfinite(midpoint_x) or not math.isfinite(midpoint_y):
            raise ValueError("eye midpoint must be finite")
        self._activation_radius(display_height)
        return EyeGeometry(midpoint_x, midpoint_y, display_height)

    @staticmethod
    def _activation_radius(display_height: float) -> float:
        if not math.isfinite(display_height) or display_height <= 0.0:
            raise ValueError("display height must be finite and positive")
        activation_radius = (
            display_height / REFERENCE_DISPLAY_HEIGHT * REFERENCE_ACTIVATION_RADIUS
        )
        if not math.isfinite(activation_radius) or activation_radius <= 0.0:
            raise ValueError("activation radius must be finite and positive")
        return activation_radius

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
SAMPLE_INTERVAL_SECONDS: Final = SAMPLE_INTERVAL_MS / 1000.0
TIME_CONSTANT_SECONDS: Final = 0.060
HEAD_TIME_CONSTANT_SECONDS: Final = 0.220
HEAD_RENDER_GAIN: Final = 1.225
EYE_HEAD_COMPENSATION: Final = 0.35
MAX_DT_SECONDS: Final = 0.100
STABILITY_THRESHOLD: Final = 0.006
REFERENCE_DISPLAY_HEIGHT: Final = 280.0
REFERENCE_ACTIVATION_RADIUS: Final = 100.0
_SCHEDULING: Final = object()


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
        coordinated_pose_changed: Callable[
            [float, float, float, float], None
        ]
        | None = None,
        pulse: Callable[[], None] | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._cancel = cancel
        self._cursor_provider = cursor_provider
        self._geometry_provider = geometry_provider
        self._pose_changed = pose_changed
        self._coordinated_pose_changed = coordinated_pose_changed
        self._pulse = pulse
        self._clock = clock
        self._pose = (0.0, 0.0)
        self._head_pose = (0.0, 0.0)
        self._last_emitted = self._pose
        self._last_emitted_coordinated = (0.0, 0.0, 0.0, 0.0)
        self._last_time: float | None = None
        self._next_deadline: float | None = None
        self._scheduled: object | None = None
        self._schedule_slot: object | None = None
        self._running = False
        self._paused = False
        self._stopped = False
        self._generation = 0

    @property
    def pose(self) -> tuple[float, float]:
        return self._pose

    @property
    def coordinated_pose(self) -> tuple[float, float, float, float]:
        """Return rendered eye offsets followed by rendered head coordinates."""
        focus_x = self._pose[0] / HORIZONTAL_LIMIT
        focus_y = self._pose[1] / VERTICAL_LIMIT
        residual_x, residual_y = self._radial_clamp(
            focus_x - EYE_HEAD_COMPENSATION * self._head_pose[0],
            focus_y - EYE_HEAD_COMPENSATION * self._head_pose[1],
        )
        head_x, head_y = self._radial_clamp(
            self._head_pose[0] * HEAD_RENDER_GAIN,
            self._head_pose[1] * HEAD_RENDER_GAIN,
        )
        return (
            HORIZONTAL_LIMIT * residual_x,
            VERTICAL_LIMIT * residual_y,
            head_x,
            head_y,
        )

    def start(self) -> None:
        if self._stopped or self._running:
            return
        self._generation += 1
        self._running = True
        self._paused = False
        now = self._clock()
        self._last_time = now
        self._next_deadline = now + SAMPLE_INTERVAL_SECONDS
        self._schedule()

    def pause(self) -> None:
        if not self._running:
            return
        self._generation += 1
        self._running = False
        self._paused = True
        self._next_deadline = None
        token = self._scheduled
        self._scheduled = None
        self._schedule_slot = None
        if token is not None and token is not _SCHEDULING:
            try:
                self._cancel(token)
            except Exception:
                self._generation += 1
                self._paused = False
                self._stopped = True
                raise

    def resume(self) -> None:
        self.start()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._generation += 1
        self._running = False
        self._paused = False
        self._next_deadline = None
        token = self._scheduled
        self._scheduled = None
        self._schedule_slot = None
        if token is not None and token is not _SCHEDULING:
            try:
                self._cancel(token)
            except Exception:
                pass

    def synchronize_pose(self, eye_x: float, eye_y: float) -> None:
        """Synchronize a paused controller without emitting or scheduling."""
        if not self._paused or self._running or self._stopped:
            raise RuntimeError("eye pose can only be synchronized while paused")
        try:
            pose = (float(eye_x), float(eye_y))
        except (OverflowError, TypeError, ValueError) as error:
            raise ValueError("eye pose must contain finite numeric values") from error
        if (
            not math.isfinite(pose[0])
            or not math.isfinite(pose[1])
            or abs(pose[0]) > HORIZONTAL_LIMIT
            or abs(pose[1]) > VERTICAL_LIMIT
        ):
            raise ValueError("eye pose is outside the supported finite range")
        self._pose = pose
        self._last_emitted = pose
        self._last_emitted_coordinated = self.coordinated_pose

    def synchronize_center(self) -> None:
        """Synchronize every coordinated channel to exact center while paused."""
        if not self._paused or self._running or self._stopped:
            raise RuntimeError("eye pose can only be synchronized while paused")
        self._pose = (0.0, 0.0)
        self._head_pose = (0.0, 0.0)
        self._last_emitted = (0.0, 0.0)
        self._last_emitted_coordinated = (0.0, 0.0, 0.0, 0.0)

    def _schedule(self) -> None:
        if self._running and not self._stopped and self._scheduled is None:
            now = self._clock()
            if self._next_deadline is None:
                self._next_deadline = now + SAMPLE_INTERVAL_SECONDS
            elif self._next_deadline <= now:
                missed = math.floor(
                    (now - self._next_deadline) / SAMPLE_INTERVAL_SECONDS
                )
                self._next_deadline += (missed + 1) * SAMPLE_INTERVAL_SECONDS
                if self._next_deadline <= now:
                    self._next_deadline += SAMPLE_INTERVAL_SECONDS
            remaining_ms = (self._next_deadline - now) * 1000.0
            delay_ms = max(1, math.ceil(remaining_ms - 1e-9))
            generation = self._generation
            slot = object()
            fired = False
            scheduler_returned = False

            def scheduled_callback() -> None:
                nonlocal fired
                fired = True
                if scheduler_returned:
                    self._tick(generation, slot)

            self._schedule_slot = slot
            self._scheduled = _SCHEDULING
            try:
                token = self._scheduler(delay_ms, scheduled_callback)
            except Exception:
                self._fail_schedule(generation, slot)
                raise
            scheduler_returned = True
            if fired:
                self._fail_schedule(generation, slot)
                raise RuntimeError("scheduler callback ran synchronously")
            if (
                self._generation == generation
                and self._running
                and not self._stopped
                and self._schedule_slot is slot
            ):
                self._scheduled = token
            else:
                try:
                    self._cancel(token)
                except Exception:
                    pass

    def _tick(self, generation: int, slot: object) -> None:
        if generation != self._generation or self._schedule_slot is not slot:
            return
        self._scheduled = None
        self._schedule_slot = None
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
        if target == (0.0, 0.0) and all(
            abs(value) <= STABILITY_THRESHOLD for value in self._pose
        ):
            self._pose = (0.0, 0.0)

        normalized_target = (
            target[0] / HORIZONTAL_LIMIT,
            target[1] / VERTICAL_LIMIT,
        )
        head_alpha = 1.0 - math.exp(-dt / HEAD_TIME_CONSTANT_SECONDS)
        self._head_pose = self._radial_clamp(
            self._head_pose[0]
            + head_alpha * (normalized_target[0] - self._head_pose[0]),
            self._head_pose[1]
            + head_alpha * (normalized_target[1] - self._head_pose[1]),
        )
        if target == (0.0, 0.0) and all(
            abs(value) <= STABILITY_THRESHOLD for value in self._head_pose
        ):
            self._head_pose = (0.0, 0.0)

        if self._coordinated_pose_changed is None:
            if self._pose == (0.0, 0.0) and self._last_emitted != (0.0, 0.0):
                self._last_emitted = self._pose
                self._pose_changed(*self._pose)
            elif (
                abs(self._pose[0] - self._last_emitted[0]) >= STABILITY_THRESHOLD
                or abs(self._pose[1] - self._last_emitted[1]) >= STABILITY_THRESHOLD
            ):
                self._last_emitted = self._pose
                self._pose_changed(*self._pose)
        else:
            coordinated = self.coordinated_pose
            if coordinated == (0.0, 0.0, 0.0, 0.0) and (
                self._last_emitted_coordinated != coordinated
            ):
                self._last_emitted_coordinated = coordinated
                self._coordinated_pose_changed(*coordinated)
            elif any(
                abs(value - previous) >= STABILITY_THRESHOLD
                for value, previous in zip(
                    coordinated,
                    self._last_emitted_coordinated,
                    strict=True,
                )
            ):
                self._last_emitted_coordinated = coordinated
                self._coordinated_pose_changed(*coordinated)
        if self._pulse is not None:
            self._pulse()
        self._schedule()

    def _fail_schedule(self, generation: int, slot: object) -> None:
        if self._generation != generation or self._schedule_slot is not slot:
            return
        self._generation += 1
        self._scheduled = None
        self._schedule_slot = None
        self._running = False
        self._paused = False
        self._stopped = True
        self._next_deadline = None

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

    @staticmethod
    def _radial_clamp(x: float, y: float) -> tuple[float, float]:
        magnitude = math.hypot(x, y)
        if magnitude <= 1.0:
            return (x, y)
        return (x / magnitude, y / magnitude)

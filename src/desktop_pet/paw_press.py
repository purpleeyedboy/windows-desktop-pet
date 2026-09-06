"""Single-forepaw feature adapter for a shared activity and cursor service."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol


@dataclass(frozen=True)
class PointerPoint:
    x: int
    y: int


@dataclass(frozen=True)
class PointerBounds:
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


class CursorMovementService(Protocol):
    """Foundation adapter: position access only; never emits input events."""

    def position(self) -> PointerPoint: ...
    def set_position(self, point: PointerPoint) -> None: ...
    def pointer_nominal_height(self) -> int: ...
    def monitor_bounds_for(self, point: PointerPoint) -> PointerBounds: ...
    def current_clip(self) -> PointerBounds | None: ...


class PawInputGate(Protocol):
    """Read-only bridge to the shared InputRouter/InputGate."""

    def any_button_down(self) -> bool: ...
    def pointer_interaction_blocked(self) -> bool: ...
    def paw_activity_allowed(self) -> bool: ...


class PawActivityService(Protocol):
    """Adapter point for foundation ActivityCoordinator's serialized queue."""

    def request_paw(self, side: "PawSide") -> "ActivityApproval | None": ...
    def validate_paw(self, approval: "ActivityApproval") -> bool: ...
    def complete_paw(self, approval: "ActivityApproval") -> None: ...
    def paw_allowed(self) -> bool: ...


class LocalPawActivityAdapter:
    """Feature-local compatibility adapter until the shared foundation lands.

    It creates no application state, queue, clock, or persistence.  The shared
    ActivityCoordinator can replace it through the same PawActivityService API.
    """

    def __init__(self) -> None:
        self._active: ActivityApproval | None = None
        self._version = 0

    def request_paw(self, side: "PawSide") -> "ActivityApproval | None":
        if self._active is not None:
            return None
        self._version += 1
        approval = ActivityApproval(
            f"paw-{side.value}-{self._version}", self._version, object()
        )
        self._active = approval
        return approval

    def validate_paw(self, approval: "ActivityApproval") -> bool:
        return self._active == approval

    def complete_paw(self, approval: "ActivityApproval") -> None:
        if self._active == approval:
            self._active = None

    def paw_allowed(self) -> bool:
        return self._active is None


@dataclass(frozen=True)
class ActivityApproval:
    animation_id: str
    state_version: int
    cancellation_token: object


class PawSide(Enum):
    LEFT = "left"
    RIGHT = "right"


class PawState(Enum):
    IDLE = "idle"
    LIFT = "lift"
    PAUSE = "pause"
    PRESS = "press"
    RECOVER = "recover"
    COOLDOWN = "cooldown"
    CLOSED = "closed"


@dataclass(frozen=True)
class PawPose:
    state: PawState
    left_y: float = 0.0
    right_y: float = 0.0


@dataclass(frozen=True)
class PawMotionConfig:
    lift_seconds: float = .12
    pause_seconds: float = .08
    press_seconds: float = .16
    recover_seconds: float = .24
    cooldown_seconds: float = .60
    lift_pixels: float = 6.0
    press_pixels: float = 5.0
    cursor_base_pixels: int = 14
    cursor_min_pixels: int = 8
    cursor_max_pixels: int = 28
    takeover_tolerance_pixels: int = 4


class PawPressController:
    def __init__(
        self,
        cursor: CursorMovementService,
        input_gate: PawInputGate,
        *,
        approval_validator: Callable[[ActivityApproval], bool],
        on_complete: Callable[[ActivityApproval], None] | None = None,
        config: PawMotionConfig = PawMotionConfig(),
    ) -> None:
        self.cursor = cursor
        self.input_gate = input_gate
        self.approval_validator = approval_validator
        self.on_complete = on_complete or (lambda _approval: None)
        self.config = config
        self.LIFT_END = config.lift_seconds
        self.PAUSE_END = self.LIFT_END + config.pause_seconds
        self.PRESS_END = self.PAUSE_END + config.press_seconds
        self.RECOVER_END = self.PRESS_END + config.recover_seconds
        self.COOLDOWN_END = self.RECOVER_END + config.cooldown_seconds
        self.state = PawState.IDLE
        self.side: PawSide | None = None
        self._approval: ActivityApproval | None = None
        self._started = 0.0
        self._release_point: PointerPoint | None = None
        self._press_start: PointerPoint | None = None
        self._expected: PointerPoint | None = None
        self._start_monitor: PointerBounds | None = None
        self._cursor_cancelled = False
        self._cursor_failed = False

    def start(self, side: PawSide, approval: ActivityApproval, now: float) -> bool:
        if self.state is not PawState.IDLE or not self.input_gate.paw_activity_allowed():
            return False
        self.side, self._approval, self._started = side, approval, now
        self.state = PawState.LIFT
        self._cursor_cancelled = self.input_gate.pointer_interaction_blocked()
        self._cursor_failed = False
        try:
            self._release_point = self.cursor.position()
        except Exception:
            self._release_point = None
            self._cursor_cancelled = True
        return True

    def sample(self, now: float) -> PawPose:
        if self.state in (PawState.IDLE, PawState.CLOSED):
            return PawPose(self.state)
        approval = self._approval
        if (approval is None or not self.approval_validator(approval)
                or not self.input_gate.paw_activity_allowed()):
            self.cancel()
            return PawPose(self.state)
        elapsed = max(0.0, now - self._started)
        if elapsed < self.LIFT_END:
            self.state = PawState.LIFT
            amount = -self.config.lift_pixels * _smooth(elapsed / self.LIFT_END)
        elif elapsed < self.PAUSE_END:
            self.state = PawState.PAUSE
            amount = -self.config.lift_pixels
        elif elapsed < self.PRESS_END:
            self.state = PawState.PRESS
            progress = (elapsed - self.PAUSE_END) / (self.PRESS_END - self.PAUSE_END)
            travel = self.config.lift_pixels + self.config.press_pixels
            amount = -self.config.lift_pixels + travel * _smooth(progress)
            self._move_cursor(progress)
        elif elapsed < self.RECOVER_END:
            self.state = PawState.RECOVER
            progress = (elapsed - self.PRESS_END) / (self.RECOVER_END - self.PRESS_END)
            amount = self.config.press_pixels * (1.0 - _smooth(progress))
        elif elapsed < self.COOLDOWN_END:
            self.state = PawState.COOLDOWN
            amount = 0.0
        else:
            self.state = PawState.IDLE
            self.side = None
            self._approval = None
            self.on_complete(approval)
            return PawPose(self.state)
        self._observe_takeover(elapsed)
        return _pose(self.state, self.side, amount)

    def cancel(self) -> None:
        if self.state is PawState.CLOSED:
            return
        approval = self._approval
        self.state, self.side, self._approval = PawState.IDLE, None, None
        self._cursor_cancelled = True
        if approval is not None:
            self.on_complete(approval)

    def close(self) -> None:
        self.cancel()
        self.state = PawState.CLOSED

    def _observe_takeover(self, elapsed: float) -> None:
        if self._cursor_cancelled or self._cursor_failed:
            return
        if self.input_gate.any_button_down() or self.input_gate.pointer_interaction_blocked():
            self._cursor_cancelled = True
            return
        if elapsed >= self.PAUSE_END or self._release_point is None:
            return
        try:
            if _distance(self.cursor.position(), self._release_point) > self.config.takeover_tolerance_pixels:
                self._cursor_cancelled = True
        except Exception:
            self._cursor_failed = True

    def _move_cursor(self, progress: float) -> None:
        if self._cursor_cancelled or self._cursor_failed:
            return
        if self.input_gate.any_button_down() or self.input_gate.pointer_interaction_blocked():
            self._cursor_cancelled = True
            return
        try:
            actual = self.cursor.position()
            if self._press_start is None:
                if (self._release_point is not None and _distance(actual, self._release_point)
                        > self.config.takeover_tolerance_pixels):
                    self._cursor_cancelled = True
                    return
                self._press_start = self._expected = actual
                self._start_monitor = self.cursor.monitor_bounds_for(actual)
            elif (self._expected is None or _distance(actual, self._expected)
                    > self.config.takeover_tolerance_pixels):
                self._cursor_cancelled = True
                return
            height = self.cursor.pointer_nominal_height()
            distance = self.config.cursor_base_pixels if height <= 0 else max(
                self.config.cursor_min_pixels,
                min(self.config.cursor_max_pixels,
                    round(self.config.cursor_base_pixels * height / 32)),
            )
            desired = PointerPoint(self._press_start.x,
                                   self._press_start.y + round(distance * _smooth(progress)))
            bounds = self._start_monitor
            current_monitor = self.cursor.monitor_bounds_for(self._press_start)
            if bounds is not None:
                bounds = bounds.intersection(current_monitor)
            clip = self.cursor.current_clip()
            if bounds is not None and clip is not None:
                bounds = bounds.intersection(clip)
            if bounds is None:
                self._cursor_cancelled = True
                return
            desired = bounds.clamp(desired)
            if desired == actual:
                self._expected = actual
                return
            self.cursor.set_position(desired)
            self._expected = desired
        except Exception:
            self._cursor_failed = True


def _distance(first: PointerPoint, second: PointerPoint) -> int:
    return max(abs(first.x - second.x), abs(first.y - second.y))


def _smooth(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def _pose(state: PawState, side: PawSide | None, amount: float) -> PawPose:
    if side is PawSide.LEFT:
        return PawPose(state, left_y=amount)
    if side is PawSide.RIGHT:
        return PawPose(state, right_y=amount)
    return PawPose(state)

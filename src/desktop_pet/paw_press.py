"""Single-forepaw feature adapter for a shared activity and cursor service."""

from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_right
from enum import Enum
from typing import Callable, Protocol

from .foundation.runtime import Activity, ActivityCoordinator, ActivityToken


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
    def cancel_paw(self, approval: "ActivityApproval") -> None: ...
    def attach_paw_recovery(self, approval: "ActivityApproval", recovery: Callable[[], None]) -> None: ...


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

    def cancel_paw(self, approval: "ActivityApproval") -> None:
        self.complete_paw(approval)

    def attach_paw_recovery(self, approval, recovery) -> None:
        pass

    def paw_allowed(self) -> bool:
        return self._active is None


class FoundationPawActivityAdapter:
    """Narrow PAWS port backed exclusively by the shared coordinator."""

    def __init__(self, coordinator: ActivityCoordinator) -> None:
        self._coordinator = coordinator

    @staticmethod
    def _token(approval: "ActivityApproval") -> ActivityToken | None:
        token = approval.cancellation_token
        return token if isinstance(token, ActivityToken) else None

    def request_paw(self, side: "PawSide") -> "ActivityApproval | None":
        animation_id = f"forepaw-{side.value}"
        token = self._coordinator.request_activity(
            Activity.BODY_ACTION,
            animation_id=animation_id,
            timeout_seconds=2.0,
        )
        if token is None:
            return None
        return ActivityApproval(animation_id, token.version, token)

    def validate_paw(self, approval: "ActivityApproval") -> bool:
        token = self._token(approval)
        return bool(
            token is not None
            and self._coordinator.current_token == token
            and token.version == approval.state_version
            and token.animation_id == approval.animation_id
        )

    def complete_paw(self, approval: "ActivityApproval") -> None:
        token = self._token(approval)
        if token is not None:
            self._coordinator.complete(token, animation_id=approval.animation_id)

    def cancel_paw(self, approval: "ActivityApproval") -> None:
        token = self._token(approval)
        if token is not None:
            self._coordinator.cancel_and_recover(token)

    def attach_paw_recovery(
        self, approval: "ActivityApproval", recovery: Callable[[], None]
    ) -> None:
        token = self._token(approval)
        if token is None or not self.validate_paw(approval):
            raise ValueError("cannot attach recovery to stale paw approval")
        self._coordinator.attach_recovery(token, recovery)

    def paw_allowed(self) -> bool:
        return self._coordinator.permits(Activity.BODY_ACTION)


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
    frame_index: int = 0


@dataclass(frozen=True)
class PawMotionConfig:
    lift_seconds: float = .12
    pause_seconds: float = .08
    press_seconds: float = .16
    recover_seconds: float = .24
    cooldown_seconds: float = .60
    lift_pixels: float = 6.0
    press_pixels: float = 5.0
    # 2.5x the previously tested displacement. Scale the complete gesture,
    # never each tick; monitor/clip bounds and user takeover remain authoritative.
    cursor_base_pixels: int = 35
    cursor_min_pixels: int = 20
    cursor_max_pixels: int = 70
    takeover_tolerance_pixels: int = 4


class PawPressController:
    FRAME_TIMES_MS = (0, 40, 80, 120, 200, 240, 280, 320, 360,
                      400, 440, 480, 520, 560, 600)
    def __init__(
        self,
        cursor: CursorMovementService,
        input_gate: PawInputGate,
        *,
        approval_validator: Callable[[ActivityApproval], bool],
        on_complete: Callable[[ActivityApproval], None] | None = None,
        config: PawMotionConfig = PawMotionConfig(),
        on_cancel: Callable[[ActivityApproval], None] | None = None,
    ) -> None:
        self.cursor = cursor
        self.input_gate = input_gate
        self.approval_validator = approval_validator
        self.on_complete = on_complete or (lambda _approval: None)
        self.on_cancel = on_cancel or self.on_complete
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
        self.cancellation_error: Exception | None = None

    def start(self, side: PawSide, approval: ActivityApproval, now: float) -> bool:
        if self.state is not PawState.IDLE or not self.input_gate.paw_activity_allowed():
            return False
        self.side, self._approval, self._started = side, approval, now
        self.state = PawState.LIFT
        # Each click owns a fresh absolute trajectory. Reusing a prior action's
        # origin either cancels this click or pulls toward an old cursor point.
        self._press_start = None
        self._expected = None
        self._start_monitor = None
        self._cursor_cancelled = self.input_gate.pointer_interaction_blocked()
        self._cursor_failed = False
        self.cancellation_error = None
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
            # A timer can skip the final press sample. Finish the absolute
            # bounded trajectory once at recovery, unless the user took over.
            self._move_cursor(1.0)
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
        frame_index = max(0, min(len(self.FRAME_TIMES_MS) - 1,
            bisect_right(self.FRAME_TIMES_MS, round(elapsed * 1000)) - 1))
        return _pose(self.state, self.side, amount, frame_index)

    def begin_presentation(self, now: float) -> bool:
        """Start artwork timing after recentering; retain the click's cursor origin."""
        if self.state is not PawState.LIFT or self._press_start is not None:
            return False
        if self._approval is None or not self.approval_validator(self._approval):
            return False
        self._started = now
        return True

    def cancel(self, *, notify: bool = True) -> None:
        if self.state is PawState.CLOSED:
            return
        approval = self._approval
        self.state, self.side, self._approval = PawState.IDLE, None, None
        self._cursor_cancelled = True
        if approval is not None and notify:
            try:
                self.on_cancel(approval)
            except Exception as error:
                # Cancellation is a recovery boundary invoked by focus loss,
                # renderer failure and shutdown.  External ownership cleanup
                # must not prevent a terminal pose; retain the error so it is
                # observable rather than silently treating cleanup as clean.
                self.cancellation_error = error

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


def _pose(state: PawState, side: PawSide | None, amount: float,
          frame_index: int = 0) -> PawPose:
    if side is PawSide.LEFT:
        return PawPose(state, left_y=amount, frame_index=frame_index)
    if side is PawSide.RIGHT:
        return PawPose(state, right_y=amount, frame_index=frame_index)
    return PawPose(state, frame_index=frame_index)

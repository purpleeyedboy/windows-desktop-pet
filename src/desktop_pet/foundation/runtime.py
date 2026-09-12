"""Single-queue runtime state and activity ownership for V2.1 features."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from queue import SimpleQueue
from threading import get_ident
from typing import Any, Callable
from uuid import uuid4

from .sources import TimeSource


class Health(str, Enum):
    NORMAL = "normal"
    HUNGRY = "hungry"
    SEVERE = "severe"
    CRITICAL = "critical"


class Activity(str, Enum):
    IDLE = "idle"
    BLINK = "blink"
    GROOM = "groom"
    NORMAL_HUNGER_ANIMATION = "normal_hunger_animation"
    EAR_ACTION = "ear_action"
    BODY_ACTION = "body_action"
    SEVERE_HUNGER_ANIMATION = "severe_hunger_animation"
    CONTEXT_MENU_OPEN = "context_menu_open"
    DRAG_PREVIEW = "drag_preview"
    TRANSACTION_REVIEW = "transaction_review"
    FEED_CONFIRM = "feed_confirm"
    FEED_ANIMATION = "feed_animation"
    FEED_PROCESSING = "feed_processing"
    SHUTTING_DOWN = "shutting_down"


PRIORITY = {activity: index for index, activity in enumerate(Activity)}


@dataclass(frozen=True)
class RuntimeEvent:
    type: str
    source: str
    monotonic_time: float
    correlation_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ActivityToken:
    activity: Activity
    version: int
    cancellation_id: str
    animation_id: str | None = None
    deadline: float | None = None


@dataclass(frozen=True)
class RuntimeSnapshot:
    health: Health = Health.NORMAL
    activity: Activity = Activity.IDLE
    eye: str = "following"
    mouth: str = "neutral"
    tear: str = "hidden"
    particle: str = "hidden"
    input_gate: str = "normal"
    activity_version: int = 0


class ActivityCoordinator:
    """The sole writer of orthogonal runtime state."""

    def __init__(self, clock: TimeSource) -> None:
        self._clock = clock
        self._snapshot = RuntimeSnapshot()
        self._token: ActivityToken | None = None
        self._recovery: dict[str, Callable[[], None]] = {}

    def snapshot(self) -> RuntimeSnapshot:
        return self._snapshot

    def permits(self, activity: Activity) -> bool:
        if self._snapshot.health is Health.CRITICAL and activity in {
            Activity.EAR_ACTION,
            Activity.BODY_ACTION,
            Activity.GROOM,
            Activity.NORMAL_HUNGER_ANIMATION,
        }:
            return False
        return self._snapshot.activity is Activity.IDLE or PRIORITY[activity] > PRIORITY[self._snapshot.activity]

    @property
    def current_token(self) -> ActivityToken | None:
        return self._token

    def request_activity(self, activity: Activity, *, animation_id: str | None = None, timeout_seconds: float = 30.0) -> ActivityToken | None:
        if not self.permits(activity):
            return None
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("activity timeout must be positive")
        if self._token is not None:
            previous = self._token
            try:
                self._cancel_physical(previous)
            finally:
                self._recover_neutral(previous)
        # A recovery callback may have acquired a newer activity. It owns the
        # runtime now; the interrupted request must not overwrite its token.
        if self._token is not None or not self.permits(activity):
            return None
        version = self._snapshot.activity_version + 1
        token = ActivityToken(activity, version, uuid4().hex, animation_id, self._clock.monotonic() + timeout_seconds)
        self._token = token
        self._snapshot = replace(
            self._snapshot,
            activity=activity,
            activity_version=version,
            input_gate=self._derive_input_gate(activity),
            eye="following" if activity is Activity.DRAG_PREVIEW else self._snapshot.eye,
            tear="hidden" if activity is Activity.DRAG_PREVIEW else self._snapshot.tear,
        )
        return token

    def attach_recovery(self, token: ActivityToken, recovery: Callable[[], None]) -> None:
        if token != self._token:
            raise ValueError("cannot attach recovery to a stale activity")
        self._recovery[token.cancellation_id] = recovery

    def complete(self, token: ActivityToken, *, animation_id: str | None = None) -> bool:
        if not self._matches(token, animation_id):
            return False
        self._recover_neutral()
        return True

    def cancel_and_recover(self, token: ActivityToken | None = None) -> bool:
        if token is not None and not self._matches(token, token.animation_id):
            return False
        if self._token is not None:
            previous = self._token
            try:
                self._cancel_physical(previous)
            finally:
                self._recover_neutral(previous)
        else:
            self._recover_neutral()
        return True

    def _set_health(self, health: Health) -> None:
        self._snapshot = replace(self._snapshot, health=health)

    def expire_timeout(self) -> bool:
        if self._token is None or self._token.deadline is None or self._clock.monotonic() < self._token.deadline:
            return False
        previous = self._token
        try:
            self._cancel_physical(previous)
        finally:
            self._recover_neutral(previous)
        return True

    def _matches(self, token: ActivityToken, animation_id: str | None) -> bool:
        return (
            self._token == token
            and token.activity is self._snapshot.activity
            and token.version == self._snapshot.activity_version
            and token.cancellation_id == self._token.cancellation_id
            and token.animation_id == animation_id
        )

    def _recover_neutral(self, expected: ActivityToken | None = None) -> None:
        if expected is not None and self._token != expected:
            return
        if self._token is not None:
            self._recovery.pop(self._token.cancellation_id, None)
        self._token = None
        self._snapshot = replace(
            self._snapshot,
            activity=Activity.IDLE,
            activity_version=self._snapshot.activity_version + 1,
            input_gate="normal",
            mouth="neutral",
            particle="hidden",
            tear="visible" if self._snapshot.health in {Health.SEVERE, Health.CRITICAL} else "hidden",
        )

    def _cancel_physical(self, token: ActivityToken) -> None:
        recovery = self._recovery.pop(token.cancellation_id, None)
        if recovery is not None:
            recovery()

    @staticmethod
    def _derive_input_gate(activity: Activity) -> str:
        if activity is Activity.SHUTTING_DOWN:
            return "shutdown_only"
        if activity is Activity.DRAG_PREVIEW:
            return "drop_only"
        return "normal"


class RuntimeContext:
    """Thread-safe producer queue; only the creating Tk thread may drain it."""

    def __init__(self, clock: TimeSource) -> None:
        self.clock = clock
        self.coordinator = ActivityCoordinator(clock)
        self._queue: SimpleQueue[RuntimeEvent] = SimpleQueue()
        self._owner_thread = get_ident()
        self._handlers: dict[str, list[Callable[[RuntimeEvent], None]]] = {}
        self._closed = False
        self.bind("health.set", lambda event: self.coordinator._set_health(Health(event.payload["health"])))
        self.bind("transaction.review", lambda _event: self.coordinator.request_activity(Activity.TRANSACTION_REVIEW))

    def bind(self, event_type: str, handler: Callable[[RuntimeEvent], None]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def post(self, event_type: str, *, source: str, correlation_id: str | None = None, **payload: Any) -> str:
        if self._closed:
            raise RuntimeError("runtime is closed")
        correlation = correlation_id or uuid4().hex
        self._queue.put(RuntimeEvent(event_type, source, self.clock.monotonic(), correlation, payload))
        return correlation

    def drain(self, limit: int = 128) -> int:
        if get_ident() != self._owner_thread:
            raise RuntimeError("runtime queue must be drained by its Tk owner thread")
        self.coordinator.expire_timeout()
        count = 0
        while count < limit and not self._queue.empty():
            event = self._queue.get_nowait()
            for handler in tuple(self._handlers.get(event.type, ())):
                handler(event)
            count += 1
        return count

    def snapshot(self) -> RuntimeSnapshot:
        return self.coordinator.snapshot()

    def set_health(self, health: Health, *, source: str) -> str:
        return self.post("health.set", source=source, health=health.value)

    def close(self) -> None:
        self._closed = True
        self.coordinator.request_activity(Activity.SHUTTING_DOWN)
        self.drain()


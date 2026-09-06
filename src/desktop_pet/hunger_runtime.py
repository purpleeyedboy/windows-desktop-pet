"""Runtime adapter from HungerService to the PR5 ActivityCoordinator contract."""
from __future__ import annotations
import time
from typing import Callable
from .hunger import HungerLevel, HungerService
from .hunger_animation import HungerAnimationController, HungerAnimationFrame

from .foundation_contract import ActivityCoordinatorPort


def enable_debug_time_simulation(*, test_build: bool, clock: object, seconds: int) -> None:
    if not test_build:
        raise RuntimeError("debug time simulation is disabled outside a test build")
    advance = getattr(clock, "advance", None)
    if not callable(advance):
        raise TypeError("debug simulation requires an offset UTC clock")
    advance(int(seconds))

class HungerRuntime:
    TICK_MS = 50
    def __init__(self, *, service: HungerService, activity: ActivityCoordinatorPort,
                 monotonic_clock: Callable[[], float] = time.monotonic,
                 schedule: Callable[[int, Callable[[], None]], object],
                 cancel: Callable[[object], None],
                 on_frame: Callable[[HungerAnimationFrame], None]) -> None:
        if activity is None:
            raise RuntimeError("PR5 ActivityCoordinator adapter is required")
        self.service, self.activity = service, activity
        self.schedule, self.cancel, self.on_frame = schedule, cancel, on_frame
        self.animation = HungerAnimationController(clock=monotonic_clock)
        self._token = None
        self._running = False
        self._last_health = self.service.snapshot().level
        self._state_version = 1
        self._activity_token: object | None = None
        self._activity_name: str | None = None
        self._active_animation_id = 0
        self.animation.update_health(self._last_health)

    def start(self) -> None:
        if self._running: return
        self._running = True
        self._tick()

    def _tick(self) -> None:
        if not self._running: return
        snapshot = self.service.snapshot()
        if snapshot.level is not self._last_health:
            if self._activity_token is not None:
                self.activity.cancel(self._activity_token, "FixedAnchor")
                self._activity_token = None
                self._activity_name = None
            self._state_version += 1
            self.animation.update_health(snapshot.level)
            self._last_health = snapshot.level
        published_version = self.activity.publish_health(snapshot.level, snapshot.units)
        self._state_version = max(self._state_version, int(published_version))
        frame = self.animation.frame()
        active = frame.mouth_open > 0.0
        if active and self._activity_token is None:
            self._activity_name = (
                "SevereHungerAnimation"
                if snapshot.level is HungerLevel.SEVERE_HUNGRY
                else "NormalHungerAnimation"
            )
            priority = self._activity_name
            self._activity_token = self.activity.begin(
                self._activity_name, priority, frame.animation_id, self._state_version
            )
            self._active_animation_id = frame.animation_id
        if active and self._activity_token is not None and self.activity.is_current(
            self._activity_name, self._active_animation_id,
            self._state_version, self._activity_token,
        ):
            self.on_frame(frame)
        elif not active:
            if self._activity_token is not None:
                if self.activity.is_current(
                    self._activity_name, self._active_animation_id,
                    self._state_version, self._activity_token,
                ):
                    self.activity.complete(
                        self._activity_name, self._active_animation_id,
                        self._state_version, self._activity_token,
                    )
                self._activity_token = None
                self._activity_name = None
            # Critical tears are orthogonal Health presentation, not a queued activity.
            self.on_frame(frame)
        self._token = self.schedule(self.TICK_MS, self._tick)

    def set_debug_units(self, units: int) -> None:
        snapshot = self.service.set_units(units)
        self.animation.update_health(snapshot.level)
        self._last_health = snapshot.level

    def replay(self) -> None: self.animation.replay()
    def interrupt(self) -> None:
        if self._activity_token is not None:
            self.activity.cancel(self._activity_token, "FixedAnchor")
            self._activity_token = None
            self._activity_name = None
        self.animation.cancel_for_interruption()
    def resume(self) -> None: self.animation.resume_after_interruption()
    def status_text(self) -> str:
        s = self.service.snapshot()
        return (f"Internal={s.units}; Display={s.display_percent}; Health={s.level.value}; Recovery={s.recovery}; Activity={self.activity.status_text()}; "
                f"StateVersion={self._state_version}; AnimationId={self._active_animation_id}; "
                f"AnchorUnits={s.anchor_units}; AnchorUtc={s.anchor_utc}; Next={self.animation.frame().next_animation_monotonic}")
    def stop(self) -> None:
        self._running = False
        if self._token is not None:
            try: self.cancel(self._token)
            except Exception: pass
            self._token = None
        self.service.close()

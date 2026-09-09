"""Hunger adapter over the single V2.1 RuntimeContext and coordinator."""
from __future__ import annotations

from typing import Callable

from .foundation.runtime import Activity, ActivityToken, Health, RuntimeContext
from .hunger import HungerLevel, HungerService
from .hunger_animation import HungerAnimationController, HungerAnimationFrame


def enable_debug_time_simulation(*, test_build: bool, clock: object, seconds: int) -> None:
    if not test_build:
        raise RuntimeError("debug time simulation is disabled outside a test build")
    advance = getattr(clock, "advance", None)
    if not callable(advance):
        raise TypeError("debug simulation requires an offset UTC clock")
    advance(int(seconds))


_HEALTH = {
    HungerLevel.NORMAL: Health.NORMAL,
    HungerLevel.HUNGRY: Health.HUNGRY,
    HungerLevel.SEVERE_HUNGRY: Health.SEVERE,
    HungerLevel.CRITICAL_HUNGRY: Health.CRITICAL,
}


class HungerRuntime:
    TICK_MS = 50

    def __init__(
        self,
        *,
        service: HungerService,
        runtime: RuntimeContext,
        schedule: Callable[[int, Callable[[], None]], object],
        cancel: Callable[[object], None],
        on_frame: Callable[[HungerAnimationFrame], None],
    ) -> None:
        self.service = service
        self.runtime = runtime
        self.activity = runtime.coordinator
        self.schedule = schedule
        self.cancel = cancel
        self.on_frame = on_frame
        self.animation = HungerAnimationController(clock=runtime.clock.monotonic)
        self._timer: object | None = None
        self._running = False
        self._last_health = self.service.snapshot().level
        self._activity_token: ActivityToken | None = None
        self._active_animation_id = "0"
        self.animation.update_health(self._last_health)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tick()

    def _publish_health(self, level: HungerLevel) -> None:
        expected = _HEALTH[level]
        if self.runtime.snapshot().health is expected:
            return
        self.runtime.set_health(expected, source="hunger")
        self.runtime.drain()

    def _tick(self) -> None:
        if not self._running:
            return
        snapshot = self.service.snapshot()
        if snapshot.level is not self._last_health:
            self.interrupt()
            self.animation.update_health(snapshot.level)
            self._last_health = snapshot.level
        self._publish_health(snapshot.level)
        frame = self.animation.frame()
        active = frame.mouth_open > 0.0
        animation_id = str(frame.animation_id)
        if active and self._activity_token is None:
            activity = (
                Activity.SEVERE_HUNGER_ANIMATION
                if snapshot.level is HungerLevel.SEVERE_HUNGRY
                else Activity.NORMAL_HUNGER_ANIMATION
            )
            self._activity_token = self.activity.request_activity(
                activity,
                animation_id=animation_id,
                timeout_seconds=2.0,
            )
            self._active_animation_id = animation_id
            if self._activity_token is None:
                self.animation.cancel_for_interruption()
                frame = self.animation.frame()
                active = False
            else:
                self.activity.attach_recovery(
                    self._activity_token,
                    self._recover_animation,
                )
        if active and self._activity_token == self.activity.current_token:
            self.on_frame(frame)
        elif not active:
            if self._activity_token is not None:
                self.activity.complete(
                    self._activity_token,
                    animation_id=self._active_animation_id,
                )
                self._activity_token = None
            # Critical tears are orthogonal health presentation, not an activity.
            self.on_frame(frame)
        self._timer = self.schedule(self.TICK_MS, self._tick)

    def set_debug_units(self, units: int) -> None:
        snapshot = self.service.set_units(units)
        self.interrupt()
        self.animation.update_health(snapshot.level)
        self._last_health = snapshot.level
        self._publish_health(snapshot.level)

    def replay(self) -> None:
        self.animation.replay()

    def interrupt(self) -> None:
        if self._activity_token is not None:
            self.activity.cancel_and_recover(self._activity_token)
            self._activity_token = None
        self.animation.cancel_for_interruption()

    def _recover_animation(self) -> None:
        """Return the physical hunger layer to a fixed neutral frame."""
        self._activity_token = None
        self.animation.cancel_for_interruption()
        self.on_frame(self.animation.frame())

    def resume(self) -> None:
        self.animation.resume_after_interruption()

    def status_text(self) -> str:
        snapshot = self.service.snapshot()
        runtime = self.runtime.snapshot()
        return (
            f"Internal={snapshot.units}; Display={snapshot.display_percent}; "
            f"Health={runtime.health.value}; Activity={runtime.activity.value}; "
            f"Recovery={snapshot.recovery}; StateVersion={runtime.activity_version}; "
            f"AnimationId={self._active_animation_id}; "
            f"AnchorUnits={snapshot.anchor_units}; AnchorUtc={snapshot.anchor_utc}; "
            f"Next={self.animation.frame().next_animation_monotonic}"
        )

    def stop(self) -> None:
        self._running = False
        if self._timer is not None:
            self.cancel(self._timer)
            self._timer = None
        self.interrupt()
        self.service.close()

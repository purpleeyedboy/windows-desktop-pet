"""UTC hunger ownership with real clips scheduled on the shared graphic player."""
from __future__ import annotations

from .foundation.runtime import Activity
from .foundation_contract import HEALTH
from .hunger import HungerLevel, HungerService
from .hunger_feedback import HungerFeedback


class HungerGraphicRuntime:
    TICK_MS = 40
    HUNGER_ACTIVITIES = {Activity.NORMAL_HUNGER_ANIMATION, Activity.SEVERE_HUNGER_ANIMATION}
    RANK = {HungerLevel.NORMAL: 0, HungerLevel.HUNGRY: 1, HungerLevel.SEVERE_HUNGRY: 2, HungerLevel.CRITICAL_HUNGRY: 3}

    def __init__(self, *, services, service: HungerService, window, clock) -> None:
        self.services, self.service, self.window, self.clock = services, service, window, clock
        self._timer = None
        self._running = False
        self._level = None
        self._next = None
        self._blocked = False
        self.feedback = HungerFeedback()
        self.feedback.update(service.snapshot().units)
        self._pending_mood = None

    def _interval(self, level):
        # Events are driven by value crossings, never elapsed-time spam.
        return None

    def _schedule_next(self, now) -> None:
        interval = self._interval(self._level)
        self._next = None if interval is None else now + interval

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._tick()

    def _tick(self) -> None:
        if not self._running:
            return
        runtime = self.services.runtime
        now = self.clock.monotonic()
        snapshot = self.service.snapshot()
        mood = self.feedback.update(snapshot.units)
        changed = snapshot.level is not self._level
        if changed:
            previous = self._level
            current = runtime.coordinator.current_token
            cancel_activities = set(self.HUNGER_ACTIVITIES)
            if snapshot.level is HungerLevel.CRITICAL_HUNGRY:
                cancel_activities.update({Activity.BODY_ACTION, Activity.GROOM, Activity.BLINK})
            if current is not None and current.activity in cancel_activities:
                runtime.coordinator.cancel_and_recover(current)
            self._level = snapshot.level
            runtime.set_health(HEALTH[self._level], source="hunger")
            runtime.drain()
            self._schedule_next(now)
            self._pending_mood = None
        if mood is not None:
            if mood in {'mild', 'severe'}:
                self._next = now
                self._pending_mood = mood
            else:
                self.window.show_hunger_feedback(mood)
        activity = runtime.snapshot().activity
        name, target = (
            ("hunger.hungry", Activity.NORMAL_HUNGER_ANIMATION)
            if snapshot.units >= 10000
            else ("hunger.severe", Activity.SEVERE_HUNGER_ANIMATION)
        )
        blocked = (
            activity not in {Activity.IDLE, *self.HUNGER_ACTIVITIES}
            and not runtime.coordinator.permits(target)
        )
        if blocked:
            self._blocked = True
        elif self._blocked:
            self._blocked = False
        if not blocked and self._next is not None and now >= self._next and runtime.coordinator.permits(target):
            self.window.request_graphic_clip(name, target)
            if self._pending_mood is not None:
                self.window.show_hunger_feedback(self._pending_mood)
                self._pending_mood = None
            self._schedule_next(now)
        self.window.refresh_hunger_presentation(snapshot)
        self._timer = self.window.root.after(self.TICK_MS, self._tick)

    def set_debug_units(self, units: int) -> None:
        self.service.set_units(units)

    def replay(self) -> None:
        if self._level in {HungerLevel.HUNGRY, HungerLevel.SEVERE_HUNGRY}:
            self._next = self.clock.monotonic()

    def status_text(self) -> str:
        snapshot = self.service.snapshot()
        state = self.services.runtime.snapshot()
        return f"Hunger={snapshot.units}; Display={snapshot.display_percent}; Health={snapshot.level.value}; Activity={state.activity.value}; Version={state.activity_version}; Recovery={snapshot.recovery}; Next={self._next}"

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._timer is not None:
            self.window._cancel_after(self._timer)
            self._timer = None
        self.service.close()

"""Monotonic V2.1 hunger mouth/tear animation scheduler."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from random import Random
from typing import Callable
from .hunger import HungerLevel

class HungerVisual(Enum):
    NONE = "none"
    MOUTH = "mouth"
    CRITICAL = "critical"
    SUSPENDED = "suspended"
    # compatibility names
    NORMAL_HUNGRY = "none"
    SEVERE_HUNGRY = "mouth"
    EXTREME_HUNGRY = "critical"

@dataclass(frozen=True)
class HungerAnimationFrame:
    health: HungerLevel
    visual: HungerVisual
    mouth_open: float
    tears_visible: bool
    tear_intensity: float
    phase_millis: int
    next_animation_monotonic: float | None
    animation_id: int

class HungerAnimationController:
    OPEN_SECONDS = .35
    HOLD_SECONDS = 1.0
    CLOSE_SECONDS = .35
    TOTAL_SECONDS = 1.70

    def __init__(self, *, clock: Callable[[], float], rng: Random | None = None) -> None:
        self._clock = clock
        self._rng = rng or Random()
        self._health = HungerLevel.NORMAL
        self._started: float | None = None
        self._next: float | None = None
        self._suspended = False
        self._animation_id = 0
        self._schedule_for(self._health)

    @staticmethod
    def _rank(level: HungerLevel) -> int:
        return {HungerLevel.NORMAL: 0, HungerLevel.HUNGRY: 1, HungerLevel.SEVERE_HUNGRY: 2, HungerLevel.CRITICAL_HUNGRY: 3}[level]

    def _interval(self, level: HungerLevel) -> float | None:
        if level is HungerLevel.HUNGRY:
            return self._rng.uniform(20.0, 40.0)
        if level is HungerLevel.SEVERE_HUNGRY:
            return self._rng.uniform(8.0, 15.0)
        return None

    def _schedule_for(self, level: HungerLevel) -> None:
        interval = self._interval(level)
        self._next = None if interval is None else self._clock() + interval

    def update_health(self, level: HungerLevel) -> None:
        previous = self._health
        self._health = level
        self._started = None
        self._suspended = False
        # Only downward entry into Hungry/Severe starts immediately. Crossing
        # several boundaries handles final state only. Upward transitions never play it.
        if self._rank(level) > self._rank(previous) and level in (HungerLevel.HUNGRY, HungerLevel.SEVERE_HUNGRY):
            self.replay()
        else:
            self._schedule_for(level)

    def replay(self) -> None:
        if self._health in (HungerLevel.HUNGRY, HungerLevel.SEVERE_HUNGRY):
            self._animation_id += 1
            self._started = self._clock()
            self._next = None

    def cancel_for_interruption(self) -> None:
        self._started = None
        self._suspended = True
        self._schedule_for(self._health)

    def resume_after_interruption(self) -> None:
        self._suspended = False
        self._started = None
        self._schedule_for(self._health)

    def frame(self) -> HungerAnimationFrame:
        now = self._clock()
        if self._suspended:
            return HungerAnimationFrame(self._health, HungerVisual.SUSPENDED, 0, False, 0, 0, self._next, self._animation_id)
        if self._started is None and self._next is not None and now >= self._next:
            self.replay()
        mouth = 0.0
        tears = self._health is HungerLevel.CRITICAL_HUNGRY
        intensity = 1.0 if tears else 0.0
        phase_ms = int(now * 1000) if tears else 0
        if self._started is not None:
            elapsed = max(0.0, now - self._started)
            phase_ms = int(elapsed * 1000)
            if elapsed < self.OPEN_SECONDS:
                mouth = elapsed / self.OPEN_SECONDS
            elif elapsed < self.OPEN_SECONDS + self.HOLD_SECONDS:
                mouth = 1.0
                if self._health is HungerLevel.SEVERE_HUNGRY:
                    tears, intensity = True, 1.0
            elif elapsed < self.TOTAL_SECONDS:
                mouth = 1.0 - (elapsed - self.OPEN_SECONDS - self.HOLD_SECONDS) / self.CLOSE_SECONDS
            else:
                self._started = None
                self._schedule_for(self._health)
                mouth = 0.0
        visual = HungerVisual.CRITICAL if self._health is HungerLevel.CRITICAL_HUNGRY else (HungerVisual.MOUTH if mouth > 0 or tears else HungerVisual.NONE)
        return HungerAnimationFrame(self._health, visual, max(0.0, min(1.0, mouth)), tears, intensity, phase_ms, self._next, self._animation_id)

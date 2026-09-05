"""Interruptible presentation state for hunger; contains no hunger value."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .hunger import HungerLevel


class HungerVisual(Enum):
    NORMAL_HUNGRY = "normal_hungry"
    SEVERE_HUNGRY = "severe_hungry"
    EXTREME_HUNGRY = "extreme_hungry"
    SUSPENDED = "suspended"


@dataclass(frozen=True)
class HungerAnimationFrame:
    visual: HungerVisual
    tears_visible: bool
    phase_millis: int
    cycle_millis: int


class HungerAnimationController:
    _CYCLES = {
        HungerLevel.NORMAL: 4_000,
        HungerLevel.SEVERE: 2_400,
        HungerLevel.EXTREME: 1_600,
    }

    def __init__(self, *, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._level = HungerLevel.NORMAL
        self._started = clock()
        self._suspended = False

    def _frame(self) -> HungerAnimationFrame:
        cycle = self._CYCLES[self._level]
        if self._suspended:
            return HungerAnimationFrame(HungerVisual.SUSPENDED, False, 0, cycle)
        visuals = {
            HungerLevel.NORMAL: HungerVisual.NORMAL_HUNGRY,
            HungerLevel.SEVERE: HungerVisual.SEVERE_HUNGRY,
            HungerLevel.EXTREME: HungerVisual.EXTREME_HUNGRY,
        }
        elapsed_ms = max(0, int((self._clock() - self._started) * 1_000))
        return HungerAnimationFrame(
            visuals[self._level],
            self._level is HungerLevel.EXTREME,
            elapsed_ms % cycle,
            cycle,
        )

    def update(self, level: HungerLevel) -> HungerAnimationFrame:
        if level is not self._level:
            self._level = level
            self._started = self._clock()
        return self._frame()

    def user_animation_started(self) -> None:
        self._suspended = True

    def user_animation_finished(self) -> HungerAnimationFrame:
        self._suspended = False
        self._started = self._clock()
        return self._frame()

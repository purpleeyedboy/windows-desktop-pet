"""Low-key spontaneous blink timing for the desktop cat."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Final


MIN_BLINK_INTERVAL_SECONDS: Final = 12.0
MAX_BLINK_INTERVAL_SECONDS: Final = 20.0
CLOSE_SECONDS: Final = 0.066
CLOSED_HOLD_SECONDS: Final = 0.033
OPEN_SECONDS: Final = 0.066
TOTAL_BLINK_SECONDS: Final = CLOSE_SECONDS + CLOSED_HOLD_SECONDS + OPEN_SECONDS


def _finite_time(value: object, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be finite") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


class NaturalBlinkMotion:
    """Generate infrequent, short complete blinks without owning a scheduler."""

    def __init__(
        self,
        uniform: Callable[[float, float], float] | None = None,
    ) -> None:
        self._uniform = uniform or random.SystemRandom().uniform
        self._next_blink_at: float | None = None

    @property
    def next_blink_at(self) -> float | None:
        return self._next_blink_at

    def reset(self, now: float) -> None:
        current = _finite_time(now, "blink clock")
        try:
            interval = float(
                self._uniform(
                    MIN_BLINK_INTERVAL_SECONDS,
                    MAX_BLINK_INTERVAL_SECONDS,
                )
            )
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("blink interval source returned an invalid value") from error
        if (
            not math.isfinite(interval)
            or interval < MIN_BLINK_INTERVAL_SECONDS
            or interval > MAX_BLINK_INTERVAL_SECONDS
        ):
            raise ValueError("blink interval is outside the supported range")
        self._next_blink_at = current + interval

    def trigger(self, now: float) -> None:
        """Start one ordinary blink and replace any pending cooldown."""

        self._next_blink_at = _finite_time(now, "blink clock")

    def sample(self, now: float) -> float:
        """Return eyelid closure in the inclusive range 0..1."""

        current = _finite_time(now, "blink clock")
        if self._next_blink_at is None:
            self.reset(current)
            return 0.0

        elapsed = current - self._next_blink_at
        if elapsed < 0.0:
            return 0.0
        if elapsed < CLOSE_SECONDS:
            return _smoothstep(elapsed / CLOSE_SECONDS)

        elapsed -= CLOSE_SECONDS
        if elapsed < CLOSED_HOLD_SECONDS:
            return 1.0

        elapsed -= CLOSED_HOLD_SECONDS
        if elapsed < OPEN_SECONDS:
            return 1.0 - _smoothstep(elapsed / OPEN_SECONDS)

        self.reset(current)
        return 0.0

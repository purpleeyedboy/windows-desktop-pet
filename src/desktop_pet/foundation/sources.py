from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import Random, SystemRandom
import time
from typing import Protocol


class TimeSource(Protocol):
    def utc_now(self) -> datetime: ...
    def monotonic(self) -> float: ...


class RandomSource(Protocol):
    fixed_seed: int | None
    def random(self) -> float: ...


class SystemTimeSource:
    def utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()


class FixedTimeSource:
    def __init__(self, utc_value: datetime, monotonic_value: float) -> None:
        if utc_value.tzinfo is None or utc_value.utcoffset() != timedelta(0):
            raise ValueError("utc_value must be timezone-aware UTC")
        self._utc_value = utc_value
        self._monotonic_value = float(monotonic_value)

    def utc_now(self) -> datetime:
        return self._utc_value

    def monotonic(self) -> float:
        return self._monotonic_value

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("time cannot move backwards")
        self._monotonic_value += seconds
        self._utc_value += timedelta(seconds=seconds)


class SeededRandomSource:
    def __init__(self, seed: int) -> None:
        self.fixed_seed = seed
        self._random = Random(seed)

    def random(self) -> float:
        return self._random.random()


class SystemRandomSource:
    fixed_seed = None

    def __init__(self) -> None:
        self._random = SystemRandom()

    def random(self) -> float:
        return self._random.random()

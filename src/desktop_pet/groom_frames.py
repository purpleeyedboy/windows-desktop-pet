"""Approved full-frame grooming playback on the shared runtime tick."""

from __future__ import annotations

from typing import Protocol, Sequence

from PIL import Image


FRAME_SECONDS = 0.075
EXPLICIT_IDLE_SECONDS = 60.0
WAIT_MIN_SECONDS = 90.0
WAIT_MAX_SECONDS = 300.0
RUNTIME_SIZE = (672, 768)


class GroomRandom(Protocol):
    def uniform(self, low: float, high: float) -> float: ...

    def randint(self, low: int, high: int) -> int: ...


class GroomFramePlayer:
    """Select approved frames without owning a timer, listener, or event queue."""

    def __init__(self, frames: Sequence[Image.Image], *, rng: GroomRandom) -> None:
        if len(frames) != 12:
            raise ValueError("groom animation requires exactly twelve frames")
        copied = tuple(frame.convert("RGBA") for frame in frames)
        if any(frame.size != RUNTIME_SIZE for frame in copied):
            raise ValueError("groom frames must use the 672x768 runtime canvas")
        if copied[0].tobytes() != copied[-1].tobytes():
            raise ValueError("groom first and last frames must be the same canonical idle")
        self._frames = copied
        self._rng = rng
        self._active = False
        self._started_at = 0.0
        self._sequence: tuple[int, ...] = ()
        self._last_interaction: float | None = None
        self._next_idle_at: float | None = None

    @property
    def active(self) -> bool:
        return self._active

    def sample(self, now: float) -> Image.Image | None:
        current = float(now)
        if self._last_interaction is None:
            self._restart_idle(current)
        if not self._active:
            if self._next_idle_at is None or current + 1e-9 < self._next_idle_at:
                return None
            count = self._validated_count()
            self._begin(current, count)
        index = int(max(0.0, current - self._started_at) / FRAME_SECONDS + 1e-9)
        if index >= len(self._sequence):
            self._active = False
            self._restart_idle(current)
            return None
        return self._frames[self._sequence[index]]

    def trigger(self, now: float, *, repetitions: int) -> bool:
        if self._active or not 3 <= repetitions <= 20:
            return False
        self._begin(float(now), repetitions)
        return True

    def interrupt(self, now: float) -> Image.Image | None:
        was_active = self._active
        self._active = False
        self._sequence = ()
        self._restart_idle(float(now))
        return self._frames[-1] if was_active else None

    def _begin(self, now: float, repetitions: int) -> None:
        self._sequence = (
            (0, 1, 2)
            + (3, 4, 5, 6, 7, 8) * repetitions
            + (9, 10, 11)
        )
        self._started_at = now
        self._active = True

    def _restart_idle(self, now: float) -> None:
        wait = float(self._rng.uniform(WAIT_MIN_SECONDS, WAIT_MAX_SECONDS))
        if not WAIT_MIN_SECONDS <= wait <= WAIT_MAX_SECONDS:
            raise ValueError("groom idle wait is outside 90..300 seconds")
        self._last_interaction = now
        self._next_idle_at = now + EXPLICIT_IDLE_SECONDS + wait

    def _validated_count(self) -> int:
        count = self._rng.randint(3, 20)
        if isinstance(count, bool) or not isinstance(count, int) or not 3 <= count <= 20:
            raise ValueError("groom repetition count is outside 3..20")
        return count

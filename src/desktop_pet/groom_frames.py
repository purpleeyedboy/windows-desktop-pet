"""Approved full-frame grooming playback on the shared runtime tick."""

from __future__ import annotations

import hashlib

from typing import Mapping, Protocol, Sequence

from PIL import Image


FRAME_SECONDS = 0.075
EXPLICIT_IDLE_SECONDS = 60.0
WAIT_MIN_SECONDS = 90.0
WAIT_MAX_SECONDS = 300.0
RUNTIME_SIZE = (640, 768)


class GroomRandom(Protocol):
    def uniform(self, low: float, high: float) -> float: ...

    def randint(self, low: int, high: int) -> int: ...

    def choice(self, values: tuple[str, ...]) -> str: ...


class GroomFramePlayer:
    """Select approved frames without owning a timer, listener, or event queue."""

    def __init__(self, frames: Sequence[Image.Image], *, rng: GroomRandom, other_sides: Mapping[str, Sequence[Image.Image]] | None = None) -> None:
        if len(frames) != 12:
            raise ValueError("groom animation requires exactly twelve frames")
        copied = tuple(frame.convert("RGBA") for frame in frames)
        if any(frame.size != RUNTIME_SIZE for frame in copied):
            raise ValueError("groom frames must use the 640x768 runtime canvas")
        if copied[0].tobytes() != copied[-1].tobytes():
            raise ValueError("groom first and last frames must be the same canonical idle")
        self._clips = {"left": copied}
        for side, supplied in (other_sides or {}).items():
            if side != "right" or len(supplied) != 12:
                raise ValueError("groom extra clip must be twelve separately authored right frames")
            alternate = tuple(frame.convert("RGBA") for frame in supplied)
            if any(frame.size != RUNTIME_SIZE for frame in alternate):
                raise ValueError("groom right frames must use the 640x768 runtime canvas")
            if any(frame.tobytes() != copied[0].tobytes() for frame in (alternate[0],alternate[-1])):
                raise ValueError("groom right endpoints must match the actual left neutral")
            self._clips[side] = alternate
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

    @property
    def available_sides(self) -> tuple[str, ...]:
        return tuple(self._clips)

    def clip_summaries(self) -> dict[str, dict[str, object]]:
        summaries = {}
        for side, frames in self._clips.items():
            digest = hashlib.sha256()
            for frame in frames:
                digest.update(frame.tobytes())
            summaries[side] = {"frame_count": len(frames), "canvas": list(RUNTIME_SIZE), "rgba_sha256": digest.hexdigest()}
        return summaries

    def choose_side(self) -> str:
        sides = self.available_sides
        side = sides[0] if len(sides) == 1 else self._rng.choice(sides)
        if side not in self._clips:
            raise ValueError("groom RNG selected an unavailable side")
        return side

    def sample(self, now: float) -> Image.Image | None:
        current = float(now)
        if not self._active:
            return None
        index = int(max(0.0, current - self._started_at) / FRAME_SECONDS + 1e-9)
        if index >= len(self._sequence):
            self._active = False
            self._restart_idle(current)
            return None
        return self._frames[self._sequence[index]]

    def idle_due(self, now: float) -> bool:
        if self._last_interaction is None:
            self._restart_idle(float(now))
        return not self._active and self._next_idle_at is not None and now + 1e-9 >= self._next_idle_at

    def choose_repetitions(self) -> int:
        return self._validated_count()

    def trigger(self, now: float, *, repetitions: int, side: str = "left") -> bool:
        if side not in self._clips or self._active or isinstance(repetitions, bool) or not isinstance(repetitions, int) or not 3 <= repetitions <= 20:
            return False
        self._frames = self._clips[side]
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

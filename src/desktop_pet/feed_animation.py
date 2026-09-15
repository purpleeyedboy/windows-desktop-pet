"""Exclusive full-frame playback for a successful FEED operation."""
from __future__ import annotations

from collections.abc import Callable, Sequence


FEED_POSE_SEQUENCE = (0, 1, 2, 3, 2, 1, 2, 4, 5)


class FeedAnimationPlayer:
    def __init__(
        self,
        frames: Sequence[object],
        schedule: Callable[[int, Callable[[], None]], object],
        cancel: Callable[[object], None],
        display: Callable[[object], None],
        restore_frame: Callable[[], object],
        interval_ms: int = 110,
    ) -> None:
        if len(frames) != 6:
            raise ValueError("feed animation requires exactly six frames")
        self._frames = tuple(frames)
        self._schedule = schedule
        self._cancel = cancel
        self._display = display
        self._restore_frame = restore_frame
        self._interval_ms = interval_ms
        self._position = 0
        self._token: object | None = None
        self._generation = 0
        self.busy = False

    def play(self) -> bool:
        if self.busy:
            return False
        self.busy = True
        self._generation += 1
        generation = self._generation
        self._position = 0
        try:
            self._present_next(generation)
        except Exception:
            self._finish(generation)
            raise
        return self.busy or self._position > len(FEED_POSE_SEQUENCE)

    def interrupt(self) -> bool:
        if not self.busy:
            return False
        generation = self._generation
        token = self._token
        self._token = None
        if token is not None:
            try:
                self._cancel(token)
            except Exception:
                pass
        self._finish(generation)
        return True

    def _present_next(self, generation: int) -> None:
        if not self.busy or generation != self._generation:
            return
        if self._position >= len(FEED_POSE_SEQUENCE):
            self._finish(generation)
            return
        frame_index = FEED_POSE_SEQUENCE[self._position]
        self._position += 1
        self._display(self._frames[frame_index])
        self._token = self._schedule(
            self._interval_ms, lambda: self._present_next(generation)
        )

    def _finish(self, generation: int) -> None:
        if generation != self._generation:
            return
        self._generation += 1
        self._token = None
        self.busy = False
        self._display(self._restore_frame())

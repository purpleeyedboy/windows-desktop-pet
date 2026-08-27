from collections.abc import Callable
from typing import Protocol


class Scheduler(Protocol):
    def __call__(self, delay_ms: int, callback: Callable[[], None]) -> object: ...


FrameCallback = Callable[[str, int], None]
FinishedCallback = Callable[[str], None]


class AnimationController:
    def __init__(
        self,
        frame_counts: dict[str, int],
        scheduler: Scheduler,
        frame_changed: FrameCallback,
        finished: FinishedCallback,
        interval_ms: int = 90,
    ) -> None:
        self._frame_counts = frame_counts
        self._schedule = scheduler
        self._frame_changed = frame_changed
        self._finished = finished
        self._interval_ms = interval_ms
        self._action: str | None = None
        self._index = 0

    @property
    def busy(self) -> bool:
        return self._action is not None

    def play(self, action: str) -> bool:
        if self.busy or self._frame_counts.get(action, 0) <= 0:
            return False
        self._action = action
        self._index = 1
        self._frame_changed(action, 0)
        self._schedule(self._interval_ms, self._advance)
        return True

    def _advance(self) -> None:
        if self._action is None:
            return
        if self._index < self._frame_counts[self._action]:
            self._frame_changed(self._action, self._index)
            self._index += 1
            self._schedule(self._interval_ms, self._advance)
            return
        action = self._action
        self._action = None
        self._finished(action)

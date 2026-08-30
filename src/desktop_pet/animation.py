from collections.abc import Callable, Mapping
from typing import Protocol


class Scheduler(Protocol):
    def __call__(self, delay_ms: int, callback: Callable[[], None]) -> object: ...


FrameCallback = Callable[[str, int], None]
FinishedCallback = Callable[[str], None]
CancelCallback = Callable[[object], None]


_SCHEDULING = object()


class _PlayOutcome:
    def __init__(self, generation: int) -> None:
        self.generation = generation
        self.completed = False
        self.phase = "in_flight"


class AnimationController:
    def __init__(
        self,
        frame_counts: Mapping[str, int],
        scheduler: Scheduler,
        frame_changed: FrameCallback,
        finished: FinishedCallback,
        interval_ms: int = 90,
        cancel: CancelCallback | None = None,
    ) -> None:
        self._frame_counts = dict(frame_counts)
        for action, count in self._frame_counts.items():
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise ValueError(
                    f"frame count for {action!r} must be a positive integer"
                )
        self._schedule = scheduler
        self._frame_changed = frame_changed
        self._finished = finished
        self._interval_ms = interval_ms
        self._cancel = cancel
        self._action: str | None = None
        self._index = 0
        self._generation = 0
        self._token: object | None = None
        self._slot: object | None = None
        self._stopped = False
        self._cleaning_up = False
        self._attempts: list[_PlayOutcome] = []

    @property
    def busy(self) -> bool:
        return self._action is not None

    def play(self, action: str) -> bool:
        if self._attempts:
            parent = self._attempts[-1]
            if not (
                parent.completed and parent.phase == "finished_handoff"
            ):
                return False
        if (
            self._stopped
            or self._cleaning_up
            or self.busy
            or self._frame_counts.get(action, 0) <= 0
        ):
            return False
        self._generation += 1
        generation = self._generation
        self._action = action
        self._index = 1
        outcome = _PlayOutcome(generation)
        self._attempts.append(outcome)
        try:
            try:
                outcome.phase = "frame"
                try:
                    self._frame_changed(action, 0)
                finally:
                    outcome.phase = "in_flight"
            except Exception:
                self._abort(generation)
                raise
            if self._is_current(generation, action):
                self._schedule_next(generation, outcome)
            accepted = self._is_current(generation, action) or outcome.completed
            if not accepted:
                self._abort_attempt_descendant(outcome)
            return accepted
        except Exception:
            self._abort_attempt_descendant(outcome)
            raise
        finally:
            outcome.phase = "resolved"
            if self._attempts and self._attempts[-1] is outcome:
                self._attempts.pop()
            else:
                self._attempts.remove(outcome)

    def cancel_current(self, expected: str) -> bool:
        if self._action is None or self._action != expected:
            return False
        self._generation += 1
        cancelled_generation = self._generation
        token = self._token
        self._token = None
        self._slot = None
        self._action = None
        self._index = 0
        if token is not None and token is not _SCHEDULING and self._cancel is not None:
            try:
                self._cancel(token)
            except Exception:
                return False
        return (
            not self._stopped
            and self._generation == cancelled_generation
            and self._action is None
        )

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._generation += 1
        token = self._token
        self._token = None
        self._slot = None
        self._action = None
        self._index = 0
        if token is not None and token is not _SCHEDULING and self._cancel is not None:
            try:
                self._cancel(token)
            except Exception:
                pass

    def _schedule_next(
        self, generation: int, outcome: _PlayOutcome
    ) -> None:
        action = self._action
        if action is None or not self._is_current(generation, action):
            return
        slot = object()
        fired = False

        def scheduled_callback() -> None:
            nonlocal fired
            fired = True
            self._advance(generation, slot, outcome)

        self._slot = slot
        self._token = _SCHEDULING
        previous_phase = outcome.phase
        outcome.phase = "scheduler"
        try:
            token = self._schedule(self._interval_ms, scheduled_callback)
        except Exception:
            self._abort(generation)
            raise
        finally:
            outcome.phase = previous_phase
        if self._is_current(generation, action) and self._slot is slot:
            self._token = token
        elif not fired:
            self._cancel_unowned_token(token)

    def _advance(
        self, generation: int, slot: object, outcome: _PlayOutcome
    ) -> None:
        action = self._action
        if (
            action is None
            or not self._is_current(generation, action)
            or self._slot is not slot
        ):
            return
        self._slot = None
        self._token = None
        try:
            frame_count = self._frame_counts[action]
        except Exception:
            self._abort(generation)
            raise
        if self._index < frame_count:
            index = self._index
            self._index += 1
            previous_phase = outcome.phase
            outcome.phase = "frame"
            try:
                self._frame_changed(action, index)
            except Exception:
                self._abort(generation)
                raise
            finally:
                outcome.phase = previous_phase
            if self._is_current(generation, action):
                self._schedule_next(generation, outcome)
            return
        self._action = None
        self._index = 0
        outcome.completed = True
        self._generation += 1
        handoff_generation = self._generation
        previous_phase = outcome.phase
        outcome.phase = "finished_handoff"
        try:
            self._finished(action)
        except Exception:
            self._abort_descendant_after(handoff_generation)
            raise
        finally:
            outcome.phase = previous_phase

    def _is_current(self, generation: int, action: str) -> bool:
        return (
            not self._stopped
            and self._generation == generation
            and self._action == action
        )

    def _abort(self, generation: int) -> None:
        if self._generation != generation:
            return
        was_cleaning_up = self._cleaning_up
        self._cleaning_up = True
        try:
            token = self._token
            self._generation += 1
            self._token = None
            self._slot = None
            self._action = None
            self._index = 0
            self._cancel_token(token)
        finally:
            self._cleaning_up = was_cleaning_up

    def _cancel_unowned_token(self, token: object) -> None:
        was_cleaning_up = self._cleaning_up
        self._cleaning_up = True
        try:
            self._cancel_token(token)
        finally:
            self._cleaning_up = was_cleaning_up

    def _cancel_token(self, token: object | None) -> None:
        if token is None or token is _SCHEDULING or self._cancel is None:
            return
        try:
            self._cancel(token)
        except Exception:
            pass

    def _abort_attempt_descendant(self, outcome: _PlayOutcome) -> None:
        self._abort_descendant_after(outcome.generation)

    def _abort_descendant_after(self, generation: int) -> None:
        if self._action is not None and self._generation > generation:
            self._abort(self._generation)

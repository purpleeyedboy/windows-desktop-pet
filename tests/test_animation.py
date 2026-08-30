from collections.abc import Callable

import pytest

from desktop_pet.animation import AnimationController
from desktop_pet.assets import load_frames, runtime_frame_root
from desktop_pet.model import ActionCycle


class FakeScheduler:
    def __init__(self) -> None:
        self.callbacks: list[tuple[str, Callable[[], None]]] = []
        self.delays: list[int] = []
        self.cancelled: list[str] = []

    def __call__(self, delay_ms: int, callback: Callable[[], None]) -> str:
        assert delay_ms > 0
        self.delays.append(delay_ms)
        token = f"after-{len(self.callbacks) + 1}"
        self.callbacks.append((token, callback))
        return token

    def cancel(self, token: object) -> None:
        self.cancelled.append(str(token))

    def run_next(self) -> None:
        while self.callbacks:
            token, callback = self.callbacks.pop(0)
            if token not in self.cancelled:
                callback()
                return
        raise AssertionError("no live callback")

    def run_all(self) -> None:
        while self.callbacks:
            token, callback = self.callbacks.pop(0)
            if token not in self.cancelled:
                callback()


def test_controller_rejects_overlap_and_finishes():
    scheduler = FakeScheduler()
    frames: list[tuple[str, int]] = []
    finished: list[str] = []
    controller = AnimationController(
        {"jump": 3},
        scheduler,
        lambda action, index: frames.append((action, index)),
        finished.append,
        interval_ms=1,
    )
    assert controller.play("jump") is True
    assert controller.play("jump") is False
    scheduler.run_all()
    assert frames == [("jump", 0), ("jump", 1), ("jump", 2)]
    assert finished == ["jump"]
    assert controller.busy is False


def test_controller_rejects_unknown_action():
    scheduler = FakeScheduler()
    controller = AnimationController({"jump": 3}, scheduler, lambda *_: None, lambda _: None)
    assert controller.play("shake") is False


def test_default_interval_matches_original_six_frame_timing():
    scheduler = FakeScheduler()
    controller = AnimationController(
        {"jump": 6}, scheduler, lambda *_: None, lambda _: None
    )

    controller.play("jump")

    assert scheduler.delays == [90]


def test_six_frames_keep_final_hold_before_finished() -> None:
    scheduler = FakeScheduler()
    events: list[object] = []
    controller = AnimationController(
        {"jump": 6},
        scheduler,
        lambda action, index: events.append((action, index)),
        lambda action: events.append(("finished", action)),
    )

    assert controller.play("jump") is True
    for expected_index in range(1, 6):
        assert scheduler.delays[-1] == 90
        scheduler.run_next()
        assert events[-1] == ("jump", expected_index)
    assert events == [("jump", index) for index in range(6)]

    assert scheduler.delays == [90] * 6
    scheduler.run_next()
    assert events[-1] == ("finished", "jump")
    assert controller.busy is False


def test_stop_cancels_live_token_is_terminal_and_stale_callback_is_inert() -> None:
    scheduler = FakeScheduler()
    events: list[object] = []
    controller = AnimationController(
        {"jump": 6},
        scheduler,
        lambda action, index: events.append((action, index)),
        lambda action: events.append(("finished", action)),
        cancel=scheduler.cancel,
    )
    assert controller.play("jump") is True
    token, stale_callback = scheduler.callbacks[0]

    controller.stop()
    stale_callback()

    assert scheduler.cancelled == [token]
    assert events == [("jump", 0)]
    assert controller.busy is False
    assert controller.play("jump") is False
    assert len(scheduler.callbacks) == 1


def test_old_generation_callback_cannot_touch_new_playback() -> None:
    scheduler = FakeScheduler()
    events: list[object] = []
    controller = AnimationController(
        {"jump": 1, "shake": 2},
        scheduler,
        lambda action, index: events.append((action, index)),
        lambda action: events.append(("finished", action)),
        cancel=scheduler.cancel,
    )
    controller.play("jump")
    _, stale_callback = scheduler.callbacks[0]
    scheduler.run_next()
    assert controller.play("shake") is True
    stale_callback()

    assert events == [
        ("jump", 0),
        ("finished", "jump"),
        ("shake", 0),
    ]
    assert controller.busy is True


def test_reentrant_stop_from_frame_callback_leaves_no_ownership_or_token() -> None:
    scheduler = FakeScheduler()
    holder: list[AnimationController] = []

    def frame_changed(_action: str, _index: int) -> None:
        holder[0].stop()

    controller = AnimationController(
        {"jump": 6}, scheduler, frame_changed, lambda _: None, cancel=scheduler.cancel
    )
    holder.append(controller)

    assert controller.play("jump") is False
    assert controller.busy is False
    assert scheduler.callbacks == []


def test_frame_exception_aborts_ownership_and_reraises() -> None:
    scheduler = FakeScheduler()

    def fail_frame(_action: str, _index: int) -> None:
        raise RuntimeError("frame failed")

    controller = AnimationController(
        {"jump": 6}, scheduler, fail_frame, lambda _: None, cancel=scheduler.cancel
    )

    with pytest.raises(RuntimeError, match="frame failed"):
        controller.play("jump")
    assert controller.busy is False
    assert scheduler.callbacks == []


def test_scheduler_exception_aborts_ownership_and_reraises() -> None:
    frames: list[int] = []

    def fail_schedule(_delay_ms: int, _callback: Callable[[], None]) -> object:
        raise RuntimeError("schedule failed")

    controller = AnimationController(
        {"jump": 6},
        fail_schedule,
        lambda _action, index: frames.append(index),
        lambda _: None,
    )

    with pytest.raises(RuntimeError, match="schedule failed"):
        controller.play("jump")
    assert controller.busy is False
    assert frames == [0]


def test_abort_cleanup_rejects_reentrant_play_and_clears_guard() -> None:
    scheduler = FakeScheduler()
    successor_results: list[bool] = []
    controller: AnimationController

    def cancel_then_start(token: object) -> None:
        scheduler.cancel(token)
        successor_results.append(controller.play("shake"))

    controller = AnimationController(
        {"jump": 2, "shake": 2},
        scheduler,
        lambda *_: None,
        lambda _: None,
        cancel=cancel_then_start,
    )
    controller.play("jump")

    controller._abort(controller._generation)

    assert successor_results == [False]
    assert controller.busy is False
    assert controller.play("shake") is True


@pytest.mark.parametrize("transition", ["stop", "cancel", "successor"])
def test_scheduler_post_return_cancels_unfired_token_after_owner_loss(
    transition: str,
) -> None:
    cancelled: list[object] = []
    cleanup_play_results: list[bool] = []
    nested: list[bool] = []
    calls = 0
    controller: AnimationController

    def cancel(token: object) -> None:
        cancelled.append(token)
        cleanup_play_results.append(controller.play("squash"))

    def schedule(_delay_ms: int, _callback: Callable[[], None]) -> object:
        nonlocal calls
        calls += 1
        token = f"token-{calls}"
        if calls == 1:
            if transition == "stop":
                controller.stop()
            else:
                assert controller.cancel_current("jump") is True
                if transition == "successor":
                    nested.append(controller.play("shake"))
        return token

    controller = AnimationController(
        {"jump": 2, "shake": 2, "squash": 2},
        schedule,
        lambda *_: None,
        lambda _: None,
        cancel=cancel,
    )

    assert controller.play("jump") is False

    assert cancelled == ["token-1"]
    assert cleanup_play_results == [False]
    if transition == "successor":
        assert nested == [False]
        assert controller.busy is False
    else:
        assert nested == []
        assert controller.busy is False


def test_frame_work_does_not_shorten_first_or_final_ninety_ms_hold() -> None:
    now_ms = 0
    pending: list[tuple[int, Callable[[], None]]] = []
    delays: list[int] = []
    frame_starts: list[int] = []
    frame_ends: list[int] = []
    finished_at: list[int] = []

    def schedule(delay_ms: int, callback: Callable[[], None]) -> object:
        delays.append(delay_ms)
        pending.append((now_ms + delay_ms, callback))
        return object()

    def frame_changed(_action: str, _index: int) -> None:
        nonlocal now_ms
        frame_starts.append(now_ms)
        now_ms += 17
        frame_ends.append(now_ms)

    controller = AnimationController(
        {"jump": 6},
        schedule,
        frame_changed,
        lambda _action: finished_at.append(now_ms),
    )

    assert controller.play("jump") is True
    while pending:
        due_ms, callback = pending.pop(0)
        now_ms = max(now_ms, due_ms)
        callback()

    assert frame_starts[1] - frame_ends[0] == 90
    assert finished_at[0] - frame_ends[5] == 90
    assert frame_starts == [0, 107, 214, 321, 428, 535]
    assert delays == [90] * 6


def test_synchronous_scheduler_callbacks_report_accepted_without_busy_leak() -> None:
    events: list[object] = []

    def run_immediately(_delay_ms: int, callback: Callable[[], None]) -> object:
        callback()
        return object()

    controller = AnimationController(
        {"jump": 3},
        run_immediately,
        lambda action, index: events.append((action, index)),
        lambda action: events.append(("finished", action)),
    )

    assert controller.play("jump") is True
    assert events == [
        ("jump", 0),
        ("jump", 1),
        ("jump", 2),
        ("finished", "jump"),
    ]
    assert controller.busy is False


def test_frame_zero_cancel_cannot_start_successor_during_outer_attempt() -> None:
    scheduler = FakeScheduler()
    successor_results: list[bool] = []
    controller: AnimationController

    def frame_changed(action: str, index: int) -> None:
        if action == "jump" and index == 0:
            assert controller.cancel_current(action) is True
            successor_results.append(controller.play("shake"))

    controller = AnimationController(
        {"jump": 2, "shake": 2},
        scheduler,
        frame_changed,
        lambda _: None,
        cancel=scheduler.cancel,
    )

    assert controller.play("jump") is False
    assert successor_results == [False]
    assert controller.busy is False
    assert controller.play("shake") is True


@pytest.mark.parametrize("raise_after_cancel", [False, True])
def test_sync_scheduled_frame_cancel_cannot_leave_successor(
    raise_after_cancel: bool,
) -> None:
    successor_results: list[bool] = []
    controller: AnimationController

    def synchronous_schedule(
        _delay_ms: int, callback: Callable[[], None]
    ) -> object:
        callback()
        return object()

    def frame_changed(action: str, index: int) -> None:
        if action == "jump" and index == 1:
            assert controller.cancel_current(action) is True
            successor_results.append(controller.play("shake"))
            if raise_after_cancel:
                raise RuntimeError("cancelled frame failed")

    controller = AnimationController(
        {"jump": 2, "shake": 2},
        synchronous_schedule,
        frame_changed,
        lambda _: None,
    )

    if raise_after_cancel:
        with pytest.raises(RuntimeError, match="cancelled frame failed"):
            controller.play("jump")
    else:
        assert controller.play("jump") is False

    assert successor_results == [False]
    assert controller.busy is False


def test_cancel_current_is_nonterminal_and_invalidates_stale_callback() -> None:
    scheduler = FakeScheduler()
    events: list[object] = []
    controller = AnimationController(
        {"jump": 2, "shake": 2},
        scheduler,
        lambda action, index: events.append((action, index)),
        lambda action: events.append(("finished", action)),
        cancel=scheduler.cancel,
    )
    controller.play("jump")
    token, stale_callback = scheduler.callbacks[0]

    assert controller.cancel_current("shake") is False
    assert controller.cancel_current("jump") is True
    assert scheduler.cancelled == [token]
    assert controller.busy is False
    assert controller.play("shake") is True
    stale_callback()

    assert events == [("jump", 0), ("shake", 0)]
    assert controller.busy is True


def test_cancel_current_reentrant_successor_makes_old_cancel_report_false() -> None:
    scheduler = FakeScheduler()
    frames: list[tuple[str, int]] = []
    successor_results: list[bool] = []
    controller: AnimationController

    def cancel_then_start(token: object) -> None:
        scheduler.cancel(token)
        successor_results.append(controller.play("shake"))

    controller = AnimationController(
        {"jump": 2, "shake": 2},
        scheduler,
        lambda action, index: frames.append((action, index)),
        lambda _: None,
        cancel=cancel_then_start,
    )
    controller.play("jump")

    assert controller.cancel_current("jump") is False

    assert successor_results == [True]
    assert frames == [("jump", 0), ("shake", 0)]
    assert controller.busy is True


def test_nested_fully_synchronous_plays_report_generation_local_acceptance() -> None:
    results: list[tuple[str, bool]] = []
    frames: list[tuple[str, int]] = []
    controller: AnimationController

    def synchronous_schedule(_delay_ms: int, callback: Callable[[], None]) -> object:
        callback()
        return object()

    def finished(action: str) -> None:
        if action == "jump":
            results.append(("shake", controller.play("shake")))

    controller = AnimationController(
        {"jump": 1, "shake": 1},
        synchronous_schedule,
        lambda action, index: frames.append((action, index)),
        finished,
    )

    outer_result = controller.play("jump")

    assert outer_result is True
    assert results == [("shake", True)]
    assert frames == [("jump", 0), ("shake", 0)]
    assert controller.busy is False


def test_frame_counts_are_snapshotted_before_reentrant_caller_mutation() -> None:
    scheduler = FakeScheduler()
    counts = {"jump": 3}
    frames: list[int] = []

    def frame_changed(_action: str, index: int) -> None:
        frames.append(index)
        counts.clear()

    controller = AnimationController(
        counts, scheduler, frame_changed, lambda _: None, cancel=scheduler.cancel
    )

    assert controller.play("jump") is True
    scheduler.run_all()

    assert frames == [0, 1, 2]
    assert controller.busy is False


@pytest.mark.parametrize("invalid_count", [0, -1, True, 1.5, "6"])
def test_frame_counts_require_positive_non_boolean_integers(invalid_count: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        AnimationController(
            {"jump": invalid_count},  # type: ignore[dict-item]
            lambda _delay, _callback: object(),
            lambda *_: None,
            lambda _: None,
        )


def test_count_access_exception_aborts_instead_of_stranding_busy() -> None:
    scheduler = FakeScheduler()
    controller = AnimationController(
        {"jump": 2}, scheduler, lambda *_: None, lambda _: None
    )
    controller.play("jump")
    controller._frame_counts.clear()

    with pytest.raises(KeyError):
        scheduler.run_next()

    assert controller.busy is False


def test_reentrant_scheduler_callback_keeps_only_nested_live_token() -> None:
    pending: list[tuple[object, Callable[[], None]]] = []
    cancelled: list[object] = []
    schedule_count = 0

    def schedule(_delay_ms: int, callback: Callable[[], None]) -> object:
        nonlocal schedule_count
        schedule_count += 1
        token = object()
        if schedule_count == 1:
            callback()
        else:
            pending.append((token, callback))
        return token

    controller = AnimationController(
        {"jump": 3}, schedule, lambda *_: None, lambda _: None, cancel=cancelled.append
    )

    assert controller.play("jump") is True
    assert controller.busy is True
    assert len(pending) == 1
    assert cancelled == []


def test_reentrant_stop_from_scheduled_frame_does_not_reschedule() -> None:
    scheduler = FakeScheduler()
    controller: AnimationController

    def frame_changed(_action: str, index: int) -> None:
        if index == 1:
            controller.stop()

    controller = AnimationController(
        {"jump": 3}, scheduler, frame_changed, lambda _: None, cancel=scheduler.cancel
    )
    controller.play("jump")

    scheduler.run_next()

    assert controller.busy is False
    assert controller.play("jump") is False
    assert scheduler.callbacks == []


def test_scheduled_frame_exception_invalidates_repeated_callback() -> None:
    scheduler = FakeScheduler()
    events: list[object] = []

    def frame_changed(action: str, index: int) -> None:
        events.append((action, index))
        if index == 1:
            raise RuntimeError("later frame failed")

    controller = AnimationController(
        {"jump": 3}, scheduler, frame_changed, lambda _: None, cancel=scheduler.cancel
    )
    controller.play("jump")
    _, callback = scheduler.callbacks[0]

    with pytest.raises(RuntimeError, match="later frame failed"):
        callback()
    callback()

    assert events == [("jump", 0), ("jump", 1)]
    assert controller.busy is False


def test_finished_exception_leaves_ownership_cleared() -> None:
    scheduler = FakeScheduler()

    def fail_finished(_action: str) -> None:
        raise RuntimeError("finished failed")

    controller = AnimationController(
        {"jump": 1}, scheduler, lambda *_: None, fail_finished
    )
    controller.play("jump")

    with pytest.raises(RuntimeError, match="finished failed"):
        scheduler.run_next()

    assert controller.busy is False


def test_finished_callback_runs_after_ownership_clear_and_can_start_next() -> None:
    scheduler = FakeScheduler()
    events: list[object] = []
    controller: AnimationController

    def finished(action: str) -> None:
        events.append(("finished", action, controller.busy))
        assert controller.play("shake") is True

    controller = AnimationController(
        {"jump": 1, "shake": 1},
        scheduler,
        lambda action, index: events.append((action, index)),
        finished,
        cancel=scheduler.cancel,
    )
    controller.play("jump")

    scheduler.run_next()

    assert events == [
        ("jump", 0),
        ("finished", "jump", False),
        ("shake", 0),
    ]
    assert controller.busy is True


def test_finished_handoff_then_raise_cancels_started_descendant() -> None:
    scheduler = FakeScheduler()
    successor_results: list[bool] = []
    controller: AnimationController

    def finished(action: str) -> None:
        if action == "jump":
            successor_results.append(controller.play("shake"))
            raise RuntimeError("finished handoff failed")

    controller = AnimationController(
        {"jump": 1, "shake": 2},
        scheduler,
        lambda *_: None,
        finished,
        cancel=scheduler.cancel,
    )
    controller.play("jump")

    with pytest.raises(RuntimeError, match="finished handoff failed"):
        scheduler.run_next()

    assert successor_results == [True]
    assert controller.busy is False
    assert len(scheduler.cancelled) == 1


def test_transactional_legacy_fallback_runs_three_physical_six_frame_actions() -> None:
    physical_frames = load_frames(runtime_frame_root())
    scheduler = FakeScheduler()
    cycle = ActionCycle()
    displayed: list[tuple[str, int, object]] = []
    finished: list[str] = []
    phrases: list[str] = []
    controller = AnimationController(
        {action: len(frames) for action, frames in physical_frames.items()},
        scheduler,
        lambda action, index: displayed.append(
            (action, index, physical_frames[action][index])
        ),
        finished.append,
        cancel=scheduler.cancel,
    )

    for expected in ("jump", "squash", "shake"):
        action = cycle.peek()
        assert action == expected
        assert controller.play(action) is True
        cycle.commit(action)
        phrases.append(f"phrase:{action}")
        scheduler.run_all()

    assert [action for action, _, _ in displayed] == [
        action for action in ("jump", "squash", "shake") for _ in range(6)
    ]
    assert [index for _, index, _ in displayed] == list(range(6)) * 3
    assert all(frame is physical_frames[action][index] for action, index, frame in displayed)
    assert phrases == ["phrase:jump", "phrase:squash", "phrase:shake"]
    assert finished == ["jump", "squash", "shake"]
    assert scheduler.delays == [90] * 18

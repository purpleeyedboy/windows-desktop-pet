from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from desktop_pet.assets import load_frames, runtime_frame_root
from desktop_pet.blink import (
    CLOSE_SECONDS,
    MIN_BLINK_INTERVAL_SECONDS,
    TOTAL_BLINK_SECONDS,
    NaturalBlinkMotion,
)
from desktop_pet.eye_follow import CursorPoint
from desktop_pet.model import ACTIONS, ActionCycle, Rect


def _module():
    from desktop_pet import eye_runtime

    return eye_runtime


class Clock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


@dataclass
class Scheduled:
    delay_ms: int
    token: object
    callback: object


class ManualScheduler:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.pending: list[Scheduled] = []
        self.cancelled: list[object] = []
        self.delays: list[int] = []

    def __call__(self, delay_ms: int, callback):
        assert isinstance(delay_ms, int)
        assert delay_ms >= 0
        token = object()
        self.delays.append(delay_ms)
        self.pending.append(Scheduled(delay_ms, token, callback))
        return token

    def cancel(self, token: object) -> None:
        self.cancelled.append(token)

    def live(self) -> list[Scheduled]:
        return [entry for entry in self.pending if entry.token not in self.cancelled]

    def run_next(self, *, advance_ms: int | None = None) -> None:
        while self.pending:
            entry = self.pending.pop(0)
            if entry.token in self.cancelled:
                continue
            elapsed_ms = entry.delay_ms if advance_ms is None else advance_ms
            self.clock.value += elapsed_ms / 1000.0
            entry.callback()
            return
        raise AssertionError("no live callback")


class ControlledScheduler(ManualScheduler):
    def __init__(self, clock: Clock) -> None:
        super().__init__(clock)
        self.mode = "normal"
        self.calls = 0

    def __call__(self, delay_ms: int, callback):
        self.calls += 1
        mode, self.mode = self.mode, "normal"
        if mode == "raise_before_queue":
            raise RuntimeError("scheduler failed before queue")
        token = object()
        entry = Scheduled(delay_ms, token, callback)
        if mode == "synchronous":
            callback()
        else:
            self.delays.append(delay_ms)
            self.pending.append(entry)
        if mode == "raise_after_queue":
            raise RuntimeError("scheduler failed after queue")
        return token


class ControlledCancel:
    def __init__(self, scheduler: ManualScheduler) -> None:
        self.scheduler = scheduler
        self.callback = None
        self.raise_error = False

    def __call__(self, token: object) -> None:
        self.scheduler.cancel(token)
        if self.callback is not None:
            self.callback()
        if self.raise_error:
            raise RuntimeError("cancel failed")


@dataclass
class Cursor:
    point: object

    def position(self):
        return self.point


class Compositor:
    source_size = (512, 768)
    eye_midpoint = (122.5, 349.0)

    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []
        self.fail_next = False
        self.on_compose = None

    def compose(self, eye_x: float, eye_y: float):
        self.calls.append((eye_x, eye_y))
        if self.on_compose is not None:
            self.on_compose()
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("compose failed")
        return ("frame", eye_x, eye_y)


class BlinkCompositor(Compositor):
    def __init__(self) -> None:
        super().__init__()
        self.blink_calls: list[tuple[float, float, float]] = []

    def compose_blink(self, eye_x: float, eye_y: float, closure: float):
        self.blink_calls.append((eye_x, eye_y, closure))
        return ("blink-frame", eye_x, eye_y, closure)


class HeadCompositor(Compositor):
    def __init__(self) -> None:
        super().__init__()
        self.head_calls: list[tuple[float, float, float, float]] = []

    def compose_head(self, eye_x: float, eye_y: float, head_pose):
        call = (eye_x, eye_y, head_pose.x, head_pose.y)
        self.head_calls.append(call)
        if self.on_compose is not None:
            self.on_compose()
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("compose failed")
        return ("head-frame", *call)


class Display:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.fail_next = False
        self.on_display = None

    def __call__(self, frame: object) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("display failed")
        self.calls.append(frame)
        if self.on_display is not None:
            self.on_display()


def make_session(
    *,
    cursor: object = CursorPoint(200, 100),
    rect: Rect = Rect(0, 0, 512, 768),
    scheduler: object | None = None,
    cancel=None,
    clock: Clock | None = None,
    idle_lick_motion=None,
):
    module = _module()
    clock = clock or Clock()
    scheduler = scheduler or ManualScheduler(clock)
    compositor = Compositor()
    display = Display()
    disabled: list[str] = []
    rect_holder = [rect]
    session = module.RuntimeEyeSession(
        compositor=compositor,
        cursor_provider=Cursor(cursor),
        rect_provider=lambda: rect_holder[0],
        display=display,
        scheduler=scheduler,
        cancel=cancel or scheduler.cancel,
        clock=clock,
        on_disabled=lambda: disabled.append("disabled"),
        action_cycle=ActionCycle(),
        physical_frames={
            action: tuple(object() for _ in range(6)) for action in ACTIONS
        },
        play_action=lambda _action: True,
        cancel_action=lambda _action: True,
        choose_phrase=lambda action: f"phrase:{action}",
        present_phrase=lambda _phrase: None,
        on_action_failed=lambda _action, _failure: None,
        idle_lick_motion=idle_lick_motion,
    )
    return (
        session,
        clock,
        scheduler,
        compositor,
        display,
        disabled,
        rect_holder,
    )


def test_existing_environment_tick_samples_idle_lick_without_extra_scheduler(monkeypatch) -> None:
    from desktop_pet.idle_lick import LickPose

    class RecordingLick:
        def __init__(self) -> None:
            self.samples = []

        def sample(self, now, target, *, eligible=True):
            self.samples.append((now, target, eligible))
            return LickPose("left", "raise", 1.0, 0.0)

        def interrupt(self, _now):
            return LickPose()

    lick = RecordingLick()
    monkeypatch.setattr(_module(), "compose_lick", lambda frame, _pose: frame)
    session, _, scheduler, _, _, _, _ = make_session(idle_lick_motion=lick)
    session.start()

    scheduler.run_next()

    assert len(lick.samples) == 1
    assert session.idle_lick_pose.side == "left"
    assert len(scheduler.live()) == 1


def test_higher_priority_action_interrupts_idle_lick_before_ownership_change() -> None:
    from desktop_pet.idle_lick import LickPose

    class RecordingLick:
        def __init__(self) -> None:
            self.interruptions = 0

        def sample(self, _now, _target, *, eligible=True):
            return LickPose("right", "contact", 1.0, 1.0)

        def interrupt(self, _now):
            self.interruptions += 1
            return LickPose()

        cancel = interrupt

    lick = RecordingLick()
    session, _, _, _, _, _, _ = make_session(idle_lick_motion=lick)
    session.start()

    assert session.request_named_action("jump") is _module().SessionResult.ACCEPTED
    assert lick.interruptions == 1
    assert session.idle_lick_pose == LickPose()


def test_stop_restores_idle_lick_pose_to_neutral_even_if_cleanup_raises(monkeypatch) -> None:
    from desktop_pet.idle_lick import LickPose

    class FailingCleanupLick:
        def sample(self, _now, _target, *, eligible=True):
            return LickPose("left", "contact", 1.0, 1.0)

        def interrupt(self, _now):
            raise RuntimeError("injected cleanup failure")

    session, _, scheduler, _, _, _, _ = make_session(
        idle_lick_motion=FailingCleanupLick()
    )
    monkeypatch.setattr(_module(), "compose_lick", lambda frame, _pose: frame)
    session.start()
    scheduler.run_next()
    assert session.idle_lick_pose.side == "left"

    session.stop()

    assert session.idle_lick_pose == LickPose()


def test_runtime_display_pixels_change_for_each_visible_lick_channel_and_side() -> None:
    from PIL import Image
    from desktop_pet.idle_lick import LickPose

    class ImageCompositor(Compositor):
        def compose(self, eye_x, eye_y):
            del eye_x, eye_y
            return Image.new("RGBA", (512, 768), (80, 60, 40, 255))

    class SequencedLick:
        def __init__(self):
            self.poses = iter(
                (
                    LickPose("left", "raise", 1.0, 0.0),
                    LickPose("left", "contact", 1.0, 1.0),
                    LickPose("right", "contact", 1.0, 1.0),
                )
            )

        def sample(self, _now, _target, *, eligible=True):
            return next(self.poses)

        def interrupt(self, _now):
            return LickPose()

    clock = Clock()
    scheduler = ManualScheduler(clock)
    display = Display()
    session = _module().RuntimeEyeSession(
        compositor=ImageCompositor(), cursor_provider=Cursor(CursorPoint(200, 100)),
        rect_provider=lambda: Rect(0, 0, 512, 768), display=display,
        scheduler=scheduler, cancel=scheduler.cancel, clock=clock,
        on_disabled=lambda: None, action_cycle=ActionCycle(),
        physical_frames={action: tuple(object() for _ in range(6)) for action in ACTIONS},
        play_action=lambda _action: True, cancel_action=lambda _action: True,
        choose_phrase=lambda action: action, present_phrase=lambda _phrase: None,
        on_action_failed=lambda _action, _failure: None,
        idle_lick_motion=SequencedLick(),
    )
    session.start()
    rendered = []
    for _ in range(3):
        scheduler.run_next()
        rendered.append(display.calls[-1])

    raise_frame, tongue_frame, right_frame = rendered
    assert raise_frame.tobytes() != tongue_frame.tobytes()
    assert tongue_frame.tobytes() != right_frame.tobytes()


def test_lick_composition_exception_cancels_pose_to_neutral(monkeypatch) -> None:
    from desktop_pet.idle_lick import LickPose

    class ActiveLick:
        def __init__(self):
            self.cancelled = 0

        def sample(self, _now, _target, *, eligible=True):
            return LickPose("left", "contact", 1.0, 1.0)

        def interrupt(self, _now):
            return LickPose()

        def cancel(self, _now):
            self.cancelled += 1
            return LickPose()

    lick = ActiveLick()
    session, _, scheduler, _, _, _, _ = make_session(idle_lick_motion=lick)
    session.start()
    monkeypatch.setattr(
        _module(), "compose_lick", lambda *_args: (_ for _ in ()).throw(RuntimeError("injected"))
    )

    scheduler.run_next()

    assert lick.cancelled == 1
    assert session.idle_lick_pose == LickPose()


def make_action_session(
    *,
    cursor: object = CursorPoint(200, 100),
    cycle: ActionCycle | None = None,
    physical_frames: dict[str, object] | None = None,
    play_action=None,
    cancel_action=None,
    choose_phrase=None,
    present_phrase=None,
    on_action_failed=None,
    scheduler: object | None = None,
    cancel=None,
    clock: Clock | None = None,
):
    module = _module()
    clock = clock or Clock()
    scheduler = scheduler or ManualScheduler(clock)
    compositor = Compositor()
    display = Display()
    disabled: list[str] = []
    selected: list[str] = []
    presented: list[str] = []
    play_calls: list[str] = []
    action_cycle = cycle or ActionCycle()
    frames = physical_frames or {
        action: tuple(object() for _ in range(6)) for action in ACTIONS
    }

    def default_play(action: str) -> bool:
        play_calls.append(action)
        return True

    def default_choose(action: str) -> str:
        selected.append(action)
        return f"phrase:{action}"

    def default_present(phrase: str) -> None:
        presented.append(phrase)

    session = module.RuntimeEyeSession(
        compositor=compositor,
        cursor_provider=Cursor(cursor),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=display,
        scheduler=scheduler,
        cancel=cancel or scheduler.cancel,
        clock=clock,
        on_disabled=lambda: disabled.append("disabled"),
        action_cycle=action_cycle,
        physical_frames=frames,
        play_action=play_action or default_play,
        cancel_action=cancel_action or (lambda _action: True),
        choose_phrase=choose_phrase or default_choose,
        present_phrase=present_phrase or default_present,
        on_action_failed=on_action_failed or (lambda _action, _failure: None),
    )
    return (
        session,
        clock,
        scheduler,
        compositor,
        display,
        disabled,
        action_cycle,
        play_calls,
        selected,
        presented,
    )


def make_head_session(*, cursor: object = CursorPoint(397, 349)):
    module = _module()
    clock = Clock()
    scheduler = ManualScheduler(clock)
    compositor = HeadCompositor()
    display = Display()
    disabled: list[str] = []
    session = module.RuntimeEyeSession(
        compositor=compositor,
        cursor_provider=Cursor(cursor),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=display,
        scheduler=scheduler,
        cancel=scheduler.cancel,
        clock=clock,
        on_disabled=lambda: disabled.append("disabled"),
        action_cycle=ActionCycle(),
        physical_frames={
            action: tuple(object() for _ in range(6)) for action in ACTIONS
        },
        play_action=lambda _action: True,
        cancel_action=lambda _action: True,
        choose_phrase=lambda action: f"phrase:{action}",
        present_phrase=lambda _phrase: None,
        on_action_failed=lambda _action, _failure: None,
        head_follow=True,
    )
    return session, clock, scheduler, compositor, display, disabled


def move_once(session, scheduler: ManualScheduler) -> tuple[float, float]:
    assert session.start() is _module().SessionResult.ACCEPTED
    scheduler.run_next()
    assert session.last_displayed_pose is not None
    return session.last_displayed_pose


def test_start_displays_exact_center_then_starts_exactly_one_eye_tick() -> None:
    session, _, scheduler, compositor, display, disabled, _ = make_session()

    result = session.start()

    assert result is _module().SessionResult.ACCEPTED
    assert session.state == "following"
    assert compositor.calls == [(0.0, 0.0)]
    assert display.calls == [("frame", 0.0, 0.0)]
    assert session.last_displayed_pose == (0.0, 0.0)
    assert [entry.delay_ms for entry in scheduler.live()] == [33]
    assert disabled == []


def test_head_follow_session_composes_continuous_eye_and_head_pose_once_per_tick() -> None:
    session, _, scheduler, compositor, display, disabled = make_head_session()

    assert session.start() is _module().SessionResult.ACCEPTED
    scheduler.run_next()

    focus = 1.0 - math.exp(-0.033 / 0.060)
    head = 1.0 - math.exp(-0.033 / 0.220)
    expected = (
        3.0 * (focus - 0.35 * head),
        0.0,
        head * 1.225,
        0.0,
    )
    assert compositor.head_calls[0] == (0.0, 0.0, 0.0, 0.0)
    assert compositor.head_calls[-1] == pytest.approx(expected)
    assert session.last_displayed_pose == pytest.approx(expected[:2])
    assert session.last_displayed_head_pose == pytest.approx(expected[2:])
    assert display.calls[-1][0] == "head-frame"
    assert display.calls[-1][1:] == pytest.approx(expected)
    assert disabled == []


def test_head_follow_recenter_interpolates_both_channels_to_exact_center() -> None:
    session, _, scheduler, compositor, _, _ = make_head_session()
    session.start()
    scheduler.run_next()
    start = compositor.head_calls[-1]
    completed: list[str] = []

    assert session.pause_and_recenter(lambda: completed.append("done")) is (
        _module().SessionResult.ACCEPTED
    )
    for _ in range(4):
        scheduler.run_next()

    recentered = compositor.head_calls[-4:]
    for index, remaining in enumerate((0.75, 0.5, 0.25, 0.0)):
        assert recentered[index] == pytest.approx(
            tuple(value * remaining for value in start)
        )
    assert session.last_displayed_pose == (0.0, 0.0)
    assert session.last_displayed_head_pose == (0.0, 0.0)
    assert completed == ["done"]


def test_head_follow_composition_failure_skips_one_frame_then_recovers() -> None:
    session, _, scheduler, compositor, _, disabled = make_head_session()
    session.start()
    compositor.fail_next = True

    scheduler.run_next()

    assert session.state == "following"
    assert disabled == []
    assert len(scheduler.live()) == 1

    scheduler.run_next()

    assert session.state == "following"
    assert session.last_displayed_head_pose != (0.0, 0.0)
    assert disabled == []
    assert len(scheduler.live()) == 1


@pytest.mark.parametrize(
    "mode", ["synchronous", "raise_before_queue", "raise_after_queue"]
)
def test_initial_scheduler_hazard_disables_without_stale_owner_or_exception(
    mode: str,
) -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    scheduler.mode = mode
    session, _, _, compositor, _, disabled, _ = make_session(
        scheduler=scheduler,
        clock=clock,
    )

    result = session.start()
    stale_callbacks = [entry.callback for entry in scheduler.pending]
    scheduler.pending.clear()
    compose_count = len(compositor.calls)
    for callback in stale_callbacks:
        callback()

    assert result is _module().SessionResult.FALLBACK
    assert session.state == "disabled"
    assert disabled == ["disabled"]
    assert len(compositor.calls) == compose_count
    assert scheduler.live() == []


@pytest.mark.parametrize("failure_site", ["compose", "display"])
def test_initial_failure_disables_once_and_starts_no_timer(failure_site: str) -> None:
    session, _, scheduler, compositor, display, disabled, _ = make_session()
    if failure_site == "compose":
        compositor.fail_next = True
    else:
        display.fail_next = True

    result = session.start()

    assert result is _module().SessionResult.FALLBACK
    assert session.state == "disabled"
    assert session.last_displayed_pose is None
    assert scheduler.live() == []
    assert disabled == ["disabled"]
    assert session.start() is _module().SessionResult.FALLBACK
    assert disabled == ["disabled"]


@pytest.mark.parametrize(
    "rect",
    [
        Rect(80, 40, 512, 768),
        Rect(80, 40, 256, 384),
        Rect(-400, -250, 1024, 1536),
    ],
)
def test_live_geometry_maps_drag_resize_and_negative_coordinates(rect: Rect) -> None:
    midpoint_x = rect.x + 122.5 * rect.width / 512
    midpoint_y = rect.y + 349.0 * rect.height / 768
    activation_radius = rect.height / 280.0 * 100.0
    cursor = CursorPoint(midpoint_x + activation_radius, midpoint_y)
    session, _, scheduler, compositor, _, _, _ = make_session(
        cursor=cursor, rect=rect
    )

    move_once(session, scheduler)

    alpha = 1.0 - math.exp(-0.033 / 0.060)
    assert compositor.calls[-1] == pytest.approx((3.0 * alpha, 0.0))


def test_geometry_is_authoritative_on_every_following_tick() -> None:
    session, clock, scheduler, compositor, _, _, rect_holder = make_session(
        cursor=CursorPoint(300, 300), rect=Rect(0, 0, 512, 768)
    )
    session.start()
    scheduler.run_next()
    first_pose = compositor.calls[-1]
    rect_holder[0] = Rect(200, 100, 256, 384)

    scheduler.run_next()

    assert clock.value == pytest.approx(0.066)
    assert compositor.calls[-1] != pytest.approx(first_pose)


def test_recenter_interpolates_at_33_66_99_and_132ms_then_completes() -> None:
    session, _, scheduler, compositor, _, _, _ = make_session()
    starting_pose = move_once(session, scheduler)
    completed: list[str] = []
    marker = len(scheduler.delays)

    result = session.pause_and_recenter(lambda: completed.append("done"))
    for _ in range(4):
        assert len(scheduler.live()) == 1
        scheduler.run_next()

    recentered = compositor.calls[-4:]
    assert result is _module().SessionResult.ACCEPTED
    assert [pose[0] for pose in recentered] == pytest.approx(
        [starting_pose[0] * 0.75, starting_pose[0] * 0.5, starting_pose[0] * 0.25, 0.0]
    )
    assert [pose[1] for pose in recentered] == pytest.approx(
        [starting_pose[1] * 0.75, starting_pose[1] * 0.5, starting_pose[1] * 0.25, 0.0]
    )
    assert recentered[-1] == (0.0, 0.0)
    assert scheduler.delays[marker:] == [33, 33, 33, 33]
    assert session.last_displayed_pose == (0.0, 0.0)
    assert session.state == "playing"
    assert completed == ["done"]
    assert scheduler.live() == []


@pytest.mark.parametrize(
    "mode", ["synchronous", "raise_before_queue", "raise_after_queue"]
)
def test_recenter_scheduler_hazard_disables_without_orphan_or_action_owner(
    mode: str,
) -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    session, _, _, compositor, _, disabled, cycle, play_calls, selected, presented = (
        make_action_session(scheduler=scheduler, clock=clock)
    )
    move_once(session, scheduler)
    scheduler.mode = mode

    result = session.request_action()
    stale_callbacks = [entry.callback for entry in scheduler.pending]
    scheduler.pending.clear()
    compose_count = len(compositor.calls)
    for callback in stale_callbacks:
        callback()

    assert result is _module().SessionResult.FALLBACK
    assert session.state == "disabled"
    assert disabled == ["disabled"]
    assert cycle.peek() == "jump"
    assert play_calls == selected == presented == []
    assert len(compositor.calls) == compose_count
    assert scheduler.live() == []


def test_first_recenter_callback_after_duration_displays_center_without_overshoot() -> None:
    session, _, scheduler, compositor, _, _, _ = make_session()
    move_once(session, scheduler)
    completed: list[str] = []
    session.pause_and_recenter(lambda: completed.append("done"))

    scheduler.run_next(advance_ms=150)

    assert compositor.calls[-1] == (0.0, 0.0)
    assert session.last_displayed_pose == (0.0, 0.0)
    assert session.state == "playing"
    assert completed == ["done"]
    assert scheduler.live() == []


def test_delayed_recenter_callbacks_coalesce_elapsed_progress_monotonically() -> None:
    session, _, scheduler, compositor, _, _, _ = make_session()
    starting_pose = move_once(session, scheduler)
    session.pause_and_recenter(lambda: None)

    scheduler.run_next(advance_ms=66)
    scheduler.run_next(advance_ms=40)
    scheduler.run_next(advance_ms=40)

    values = [pose[0] for pose in compositor.calls[-3:]]
    assert values[0] == pytest.approx(starting_pose[0] * 0.5)
    assert starting_pose[0] >= values[0] >= values[1] >= values[2]
    assert values[-1] == 0.0
    assert session.state == "playing"
    assert all(delay == 33 for delay in scheduler.delays[-3:])


def test_already_centered_recenter_completes_synchronously_without_timer() -> None:
    session, _, scheduler, compositor, _, _, _ = make_session()
    session.start()
    completed: list[str] = []

    result = session.pause_and_recenter(lambda: completed.append("done"))

    assert result is _module().SessionResult.ACCEPTED
    assert session.state == "playing"
    assert completed == ["done"]
    assert scheduler.live() == []
    assert compositor.calls == [(0.0, 0.0)]


def test_resume_following_from_playing_repaints_nothing_and_is_idempotent() -> None:
    session, _, scheduler, compositor, display, _, _ = make_session()
    session.start()
    session.pause_and_recenter(lambda: None)
    compose_count = len(compositor.calls)
    display_count = len(display.calls)

    first = session.resume_following()
    second = session.resume_following()

    assert first is _module().SessionResult.ACCEPTED
    assert second is _module().SessionResult.ACCEPTED
    assert session.state == "following"
    assert len(scheduler.live()) == 1
    assert len(compositor.calls) == compose_count
    assert len(display.calls) == display_count


@pytest.mark.parametrize(
    "mode", ["synchronous", "raise_before_queue", "raise_after_queue"]
)
def test_following_tick_scheduler_hazard_disables_without_recursion_or_owner(
    mode: str,
) -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    session, _, _, compositor, _, disabled, _ = make_session(
        scheduler=scheduler,
        clock=clock,
    )
    session.start()
    scheduler.mode = mode

    scheduler.run_next()
    stale_callbacks = [entry.callback for entry in scheduler.pending]
    scheduler.pending.clear()
    compose_count = len(compositor.calls)
    for callback in stale_callbacks:
        callback()

    assert session.state == "disabled"
    assert disabled == ["disabled"]
    assert len(compositor.calls) == compose_count
    assert scheduler.live() == []


@pytest.mark.parametrize("failure_site", ["compose", "display"])
def test_following_callback_failure_is_contained_and_preserves_last_pose(
    failure_site: str,
) -> None:
    session, _, scheduler, compositor, display, disabled, _ = make_session()
    session.start()
    if failure_site == "compose":
        compositor.fail_next = True
    else:
        display.fail_next = True

    scheduler.run_next()

    assert session.state == "following"
    assert session.last_displayed_pose == (0.0, 0.0)
    assert disabled == []
    assert len(scheduler.live()) == 1

    scheduler.run_next()

    assert session.state == "following"
    assert session.last_displayed_pose != (0.0, 0.0)
    assert disabled == []
    assert len(scheduler.live()) == 1


@pytest.mark.parametrize("failure_site", ["compose", "display"])
def test_recenter_failure_cancels_work_and_stale_callback_cannot_complete(
    failure_site: str,
) -> None:
    session, _, scheduler, compositor, display, disabled, _ = make_session()
    starting_pose = move_once(session, scheduler)
    completed: list[str] = []
    session.pause_and_recenter(lambda: completed.append("done"))
    stale_callback = scheduler.live()[0].callback
    if failure_site == "compose":
        compositor.fail_next = True
    else:
        display.fail_next = True

    scheduler.run_next()
    calls_after_failure = len(compositor.calls)
    stale_callback()

    assert session.state == "disabled"
    assert session.last_displayed_pose == starting_pose
    assert disabled == ["disabled"]
    assert completed == []
    assert len(compositor.calls) == calls_after_failure
    assert scheduler.live() == []


def test_stale_recenter_callback_after_stop_is_inert() -> None:
    session, _, scheduler, compositor, display, _, _ = make_session()
    move_once(session, scheduler)
    completed: list[str] = []
    session.pause_and_recenter(lambda: completed.append("done"))
    stale_callback = scheduler.live()[0].callback
    compose_count = len(compositor.calls)
    display_count = len(display.calls)

    session.stop()
    stale_callback()

    assert session.state == "stopped"
    assert len(compositor.calls) == compose_count
    assert len(display.calls) == display_count
    assert completed == []
    assert scheduler.live() == []


def test_disabled_reports_fallback_and_never_composes_again() -> None:
    session, _, scheduler, compositor, _, disabled, _ = make_session()
    compositor.fail_next = True
    session.start()
    compose_count = len(compositor.calls)

    assert session.pause_and_recenter(lambda: None) is _module().SessionResult.FALLBACK
    assert session.resume_following() is _module().SessionResult.FALLBACK
    assert session.start() is _module().SessionResult.FALLBACK
    assert len(compositor.calls) == compose_count
    assert disabled == ["disabled"]
    assert scheduler.live() == []


def test_invalid_transitions_are_rejected_and_stop_is_valid_from_every_state() -> None:
    session, _, scheduler, _, _, _, _ = make_session()

    assert session.resume_following() is _module().SessionResult.REJECTED
    assert session.pause_and_recenter(lambda: None) is _module().SessionResult.REJECTED
    session.start()
    assert session.resume_following() is _module().SessionResult.ACCEPTED
    session.stop()
    session.stop()

    assert session.state == "stopped"
    assert session.resume_following() is _module().SessionResult.REJECTED
    assert session.pause_and_recenter(lambda: None) is _module().SessionResult.REJECTED
    assert scheduler.live() == []


@pytest.mark.parametrize("callback_site", ["compose", "display"])
def test_initial_callback_reentrant_stop_cannot_display_commit_or_revive(
    callback_site: str,
) -> None:
    session, _, scheduler, compositor, display, _, _ = make_session()
    if callback_site == "compose":
        compositor.on_compose = session.stop
    else:
        display.on_display = session.stop

    result = session.start()

    assert result is _module().SessionResult.REJECTED
    assert session.state == "stopped"
    assert session.last_displayed_pose is None
    assert display.calls == ([] if callback_site == "compose" else [("frame", 0.0, 0.0)])
    assert scheduler.live() == []


@pytest.mark.parametrize("callback_site", ["compose", "display"])
def test_following_callback_reentrant_stop_cannot_commit_or_reschedule(
    callback_site: str,
) -> None:
    session, _, scheduler, compositor, display, _, _ = make_session()
    session.start()
    display_count = len(display.calls)
    if callback_site == "compose":
        compositor.on_compose = session.stop
    else:
        display.on_display = session.stop

    scheduler.run_next()

    assert session.state == "stopped"
    assert session.last_displayed_pose == (0.0, 0.0)
    expected_displays = display_count if callback_site == "compose" else display_count + 1
    assert len(display.calls) == expected_displays
    assert scheduler.live() == []


@pytest.mark.parametrize("callback_site", ["compose", "display"])
def test_recenter_callback_reentrant_stop_cannot_commit_complete_or_reschedule(
    callback_site: str,
) -> None:
    session, _, scheduler, compositor, display, _, _ = make_session()
    starting_pose = move_once(session, scheduler)
    completed: list[str] = []
    session.pause_and_recenter(lambda: completed.append("done"))
    display_count = len(display.calls)
    if callback_site == "compose":
        compositor.on_compose = session.stop
    else:
        display.on_display = session.stop

    scheduler.run_next(advance_ms=132)

    assert session.state == "stopped"
    assert session.last_displayed_pose == starting_pose
    assert completed == []
    expected_displays = display_count if callback_site == "compose" else display_count + 1
    assert len(display.calls) == expected_displays
    assert scheduler.live() == []


def test_centered_completion_exception_is_contained_and_resumes_one_loop() -> None:
    session, _, scheduler, _, _, _, _ = make_session()
    session.start()
    callback_calls: list[str] = []

    def fail_completion() -> None:
        callback_calls.append("called")
        raise RuntimeError("completion failed")

    result = session.pause_and_recenter(fail_completion)

    assert result is _module().SessionResult.ACCEPTED
    assert callback_calls == ["called"]
    assert session.state == "following"
    assert session.last_displayed_pose == (0.0, 0.0)
    assert len(scheduler.live()) == 1


@pytest.mark.parametrize(
    "mode", ["synchronous", "raise_before_queue", "raise_after_queue"]
)
def test_centered_completion_recovery_scheduler_hazard_returns_fallback(
    mode: str,
) -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    session, _, _, _, _, disabled, _ = make_session(
        scheduler=scheduler,
        clock=clock,
    )
    session.start()
    scheduler.mode = mode

    result = session.pause_and_recenter(
        lambda: (_ for _ in ()).throw(RuntimeError("completion failed"))
    )
    stale_callbacks = [entry.callback for entry in scheduler.pending]
    scheduler.pending.clear()
    for callback in stale_callbacks:
        callback()

    assert result is _module().SessionResult.FALLBACK
    assert session.state == "disabled"
    assert disabled == ["disabled"]
    assert scheduler.live() == []


def test_timed_completion_exception_is_contained_and_resumes_one_loop() -> None:
    session, _, scheduler, _, _, _, _ = make_session()
    move_once(session, scheduler)
    callback_calls: list[str] = []

    def fail_completion() -> None:
        callback_calls.append("called")
        raise RuntimeError("completion failed")

    session.pause_and_recenter(fail_completion)
    scheduler.run_next(advance_ms=132)

    assert callback_calls == ["called"]
    assert session.state == "following"
    assert session.last_displayed_pose == (0.0, 0.0)
    assert len(scheduler.live()) == 1


@pytest.mark.parametrize(
    "mode", ["synchronous", "raise_before_queue", "raise_after_queue"]
)
def test_completion_recovery_scheduler_hazard_disables_without_following_orphan(
    mode: str,
) -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    session, _, _, compositor, _, disabled, _ = make_session(
        scheduler=scheduler,
        clock=clock,
    )
    move_once(session, scheduler)

    def fail_completion() -> None:
        raise RuntimeError("completion failed")

    session.pause_and_recenter(fail_completion)
    scheduler.mode = mode
    scheduler.run_next(advance_ms=132)
    stale_callbacks = [entry.callback for entry in scheduler.pending]
    scheduler.pending.clear()
    compose_count = len(compositor.calls)
    for callback in stale_callbacks:
        callback()

    assert session.state == "disabled"
    assert disabled == ["disabled"]
    assert len(compositor.calls) == compose_count
    assert scheduler.live() == []


def test_completion_exception_preserves_reentrant_stop() -> None:
    session, _, scheduler, _, _, _, _ = make_session()
    session.start()

    def stop_then_fail() -> None:
        session.stop()
        raise RuntimeError("completion failed after stop")

    result = session.pause_and_recenter(stop_then_fail)

    assert result is _module().SessionResult.ACCEPTED
    assert session.state == "stopped"
    assert scheduler.live() == []


def test_stop_is_directly_idempotent_from_unstarted_and_stopped() -> None:
    session, _, scheduler, _, _, _, _ = make_session()

    session.stop()
    session.stop()

    assert session.state == "stopped"
    assert session.start() is _module().SessionResult.REJECTED
    assert scheduler.live() == []


def test_stop_is_directly_idempotent_from_playing() -> None:
    session, _, scheduler, _, _, _, _ = make_session()
    session.start()
    session.pause_and_recenter(lambda: None)
    assert session.state == "playing"

    session.stop()
    session.stop()

    assert session.state == "stopped"
    assert scheduler.live() == []


def test_stop_is_directly_idempotent_from_disabled() -> None:
    session, _, scheduler, compositor, _, disabled, _ = make_session()
    compositor.fail_next = True
    session.start()
    assert session.state == "disabled"

    session.stop()
    session.stop()

    assert session.state == "stopped"
    assert disabled == ["disabled"]
    assert scheduler.live() == []


def test_pause_cancel_reentrant_stop_wins_without_recenter_or_action_owner() -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    cancel = ControlledCancel(scheduler)
    session, _, _, _, _, _, cycle, play_calls, selected, presented = (
        make_action_session(scheduler=scheduler, cancel=cancel, clock=clock)
    )
    cancel.callback = session.stop
    session.start()

    result = session.request_action()

    assert result is _module().SessionResult.REJECTED
    assert session.state == "stopped"
    assert cycle.peek() == "jump"
    assert play_calls == selected == presented == []
    assert scheduler.live() == []
    assert session.animation_finished("jump") is _module().SessionResult.REJECTED


def test_pause_cancel_reentrant_request_is_rejected_behind_outer_reservation() -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    cancel = ControlledCancel(scheduler)
    session, _, _, _, _, _, cycle, play_calls, selected, presented = (
        make_action_session(scheduler=scheduler, cancel=cancel, clock=clock)
    )
    nested_results: list[object] = []
    cancel.callback = lambda: nested_results.append(session.request_action())
    session.start()

    outer_result = session.request_action()

    assert outer_result is _module().SessionResult.ACCEPTED
    assert nested_results == [_module().SessionResult.REJECTED]
    assert session.state == "playing"
    assert cycle.peek() == "squash"
    assert play_calls == ["jump"]
    assert selected == ["jump"]
    assert presented == ["phrase:jump"]
    assert scheduler.live() == []


@pytest.mark.parametrize("nested_operation", ["pause", "resume"])
def test_pause_cancel_reentrant_public_transition_is_rejected_by_recenter_reservation(
    nested_operation: str,
) -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    cancel = ControlledCancel(scheduler)
    session, _, _, _, _, _, _ = make_session(
        scheduler=scheduler,
        cancel=cancel,
        clock=clock,
    )
    move_once(session, scheduler)
    nested_results: list[object] = []
    nested_completed: list[str] = []
    if nested_operation == "pause":
        cancel.callback = lambda: nested_results.append(
            session.pause_and_recenter(lambda: nested_completed.append("nested"))
        )
    else:
        cancel.callback = lambda: nested_results.append(session.resume_following())

    outer_result = session.pause_and_recenter(lambda: None)

    assert outer_result is _module().SessionResult.ACCEPTED
    assert nested_results == [_module().SessionResult.REJECTED]
    assert nested_completed == []
    assert session.state == "recentering"
    assert len(scheduler.live()) == 1


def test_disable_recenter_cancel_reentrant_stop_suppresses_disabled_notification() -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    cancel = ControlledCancel(scheduler)
    session, _, _, compositor, _, disabled, _ = make_session(
        scheduler=scheduler,
        cancel=cancel,
        clock=clock,
    )
    move_once(session, scheduler)
    session.pause_and_recenter(lambda: None)
    stale_callback = scheduler.live()[0].callback
    cancel.callback = session.stop

    session._disable()
    compose_count = len(compositor.calls)
    stale_callback()

    assert session.state == "stopped"
    assert disabled == []
    assert len(compositor.calls) == compose_count
    assert scheduler.live() == []


def test_stop_cancel_reentrant_request_is_rejected_without_action_owner() -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    cancel = ControlledCancel(scheduler)
    session, _, _, _, _, _, cycle, play_calls, selected, presented = (
        make_action_session(scheduler=scheduler, cancel=cancel, clock=clock)
    )
    reentrant_results: list[object] = []
    cancel.callback = lambda: reentrant_results.append(session.request_action())
    session.start()

    session.stop()

    assert reentrant_results == [_module().SessionResult.REJECTED]
    assert session.state == "stopped"
    assert cycle.peek() == "jump"
    assert play_calls == selected == presented == []
    assert scheduler.live() == []
    assert session.animation_finished("jump") is _module().SessionResult.REJECTED


def test_pause_cancel_exception_becomes_disabled_fallback_without_orphan() -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    cancel = ControlledCancel(scheduler)
    session, _, _, _, _, disabled, cycle, play_calls, selected, presented = (
        make_action_session(scheduler=scheduler, cancel=cancel, clock=clock)
    )
    session.start()
    cancel.raise_error = True

    result = session.request_action()

    assert result is _module().SessionResult.FALLBACK
    assert session.state == "disabled"
    assert disabled == ["disabled"]
    assert cycle.peek() == "jump"
    assert play_calls == selected == presented == []
    assert scheduler.live() == []


def test_stop_contains_following_cancel_exception_and_publishes_stopped() -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    cancel = ControlledCancel(scheduler)
    session, _, _, compositor, _, _, _ = make_session(
        scheduler=scheduler,
        cancel=cancel,
        clock=clock,
    )
    session.start()
    stale_callback = scheduler.live()[0].callback
    cancel.raise_error = True

    session.stop()
    compose_count = len(compositor.calls)
    stale_callback()

    assert session.state == "stopped"
    assert len(compositor.calls) == compose_count
    assert scheduler.live() == []


def test_stop_contains_recenter_cancel_exception_and_clears_action_owner() -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    cancel = ControlledCancel(scheduler)
    session, _, _, compositor, _, _, cycle, play_calls, selected, presented = (
        make_action_session(scheduler=scheduler, cancel=cancel, clock=clock)
    )
    move_once(session, scheduler)
    session.request_action()
    stale_callback = scheduler.live()[0].callback
    cancel.raise_error = True

    session.stop()
    compose_count = len(compositor.calls)
    stale_callback()

    assert session.state == "stopped"
    assert cycle.peek() == "jump"
    assert play_calls == selected == presented == []
    assert len(compositor.calls) == compose_count
    assert scheduler.live() == []


def test_action_request_accepts_then_commits_and_presents_matching_phrase() -> None:
    (
        session,
        _,
        scheduler,
        _,
        _,
        _,
        cycle,
        play_calls,
        selected,
        presented,
    ) = make_action_session()
    session.start()

    result = session.request_action()

    assert result is _module().SessionResult.ACCEPTED
    assert session.state == "playing"
    assert play_calls == ["jump"]
    assert cycle.peek() == "squash"
    assert selected == ["jump"]
    assert presented == ["phrase:jump"]
    assert scheduler.live() == []


def test_named_action_plays_exact_selection_without_advancing_click_cycle() -> None:
    (
        session,
        _,
        scheduler,
        _,
        _,
        _,
        cycle,
        play_calls,
        selected,
        presented,
    ) = make_action_session()
    session.start()

    result = session.request_named_action("shake")

    assert result is _module().SessionResult.ACCEPTED
    assert session.state == "playing"
    assert play_calls == ["shake"]
    assert selected == ["shake"]
    assert presented == ["phrase:shake"]
    assert cycle.peek() == "jump"
    assert session.logical_frame("shake", 2) is not None
    assert session.animation_finished("shake") is _module().SessionResult.ACCEPTED
    assert session.state == "following"
    assert cycle.peek() == "jump"
    assert len(scheduler.live()) == 1


def test_named_action_rejects_invalid_name_without_side_effects() -> None:
    session, _, _, _, _, _, cycle, play_calls, selected, presented = (
        make_action_session()
    )
    session.start()

    with pytest.raises(ValueError, match="named action"):
        session.request_named_action("unknown")

    assert session.state == "following"
    assert cycle.peek() == "jump"
    assert play_calls == selected == presented == []


def test_manual_blink_plays_once_and_restarts_random_cooldown() -> None:
    module = _module()
    clock = Clock()
    scheduler = ManualScheduler(clock)
    compositor = BlinkCompositor()
    displayed: list[object] = []
    blink = NaturalBlinkMotion(uniform=lambda low, high: low)
    session = module.RuntimeEyeSession(
        compositor=compositor,
        cursor_provider=Cursor(None),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=displayed.append,
        scheduler=scheduler,
        cancel=scheduler.cancel,
        clock=clock,
        on_disabled=lambda: None,
        action_cycle=ActionCycle(),
        physical_frames={
            action: tuple(object() for _ in range(6)) for action in ACTIONS
        },
        play_action=lambda _action: True,
        cancel_action=lambda _action: True,
        choose_phrase=lambda action: action,
        present_phrase=lambda _phrase: None,
        on_action_failed=lambda _action, _failure: None,
        blink_motion=blink,
    )
    assert session.start() is module.SessionResult.ACCEPTED
    assert blink.next_blink_at == pytest.approx(MIN_BLINK_INTERVAL_SECONDS)

    assert session.request_blink() is module.SessionResult.ACCEPTED
    assert blink.next_blink_at == pytest.approx(0.0)
    clock.value = CLOSE_SECONDS
    session._following_ambient_pulse()
    assert compositor.blink_calls[-1][2] == pytest.approx(1.0)

    clock.value = TOTAL_BLINK_SECONDS + 1e-6
    session._following_ambient_pulse()
    assert compositor.blink_calls[-1][2] == pytest.approx(0.0)
    assert blink.next_blink_at == pytest.approx(
        clock.value + MIN_BLINK_INTERVAL_SECONDS
    )


def test_repeated_requests_during_recentering_and_playing_have_no_side_effects() -> None:
    session, _, scheduler, _, _, _, cycle, play_calls, selected, presented = (
        make_action_session()
    )
    move_once(session, scheduler)

    assert session.request_action() is _module().SessionResult.ACCEPTED
    assert session.state == "recentering"
    first_live = scheduler.live()
    assert session.request_action() is _module().SessionResult.REJECTED
    assert scheduler.live() == first_live
    assert cycle.peek() == "jump"
    assert play_calls == selected == presented == []

    scheduler.run_next(advance_ms=132)
    assert session.state == "playing"
    assert session.request_action() is _module().SessionResult.REJECTED
    assert cycle.peek() == "squash"
    assert play_calls == ["jump"]
    assert selected == ["jump"]
    assert presented == ["phrase:jump"]


@pytest.mark.parametrize("failure_mode", ["false", "raise"])
def test_failed_play_keeps_cycle_and_phrase_untouched_then_resumes_once(
    failure_mode: str,
) -> None:
    calls: list[str] = []

    def fail_play(action: str) -> bool:
        calls.append(action)
        if failure_mode == "raise":
            raise RuntimeError("play failed")
        return False

    session, _, scheduler, compositor, display, _, cycle, _, selected, presented = (
        make_action_session(play_action=fail_play)
    )
    move_once(session, scheduler)
    compose_count = len(compositor.calls)
    display_count = len(display.calls)
    session.request_action()

    scheduler.run_next(advance_ms=132)

    assert calls == ["jump"]
    assert cycle.peek() == "jump"
    assert selected == presented == []
    assert session.state == "following"
    assert len(scheduler.live()) == 1
    assert len(compositor.calls) == compose_count + 1
    assert len(display.calls) == display_count + 1


def test_animation_finish_requires_active_match_and_resumes_without_repaint() -> None:
    session, _, scheduler, compositor, display, _, cycle, *_ = make_action_session()
    session.start()
    session.request_action()
    compose_count = len(compositor.calls)
    display_count = len(display.calls)

    assert session.animation_finished("shake") is _module().SessionResult.REJECTED
    assert session.state == "playing"
    assert session.animation_finished("jump") is _module().SessionResult.ACCEPTED
    assert session.animation_finished("jump") is _module().SessionResult.REJECTED

    assert session.state == "following"
    assert cycle.peek() == "squash"
    assert len(scheduler.live()) == 1
    assert len(compositor.calls) == compose_count
    assert len(display.calls) == display_count


@pytest.mark.parametrize(
    "mode", ["synchronous", "raise_before_queue", "raise_after_queue"]
)
def test_action_finish_scheduler_hazard_disables_without_following_orphan(
    mode: str,
) -> None:
    clock = Clock()
    scheduler = ControlledScheduler(clock)
    session, _, _, compositor, _, disabled, cycle, *_ = make_action_session(
        scheduler=scheduler,
        clock=clock,
    )
    session.start()
    session.request_action()
    scheduler.mode = mode

    result = session.animation_finished("jump")
    stale_callbacks = [entry.callback for entry in scheduler.pending]
    scheduler.pending.clear()
    compose_count = len(compositor.calls)
    for callback in stale_callbacks:
        callback()

    assert result is _module().SessionResult.FALLBACK
    assert session.state == "disabled"
    assert disabled == ["disabled"]
    assert cycle.peek() == "squash"
    assert len(compositor.calls) == compose_count
    assert scheduler.live() == []


def test_play_callback_reentrant_stop_wins_without_commit_or_phrase() -> None:
    holder: list[object] = []

    def stop_during_play(_action: str) -> bool:
        holder[0].stop()
        return True

    session, _, scheduler, _, _, _, cycle, _, selected, presented = (
        make_action_session(play_action=stop_during_play)
    )
    holder.append(session)
    session.start()

    session.request_action()

    assert session.state == "stopped"
    assert cycle.peek() == "jump"
    assert selected == presented == []
    assert scheduler.live() == []


@pytest.mark.parametrize(
    "phrase_site", ["choose_raise", "choose_stop", "present_raise", "present_stop"]
)
def test_phrase_failures_are_contained_and_reentrant_lifecycle_wins(
    phrase_site: str,
) -> None:
    holder: list[object] = []
    selected: list[str] = []
    presented: list[str] = []

    def choose(action: str) -> str:
        selected.append(action)
        if phrase_site == "choose_raise":
            raise RuntimeError("choose failed")
        if phrase_site == "choose_stop":
            holder[0].stop()
        return f"phrase:{action}"

    def present(phrase: str) -> None:
        presented.append(phrase)
        if phrase_site == "present_raise":
            raise RuntimeError("present failed")
        if phrase_site == "present_stop":
            holder[0].stop()

    session, _, scheduler, _, _, _, cycle, *_ = make_action_session(
        choose_phrase=choose, present_phrase=present
    )
    holder.append(session)
    session.start()

    session.request_action()

    assert cycle.peek() == "squash"
    assert selected == ["jump"]
    if phrase_site in ("choose_stop", "present_stop"):
        assert session.state == "stopped"
        assert presented == ([] if phrase_site == "choose_stop" else ["phrase:jump"])
        assert scheduler.live() == []
    else:
        assert session.state == "playing"
        assert presented == ([] if phrase_site == "choose_raise" else ["phrase:jump"])


def test_stop_clears_pending_and_active_action_ownership() -> None:
    session, _, scheduler, _, _, _, cycle, play_calls, selected, presented = (
        make_action_session()
    )
    move_once(session, scheduler)
    session.request_action()
    stale_recenter = scheduler.live()[0].callback

    session.stop()
    stale_recenter()

    assert session.state == "stopped"
    assert session.animation_finished("jump") is _module().SessionResult.REJECTED
    assert cycle.peek() == "jump"
    assert play_calls == selected == presented == []
    assert scheduler.live() == []


def test_stop_clears_accepted_active_action_ownership() -> None:
    session, _, scheduler, _, _, _, cycle, *_ = make_action_session()
    session.start()
    session.request_action()
    assert cycle.peek() == "squash"

    session.stop()

    assert session.animation_finished("jump") is _module().SessionResult.REJECTED
    assert session.state == "stopped"
    assert scheduler.live() == []


def test_phrase_callback_finish_transition_prevents_stale_phrase_display() -> None:
    holder: list[object] = []
    presented: list[str] = []

    def choose(action: str) -> str:
        assert holder[0].animation_finished(action) is _module().SessionResult.ACCEPTED
        return f"phrase:{action}"

    session, _, scheduler, _, _, _, cycle, *_ = make_action_session(
        choose_phrase=choose, present_phrase=presented.append
    )
    holder.append(session)
    session.start()

    session.request_action()

    assert cycle.peek() == "squash"
    assert presented == []
    assert session.state == "following"
    assert len(scheduler.live()) == 1


def test_play_callback_can_select_pending_logical_neutral_by_identity() -> None:
    holder: list[object] = []
    selected_frames: list[object] = []
    session, _, _, _, display, _, cycle, *_ = make_action_session(
        play_action=lambda action: (
            selected_frames.append(holder[0].logical_frame(action, 0)) or True
        )
    )
    holder.append(session)
    session.start()

    session.request_action()

    assert cycle.peek() == "squash"
    assert selected_frames == [display.calls[0]]
    assert selected_frames[0] is display.calls[0]


def test_disabled_action_request_is_explicit_fallback_without_composition() -> None:
    session, _, _, compositor, _, _, cycle, play_calls, selected, presented = (
        make_action_session()
    )
    compositor.fail_next = True
    session.start()
    compose_count = len(compositor.calls)

    assert session.request_action() is _module().SessionResult.FALLBACK
    assert len(compositor.calls) == compose_count
    assert cycle.peek() == "jump"
    assert play_calls == selected == presented == []


@pytest.mark.parametrize("action", ACTIONS)
def test_real_action_logical_boundaries_share_cached_center_and_middle_identity(
    action: str,
) -> None:
    frames = load_frames(runtime_frame_root())
    cycle = ActionCycle()
    while cycle.peek() != action:
        cycle.commit(cycle.peek())
    session, _, _, _, display, _, _, *_ = make_action_session(
        cycle=cycle, physical_frames=frames
    )
    session.start()
    center = display.calls[0]
    session.request_action()

    assert session.logical_frame(action, 0) is center
    assert session.logical_frame(action, 5) is center
    for index in range(1, 5):
        assert session.logical_frame(action, index) is frames[action][index]
    assert len(frames[action]) == 6
    assert all(frame.mode == "RGBA" and frame.size == (512, 768) for frame in frames[action])


@pytest.mark.parametrize("index", [-1, 6])
def test_logical_frame_rejects_indices_outside_six_slots(index: int) -> None:
    session, *_ = make_action_session()
    session.start()
    session.request_action()

    with pytest.raises(IndexError, match="logical action frame"):
        session.logical_frame("jump", index)


def test_real_controller_synchronous_completion_commits_phrase_then_resumes_once() -> None:
    from desktop_pet.animation import AnimationController

    eye_clock = Clock()
    eye_scheduler = ManualScheduler(eye_clock)
    compositor = Compositor()
    display = Display()
    frames = {action: tuple(object() for _ in range(6)) for action in ACTIONS}
    events: list[object] = []
    delays: list[int] = []
    holder: list[object] = []

    class RecordingCycle(ActionCycle):
        def commit(self, expected: str) -> None:
            events.append(("commit", expected))
            super().commit(expected)

    cycle = RecordingCycle()

    def eye_schedule(delay_ms: int, callback):
        events.append(("eye-schedule", delay_ms))
        return eye_scheduler(delay_ms, callback)

    def synchronous_schedule(delay_ms: int, callback) -> object:
        delays.append(delay_ms)
        callback()
        return object()

    controller = AnimationController(
        {action: 6 for action in ACTIONS},
        synchronous_schedule,
        lambda action, index: events.append(
            ("frame", action, index, holder[0].logical_frame(action, index))
        ),
        lambda action: events.append(
            ("finish-result", holder[0].animation_finished(action))
        ),
        cancel=lambda _token: None,
    )
    session = _module().RuntimeEyeSession(
        compositor=compositor,
        cursor_provider=Cursor(CursorPoint(200, 100)),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=display,
        scheduler=eye_schedule,
        cancel=eye_scheduler.cancel,
        clock=eye_clock,
        on_disabled=lambda: None,
        action_cycle=cycle,
        physical_frames=frames,
        play_action=controller.play,
        cancel_action=controller.cancel_current,
        choose_phrase=lambda action: (
            events.append(("choose", action)),
            events.append(
                ("choose-duplicate", holder[0].animation_finished(action))
            ),
            f"phrase:{action}",
        )[-1],
        present_phrase=lambda phrase: (
            events.append(("present", phrase)),
            events.append(
                ("present-duplicate", holder[0].animation_finished("jump"))
            ),
        ),
        on_action_failed=lambda _action, _failure: None,
    )
    holder.append(session)
    session.start()
    events.clear()

    assert session.request_action() is _module().SessionResult.ACCEPTED

    assert cycle.peek() == "squash"
    assert session.state == "following"
    assert len(eye_scheduler.live()) == 1
    assert delays == [90] * 6
    assert [event[:3] for event in events if event[0] == "frame"] == [
        ("frame", "jump", index) for index in range(6)
    ]
    assert events[-7:] == [
        ("finish-result", _module().SessionResult.ACCEPTED),
        ("commit", "jump"),
        ("choose", "jump"),
        ("choose-duplicate", _module().SessionResult.REJECTED),
        ("present", "phrase:jump"),
        ("present-duplicate", _module().SessionResult.REJECTED),
        ("eye-schedule", 33),
    ]


def test_real_controller_is_cancelled_before_following_when_commit_is_invalidated() -> None:
    from desktop_pet.animation import AnimationController

    eye_clock = Clock()
    eye_scheduler = ManualScheduler(eye_clock)
    animation_scheduler = ManualScheduler(Clock())
    cycle = ActionCycle()
    frames = {action: tuple(object() for _ in range(6)) for action in ACTIONS}
    events: list[str] = []
    holder: list[object] = []

    def eye_schedule(delay_ms: int, callback):
        events.append("eye-schedule")
        return eye_scheduler(delay_ms, callback)

    def frame_changed(action: str, index: int) -> None:
        holder[0].logical_frame(action, index)
        if index == 0:
            cycle.commit(action)

    controller = AnimationController(
        {action: 6 for action in ACTIONS},
        animation_scheduler,
        frame_changed,
        lambda action: holder[0].animation_finished(action),
        cancel=animation_scheduler.cancel,
    )

    def cancel_action(action: str) -> bool:
        events.append("action-cancel")
        return controller.cancel_current(action)

    session = _module().RuntimeEyeSession(
        compositor=Compositor(),
        cursor_provider=Cursor(CursorPoint(200, 100)),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=Display(),
        scheduler=eye_schedule,
        cancel=eye_scheduler.cancel,
        clock=eye_clock,
        on_disabled=lambda: None,
        action_cycle=cycle,
        physical_frames=frames,
        play_action=controller.play,
        cancel_action=cancel_action,
        choose_phrase=lambda action: f"phrase:{action}",
        present_phrase=lambda _phrase: events.append("present"),
        on_action_failed=lambda _action, _failure: None,
    )
    holder.append(session)
    session.start()
    events.clear()

    session.request_action()

    assert events == ["action-cancel", "eye-schedule"]
    assert controller.busy is False
    assert session.state == "following"
    assert len(eye_scheduler.live()) == 1
    assert len(animation_scheduler.live()) == 0
    assert cycle.peek() == "squash"


def test_real_reentrant_successor_cancel_failure_keeps_eyes_paused_and_signals() -> None:
    from desktop_pet.animation import AnimationController

    eye_clock = Clock()
    eye_scheduler = ManualScheduler(eye_clock)
    animation_scheduler = ManualScheduler(Clock())
    cycle = ActionCycle()
    holder: list[object] = []
    successor_results: list[bool] = []
    failures: list[object] = []
    phrases: list[str] = []
    controller: AnimationController

    def frame_changed(action: str, index: int) -> None:
        if action == "jump":
            holder[0].logical_frame(action, index)
            if index == 0:
                cycle.commit(action)

    def cancel_then_start(token: object) -> None:
        animation_scheduler.cancel(token)
        successor_results.append(controller.play("shake"))

    controller = AnimationController(
        {action: 6 for action in ACTIONS},
        animation_scheduler,
        frame_changed,
        lambda action: holder[0].animation_finished(action),
        cancel=cancel_then_start,
    )
    session = _module().RuntimeEyeSession(
        compositor=Compositor(),
        cursor_provider=Cursor(CursorPoint(200, 100)),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=Display(),
        scheduler=eye_scheduler,
        cancel=eye_scheduler.cancel,
        clock=eye_clock,
        on_disabled=lambda: None,
        action_cycle=cycle,
        physical_frames={
            action: tuple(object() for _ in range(6)) for action in ACTIONS
        },
        play_action=controller.play,
        cancel_action=controller.cancel_current,
        choose_phrase=lambda action: phrases.append(action) or action,
        present_phrase=lambda phrase: phrases.append(phrase),
        on_action_failed=lambda action, failure: failures.append((action, failure)),
    )
    holder.append(session)
    session.start()

    session.request_action()

    assert successor_results == [True]
    assert controller.busy is True
    assert session.state == "playing"
    assert eye_scheduler.live() == []
    assert phrases == []
    assert failures == [("jump", _module().ActionFailure.CANCEL_REJECTED)]
    assert session.action_failure == ("jump", _module().ActionFailure.CANCEL_REJECTED)


@pytest.mark.parametrize("cancel_mode", ["false", "raise"])
def test_cancel_action_failure_stays_paused_and_exposes_owner_signal(
    cancel_mode: str,
) -> None:
    module = _module()
    failures: list[object] = []

    class FailingCycle(ActionCycle):
        def commit(self, expected: str) -> None:
            raise ValueError(f"lost {expected}")

    def cancel_action(_action: str) -> bool:
        if cancel_mode == "raise":
            raise RuntimeError("cancel failed")
        return False

    session, _, scheduler, _, _, _, _, *_ = make_action_session(
        cycle=FailingCycle(),
        cancel_action=cancel_action,
        on_action_failed=lambda action, failure: failures.append((action, failure)),
    )
    session.start()

    session.request_action()

    expected_failure = (
        module.ActionFailure.CANCEL_RAISED
        if cancel_mode == "raise"
        else module.ActionFailure.CANCEL_REJECTED
    )
    assert session.state == "playing"
    assert scheduler.live() == []
    assert failures == [("jump", expected_failure)]
    assert session.action_failure == ("jump", expected_failure)
    assert session.resume_following() is module.SessionResult.REJECTED
    assert scheduler.live() == []


@pytest.mark.parametrize("failure_site", ["frame0", "schedule"])
def test_real_controller_start_failure_aborts_before_eye_resume(
    failure_site: str,
) -> None:
    from desktop_pet.animation import AnimationController

    eye_clock = Clock()
    eye_scheduler = ManualScheduler(eye_clock)
    cycle = ActionCycle()
    holder: list[object] = []
    phrase_calls: list[str] = []
    display = Display()

    def animation_schedule(_delay_ms: int, _callback) -> object:
        if failure_site == "schedule":
            raise RuntimeError("animation schedule failed")
        return object()

    def frame_changed(action: str, index: int) -> None:
        display(holder[0].logical_frame(action, index))
        if failure_site == "frame0":
            raise RuntimeError("frame zero failed")

    controller = AnimationController(
        {action: 6 for action in ACTIONS},
        animation_schedule,
        frame_changed,
        lambda action: holder[0].animation_finished(action),
    )
    session = _module().RuntimeEyeSession(
        compositor=Compositor(),
        cursor_provider=Cursor(CursorPoint(200, 100)),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=display,
        scheduler=eye_scheduler,
        cancel=eye_scheduler.cancel,
        clock=eye_clock,
        on_disabled=lambda: None,
        action_cycle=cycle,
        physical_frames={
            action: tuple(object() for _ in range(6)) for action in ACTIONS
        },
        play_action=controller.play,
        cancel_action=controller.cancel_current,
        choose_phrase=lambda action: phrase_calls.append(action) or action,
        present_phrase=lambda phrase: phrase_calls.append(phrase),
        on_action_failed=lambda _action, _failure: None,
    )
    holder.append(session)
    session.start()

    session.request_action()

    assert controller.busy is False
    assert session.state == "following"
    assert cycle.peek() == "jump"
    assert phrase_calls == []
    assert len(eye_scheduler.live()) == 1
    if failure_site == "frame0":
        assert len(display.calls) == 2
        assert display.calls[1] is display.calls[0]
    else:
        assert len(display.calls) == 2
        assert display.calls[1] is display.calls[0]


def test_real_controller_post_return_cleanup_blocks_successor_and_resumes_eyes() -> None:
    from desktop_pet.animation import AnimationController

    eye_clock = Clock()
    eye_scheduler = ManualScheduler(eye_clock)
    cycle = ActionCycle()
    display = Display()
    holder: list[object] = []
    cancelled: list[object] = []
    successor_results: list[bool] = []
    controller: AnimationController

    def animation_schedule(_delay_ms: int, _callback) -> object:
        assert controller.cancel_current("jump") is True
        return "lost-jump-token"

    def cancel_then_start(token: object) -> None:
        cancelled.append(token)
        successor_results.append(controller.play("shake"))

    controller = AnimationController(
        {action: 6 for action in ACTIONS},
        animation_schedule,
        lambda action, index: display(holder[0].logical_frame(action, index)),
        lambda action: holder[0].animation_finished(action),
        cancel=cancel_then_start,
    )
    session = _module().RuntimeEyeSession(
        compositor=Compositor(),
        cursor_provider=Cursor(CursorPoint(200, 100)),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=display,
        scheduler=eye_scheduler,
        cancel=eye_scheduler.cancel,
        clock=eye_clock,
        on_disabled=lambda: None,
        action_cycle=cycle,
        physical_frames={
            action: tuple(object() for _ in range(6)) for action in ACTIONS
        },
        play_action=controller.play,
        cancel_action=controller.cancel_current,
        choose_phrase=lambda action: action,
        present_phrase=lambda _phrase: None,
        on_action_failed=lambda _action, _failure: None,
    )
    holder.append(session)
    session.start()

    session.request_action()

    assert cancelled == ["lost-jump-token"]
    assert successor_results == [False]
    assert controller.busy is False
    assert session.state == "following"
    assert len(eye_scheduler.live()) == 1
    assert cycle.peek() == "jump"


@pytest.mark.parametrize("failure_site", ["scheduled_frame", "scheduled_schedule"])
def test_real_controller_later_failure_clears_owner_and_keeps_eyes_paused(
    failure_site: str,
) -> None:
    from desktop_pet.animation import AnimationController

    eye_clock = Clock()
    eye_scheduler = ManualScheduler(eye_clock)
    animation_scheduler = ManualScheduler(Clock())
    cycle = ActionCycle()
    holder: list[object] = []
    schedule_calls = 0

    def animation_schedule(delay_ms: int, callback) -> object:
        nonlocal schedule_calls
        schedule_calls += 1
        if failure_site == "scheduled_schedule" and schedule_calls == 2:
            raise RuntimeError("later schedule failed")
        return animation_scheduler(delay_ms, callback)

    def frame_changed(action: str, index: int) -> None:
        holder[0].logical_frame(action, index)
        if failure_site == "scheduled_frame" and index == 1:
            raise RuntimeError("later frame failed")

    controller = AnimationController(
        {action: 6 for action in ACTIONS},
        animation_schedule,
        frame_changed,
        lambda action: holder[0].animation_finished(action),
        cancel=animation_scheduler.cancel,
    )
    session = _module().RuntimeEyeSession(
        compositor=Compositor(),
        cursor_provider=Cursor(CursorPoint(200, 100)),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=Display(),
        scheduler=eye_scheduler,
        cancel=eye_scheduler.cancel,
        clock=eye_clock,
        on_disabled=lambda: None,
        action_cycle=cycle,
        physical_frames={
            action: tuple(object() for _ in range(6)) for action in ACTIONS
        },
        play_action=controller.play,
        cancel_action=controller.cancel_current,
        choose_phrase=lambda action: action,
        present_phrase=lambda _phrase: None,
        on_action_failed=lambda _action, _failure: None,
    )
    holder.append(session)
    session.start()
    session.request_action()

    with pytest.raises(RuntimeError, match="later (frame|schedule) failed"):
        animation_scheduler.run_next()

    assert controller.busy is False
    assert session.state == "playing"
    assert eye_scheduler.live() == []
    assert cycle.peek() == "squash"


@pytest.mark.parametrize("attempt_result", ["false", "raise"])
def test_real_reentrant_play_attempt_failure_resumes_only_one_eye_owner(
    attempt_result: str,
) -> None:
    from desktop_pet.animation import AnimationController

    eye_clock = Clock()
    eye_scheduler = ManualScheduler(eye_clock)
    cycle = ActionCycle()
    holder: list[object] = []
    successor_results: list[bool] = []
    last_frame_action: list[str] = []
    controller: AnimationController

    def synchronous_schedule(_delay_ms: int, callback) -> object:
        if last_frame_action[-1] == "jump":
            callback()
        return object()

    def frame_changed(action: str, index: int) -> None:
        last_frame_action[:] = [action]
        if action == "jump":
            holder[0].logical_frame(action, index)
        failure_index = 0 if attempt_result == "false" else 1
        if action == "jump" and index == failure_index:
            assert controller.cancel_current(action) is True
            successor_results.append(controller.play("shake"))
            if attempt_result == "raise":
                raise RuntimeError("reentrant action failed")

    controller = AnimationController(
        {action: 6 for action in ACTIONS},
        synchronous_schedule,
        frame_changed,
        lambda action: holder[0].animation_finished(action),
    )
    session = _module().RuntimeEyeSession(
        compositor=Compositor(),
        cursor_provider=Cursor(CursorPoint(200, 100)),
        rect_provider=lambda: Rect(0, 0, 512, 768),
        display=Display(),
        scheduler=eye_scheduler,
        cancel=eye_scheduler.cancel,
        clock=eye_clock,
        on_disabled=lambda: None,
        action_cycle=cycle,
        physical_frames={
            action: tuple(object() for _ in range(6)) for action in ACTIONS
        },
        play_action=controller.play,
        cancel_action=controller.cancel_current,
        choose_phrase=lambda action: action,
        present_phrase=lambda _phrase: None,
        on_action_failed=lambda _action, _failure: None,
    )
    holder.append(session)
    session.start()

    session.request_action()

    assert successor_results == [False]
    assert controller.busy is False
    assert session.state == "following"
    assert len(eye_scheduler.live()) == 1
    assert cycle.peek() == "jump"

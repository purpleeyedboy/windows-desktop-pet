from __future__ import annotations

import ctypes
import math
import sys
from dataclasses import dataclass
from decimal import Decimal

import pytest


def _module():
    from desktop_pet import eye_follow

    return eye_follow


@dataclass
class FakeCursorProvider:
    point: object
    calls: int = 0

    def position(self):
        self.calls += 1
        return self.point


@dataclass
class FakeGeometryProvider:
    geometry: object
    calls: int = 0

    def __call__(self):
        self.calls += 1
        return self.geometry


class FakeScheduler:
    def __init__(self) -> None:
        self.pending: list[tuple[int, object]] = []
        self.cancelled: list[object] = []

    def __call__(self, delay_ms: int, callback):
        token = object()
        self.pending.append((delay_ms, (token, callback)))
        return token

    def cancel(self, token: object) -> None:
        self.cancelled.append(token)

    def run_one(self) -> None:
        _, (token, callback) = self.pending.pop(0)
        if token not in self.cancelled:
            callback()


class ControlledScheduler(FakeScheduler):
    def __init__(self) -> None:
        super().__init__()
        self.mode = "normal"
        self.calls = 0
        self.returned_tokens: list[object] = []

    def __call__(self, delay_ms: int, callback):
        self.calls += 1
        mode, self.mode = self.mode, "normal"
        if mode == "raise_before_queue":
            raise RuntimeError("scheduler failed before queue")
        token = object()
        if mode == "synchronous":
            callback()
        else:
            self.pending.append((delay_ms, (token, callback)))
        if mode == "raise_after_queue":
            raise RuntimeError("scheduler failed after queue")
        self.returned_tokens.append(token)
        return token


class Clock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def make_controller(
    point: object,
    *,
    display_height: float = 280.0,
    geometry: object | None = None,
    clock: Clock | None = None,
):
    module = _module()
    scheduler = FakeScheduler()
    provider = FakeCursorProvider(point)
    geometry_provider = FakeGeometryProvider(
        geometry or module.EyeGeometry(100, 100, display_height)
    )
    observed: list[tuple[float, float]] = []
    controller = module.EyeMotionController(
        scheduler,
        scheduler.cancel,
        provider,
        geometry_provider,
        lambda x, y: observed.append((x, y)),
        clock=clock or Clock(),
    )
    return controller, scheduler, provider, observed


def test_cursor_point_is_immutable_value() -> None:
    point = _module().CursorPoint(-12, 34)

    assert point == _module().CursorPoint(-12, 34)
    with pytest.raises((AttributeError, TypeError)):
        point.x = 0


def test_win32_cursor_provider_uses_ctypes_point_success_contract() -> None:
    module = _module()

    class User32:
        def GetCursorPos(self, point_ptr) -> int:
            point = ctypes.cast(point_ptr, ctypes.POINTER(module._POINT)).contents
            point.x = -17
            point.y = 42
            return 1

    assert issubclass(module._POINT, ctypes.Structure)
    assert module.Win32CursorProvider(User32()).position() == module.CursorPoint(-17, 42)


def test_win32_point_has_fixed_windows_int32_layout() -> None:
    point_type = _module()._POINT

    assert ctypes.sizeof(point_type) == 8
    assert point_type.x.offset == 0
    assert point_type.y.offset == 4


def test_win32_cursor_provider_returns_none_when_win32_call_fails() -> None:
    class User32:
        def GetCursorPos(self, point_ptr) -> int:
            return 0

    assert _module().Win32CursorProvider(User32()).position() is None


@pytest.mark.parametrize(
    ("dx", "dy", "expected"),
    [
        (0.0, 0.0, (0.0, 0.0)),
        (100.0, 0.0, (3.0, 0.0)),
        (-100.0, 0.0, (-3.0, 0.0)),
        (0.0, 100.0, (0.0, 2.0)),
        (0.0, -100.0, (0.0, -2.0)),
        (100.0 / math.sqrt(2), 100.0 / math.sqrt(2), (3.0 / math.sqrt(2), 2.0 / math.sqrt(2))),
        (-100.0 / math.sqrt(2), 100.0 / math.sqrt(2), (-3.0 / math.sqrt(2), 2.0 / math.sqrt(2))),
        (100.0 / math.sqrt(2), -100.0 / math.sqrt(2), (3.0 / math.sqrt(2), -2.0 / math.sqrt(2))),
        (-100.0 / math.sqrt(2), -100.0 / math.sqrt(2), (-3.0 / math.sqrt(2), -2.0 / math.sqrt(2))),
        (50.0, 0.0, (1.5, 0.0)),
        (300.0, 0.0, (3.0, 0.0)),
        (-50.0, 0.0, (-1.5, 0.0)),
    ],
)
def test_cursor_target_center_cardinals_diagonals_radius_and_negative_coordinates(
    dx: float, dy: float, expected: tuple[float, float]
) -> None:
    assert _module().cursor_target(dx, dy, 100.0) == pytest.approx(expected)


def test_cursor_target_is_continuous_near_angle_boundary() -> None:
    module = _module()
    first = module.cursor_target(100.0 * math.cos(-0.0001), 100.0 * math.sin(-0.0001), 100.0)
    second = module.cursor_target(100.0 * math.cos(0.0001), 100.0 * math.sin(0.0001), 100.0)

    assert math.hypot(second[0] - first[0], second[1] - first[1]) < 0.001


@pytest.mark.parametrize(
    ("dx", "dy", "radius"),
    [
        (math.nan, 0.0, 1.0),
        (0.0, math.inf, 1.0),
        (0.0, 0.0, math.nan),
        (0.0, 0.0, math.inf),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
    ],
)
def test_cursor_target_rejects_invalid_numeric_inputs(dx: float, dy: float, radius: float) -> None:
    with pytest.raises(ValueError):
        _module().cursor_target(dx, dy, radius)


@pytest.mark.parametrize(
    ("dx", "dy"),
    [
        (sys.float_info.max, 0.0),
        (-sys.float_info.max, 0.0),
        (sys.float_info.max, sys.float_info.max),
        (-sys.float_info.max, sys.float_info.max),
    ],
)
def test_cursor_target_largest_finite_inputs_remain_finite(dx: float, dy: float) -> None:
    target = _module().cursor_target(dx, dy, 1.0)

    assert all(math.isfinite(value) for value in target)
    assert abs(target[0]) <= 3.0
    assert abs(target[1]) <= 2.0


def test_controller_uses_exact_60ms_exponential_smoothing_and_33ms_schedule() -> None:
    clock = Clock()
    controller, scheduler, _, observed = make_controller(_module().CursorPoint(200, 100), clock=clock)

    controller.start()
    assert [delay for delay, _ in scheduler.pending] == [33]
    clock.value = 0.060
    scheduler.run_one()

    alpha = 1.0 - math.exp(-1.0)
    assert observed == [pytest.approx((3.0 * alpha, 0.0))]
    assert [delay for delay, _ in scheduler.pending] == [6]


def test_controller_converges_monotonically_without_overshoot_and_time_steps_agree() -> None:
    module = _module()

    def advance(step: float, count: int) -> tuple[float, float]:
        clock = Clock()
        controller, scheduler, _, observed = make_controller(module.CursorPoint(200, 100), clock=clock)
        controller.start()
        for _ in range(count):
            clock.value += step
            scheduler.run_one()
        return observed[-1]

    clock = Clock()
    controller, scheduler, _, observed = make_controller(module.CursorPoint(200, 100), clock=clock)
    controller.start()
    for _ in range(5):
        clock.value += 0.020
        scheduler.run_one()
    values = [x for x, _ in observed]
    assert values == sorted(values)
    assert all(0.0 < value < 3.0 for value in values)
    assert advance(0.020, 5) == pytest.approx(advance(0.010, 10), abs=0.006)


def test_controller_clamps_a_long_frame_to_100ms() -> None:
    clock = Clock()
    controller, scheduler, _, observed = make_controller(_module().CursorPoint(200, 100), clock=clock)
    controller.start()
    clock.value = 10.0
    scheduler.run_one()

    assert observed[-1][0] == pytest.approx(3.0 * (1.0 - math.exp(-0.100 / 0.060)))


def test_failed_cursor_acquisition_converges_to_center() -> None:
    module = _module()
    clock = Clock()
    controller, scheduler, provider, observed = make_controller(module.CursorPoint(200, 100), clock=clock)
    controller.start()
    clock.value = 0.060
    scheduler.run_one()
    first = observed[-1][0]
    provider.point = None
    clock.value = 0.120
    scheduler.run_one()

    assert 0.0 < observed[-1][0] < first


def test_activation_radius_scales_with_display_height() -> None:
    module = _module()
    clock = Clock()
    first, first_scheduler, _, first_observed = make_controller(
        module.CursorPoint(200, 100), display_height=280.0, clock=clock
    )
    second, second_scheduler, _, second_observed = make_controller(
        module.CursorPoint(200, 100), display_height=560.0, clock=clock
    )
    first.start()
    second.start()
    clock.value = 0.060
    first_scheduler.run_one()
    second_scheduler.run_one()

    alpha = 1.0 - math.exp(-1.0)
    assert first_observed[-1] == pytest.approx((3.0 * alpha, 0.0))
    assert second_observed[-1] == pytest.approx((1.5 * alpha, 0.0))


def test_controller_accepts_largest_finite_display_height_with_finite_target() -> None:
    module = _module()
    clock = Clock()
    controller, scheduler, provider, observed = make_controller(
        module.CursorPoint(sys.float_info.max, 0),
        geometry=module.EyeGeometry(0, 0, sys.float_info.max),
        clock=clock,
    )
    controller.start()
    clock.value = 0.060
    scheduler.run_one()

    assert provider.calls == 1
    assert all(math.isfinite(value) for value in observed[-1])
    assert observed[-1][0] == pytest.approx(3.0 * (1.0 - math.exp(-1.0)))


def test_controller_reads_moved_midpoint_and_resized_height_each_tick() -> None:
    module = _module()
    clock = Clock()
    scheduler = FakeScheduler()
    provider = FakeCursorProvider(module.CursorPoint(200, 100))
    geometry_provider = FakeGeometryProvider(module.EyeGeometry(100, 100, 280))
    observed: list[tuple[float, float]] = []
    controller = module.EyeMotionController(
        scheduler,
        scheduler.cancel,
        provider,
        geometry_provider,
        lambda x, y: observed.append((x, y)),
        clock=clock,
    )
    controller.start()
    clock.value = 0.060
    scheduler.run_one()
    first = observed[-1][0]
    geometry_provider.geometry = module.EyeGeometry(150, 100, 560)
    clock.value = 0.120
    scheduler.run_one()

    alpha = 1.0 - math.exp(-1.0)
    assert observed[-1][0] == pytest.approx(first + alpha * (0.75 - first))
    assert provider.calls == 2
    assert geometry_provider.calls == 2


def test_lifecycle_is_idempotent_pause_preserves_pose_and_stop_prevents_rescheduling() -> None:
    module = _module()
    clock = Clock()
    controller, scheduler, _, observed = make_controller(module.CursorPoint(200, 100), clock=clock)
    controller.start()
    controller.start()
    controller.resume()
    assert len(scheduler.pending) == 1

    clock.value = 0.060
    scheduler.run_one()
    pose = observed[-1]
    assert len(scheduler.pending) == 1
    controller.pause()
    controller.pause()
    assert len(scheduler.cancelled) == 1
    assert controller.pose == pytest.approx(pose)
    controller.resume()
    controller.resume()
    assert len(scheduler.pending) == 2
    controller.stop()
    assert len(scheduler.cancelled) == 2
    pending_after_stop = list(scheduler.pending)
    controller.start()
    controller.resume()
    assert scheduler.pending == pending_after_stop
    while scheduler.pending:
        scheduler.run_one()
    assert not scheduler.pending
    assert observed == [pytest.approx(pose)]


def test_synchronous_scheduler_start_fails_terminally_without_recursion_or_fake_token() -> None:
    module = _module()
    scheduler = ControlledScheduler()
    scheduler.mode = "synchronous"
    provider = FakeCursorProvider(module.CursorPoint(200, 100))
    controller = module.EyeMotionController(
        scheduler,
        scheduler.cancel,
        provider,
        lambda: module.EyeGeometry(100, 100, 280),
        lambda _x, _y: None,
        clock=Clock(),
    )

    with pytest.raises(RuntimeError, match="synchronously"):
        controller.start()

    controller.start()
    controller.stop()
    assert scheduler.calls == 1
    assert provider.calls == 0
    assert scheduler.pending == []
    assert scheduler.cancelled == []


def test_synchronous_scheduler_during_tick_fails_terminally_without_nested_sample() -> None:
    module = _module()
    scheduler = ControlledScheduler()
    provider = FakeCursorProvider(module.CursorPoint(200, 100))
    controller = module.EyeMotionController(
        scheduler,
        scheduler.cancel,
        provider,
        lambda: module.EyeGeometry(100, 100, 280),
        lambda _x, _y: None,
        clock=Clock(),
    )
    controller.start()
    scheduler.mode = "synchronous"

    with pytest.raises(RuntimeError, match="synchronously"):
        scheduler.run_one()

    controller.start()
    controller.stop()
    assert scheduler.calls == 2
    assert provider.calls == 1
    assert scheduler.pending == []
    assert scheduler.cancelled == []


@pytest.mark.parametrize("mode", ["raise_before_queue", "raise_after_queue"])
def test_scheduler_exception_terminally_invalidates_any_queued_callback(
    mode: str,
) -> None:
    module = _module()
    scheduler = ControlledScheduler()
    scheduler.mode = mode
    provider = FakeCursorProvider(module.CursorPoint(200, 100))
    controller = module.EyeMotionController(
        scheduler,
        scheduler.cancel,
        provider,
        lambda: module.EyeGeometry(100, 100, 280),
        lambda _x, _y: None,
        clock=Clock(),
    )

    with pytest.raises(RuntimeError, match="scheduler failed"):
        controller.start()
    stale_callbacks = [entry[1][1] for entry in scheduler.pending]
    scheduler.pending.clear()
    for callback in stale_callbacks:
        callback()

    controller.start()
    assert scheduler.calls == 1
    assert provider.calls == 0
    assert scheduler.cancelled == []


def test_stale_callback_after_pause_resume_cannot_sample_or_replace_current_schedule() -> None:
    module = _module()
    clock = Clock()
    controller, scheduler, provider, observed = make_controller(module.CursorPoint(200, 100), clock=clock)
    controller.start()
    stale_callback = scheduler.pending[0][1][1]
    controller.pause()
    controller.resume()
    current_token = scheduler.pending[1][1][0]
    pending_before = list(scheduler.pending)

    stale_callback()

    assert provider.calls == 0
    assert observed == []
    assert scheduler.pending == pending_before
    controller.pause()
    assert scheduler.cancelled[-1] is current_token


def test_stable_input_suppresses_redundant_callbacks_but_continues_sampling() -> None:
    module = _module()
    clock = Clock()
    controller, scheduler, provider, observed = make_controller(module.CursorPoint(200, 100), clock=clock)
    controller.start()
    for _ in range(20):
        clock.value += 0.060
        scheduler.run_one()

    callback_count = len(observed)
    sample_count = provider.calls
    for _ in range(3):
        clock.value += 0.060
        scheduler.run_one()

    assert provider.calls == sample_count + 3
    assert len(observed) == callback_count


class AdvancingScheduler:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.pending: list[tuple[int, object, object]] = []
        self.cancelled: list[object] = []
        self.delays: list[int] = []

    def __call__(self, delay_ms: int, callback):
        token = object()
        self.delays.append(delay_ms)
        self.pending.append((delay_ms, token, callback))
        return token

    def cancel(self, token: object) -> None:
        self.cancelled.append(token)

    def run_one(self) -> None:
        delay_ms, token, callback = self.pending.pop(0)
        if token in self.cancelled:
            return
        self.clock.value += delay_ms / 1000.0
        callback()


@pytest.mark.parametrize("work_ms", [0, 7, 20])
def test_controller_absolute_deadline_preserves_start_cadence(work_ms: int) -> None:
    module = _module()
    clock = Clock()
    scheduler = AdvancingScheduler(clock)
    starts: list[float] = []

    class WorkingCursor:
        def position(self):
            starts.append(clock.value)
            clock.value += work_ms / 1000.0
            return module.CursorPoint(200, 100)

    controller = module.EyeMotionController(
        scheduler,
        scheduler.cancel,
        WorkingCursor(),
        lambda: module.EyeGeometry(100, 100, 280),
        lambda _x, _y: None,
        clock=clock,
    )

    controller.start()
    for _ in range(4):
        scheduler.run_one()

    assert starts == pytest.approx([0.033, 0.066, 0.099, 0.132])
    assert scheduler.delays[:4] == [33] + [33 - work_ms] * 3
    assert all(delay >= 0 for delay in scheduler.delays)
    assert len(scheduler.pending) == 1


def test_controller_coalesces_missed_deadline_without_catch_up_burst() -> None:
    module = _module()
    clock = Clock()
    scheduler = AdvancingScheduler(clock)
    starts: list[float] = []
    observed: list[tuple[float, float]] = []

    class SlowCursor:
        def position(self):
            starts.append(clock.value)
            clock.value += 0.040
            return module.CursorPoint(200, 100)

    controller = module.EyeMotionController(
        scheduler,
        scheduler.cancel,
        SlowCursor(),
        lambda: module.EyeGeometry(100, 100, 280),
        lambda x, y: observed.append((x, y)),
        clock=clock,
    )

    controller.start()
    scheduler.run_one()
    scheduler.run_one()

    assert starts == pytest.approx([0.033, 0.099])
    assert scheduler.delays[:3] == [33, 26, 26]
    assert 0 not in scheduler.delays
    assert len(scheduler.pending) == 1
    assert observed[-1][0] == pytest.approx(
        3.0 * (1.0 - math.exp(-0.099 / 0.060))
    )


def test_controller_coalesces_a_delayed_callback_to_one_future_deadline() -> None:
    module = _module()
    clock = Clock()
    controller, scheduler, provider, _ = make_controller(
        module.CursorPoint(200, 100), clock=clock
    )

    controller.start()
    clock.value = 0.120
    scheduler.run_one()

    assert provider.calls == 1
    assert [delay for delay, _ in scheduler.pending] == [12]
    assert all(delay >= 0 for delay, _ in scheduler.pending)


def test_controller_never_rounds_a_future_deadline_to_zero_delay() -> None:
    module = _module()
    clock = Clock()
    scheduler = AdvancingScheduler(clock)

    class NearDeadlineCursor:
        def position(self):
            clock.value = 0.0659999999995
            return module.CursorPoint(200, 100)

    controller = module.EyeMotionController(
        scheduler,
        scheduler.cancel,
        NearDeadlineCursor(),
        lambda: module.EyeGeometry(100, 100, 280),
        lambda _x, _y: None,
        clock=clock,
    )

    controller.start()
    scheduler.run_one()

    assert scheduler.delays == [33, 1]


def test_synchronize_pose_requires_the_actual_paused_state() -> None:
    module = _module()
    controller, scheduler, _, observed = make_controller(module.CursorPoint(100, 100))

    with pytest.raises(RuntimeError):
        controller.synchronize_pose(1.0, -1.0)
    controller.start()
    with pytest.raises(RuntimeError):
        controller.synchronize_pose(1.0, -1.0)
    controller.pause()

    scheduled_before = list(scheduler.pending)
    controller.synchronize_pose(1.0, -1.0)

    assert controller.pose == (1.0, -1.0)
    assert observed == []
    assert scheduler.pending == scheduled_before
    controller.stop()
    with pytest.raises(RuntimeError):
        controller.synchronize_pose(0.0, 0.0)


@pytest.mark.parametrize(
    ("eye_x", "eye_y"),
    [
        (math.nan, 0.0),
        (math.inf, 0.0),
        (0.0, -math.inf),
        (3.000001, 0.0),
        (-3.000001, 0.0),
        (0.0, 2.000001),
        (0.0, -2.000001),
        (Decimal("1e999999"), 0.0),
    ],
)
def test_synchronize_pose_rejects_nonfinite_overflow_and_out_of_range(
    eye_x: object, eye_y: object
) -> None:
    module = _module()
    controller, _, _, _ = make_controller(module.CursorPoint(100, 100))
    controller.start()
    controller.pause()

    with pytest.raises(ValueError):
        controller.synchronize_pose(eye_x, eye_y)


def test_synchronize_center_resumes_one_fresh_phase_without_emitting() -> None:
    module = _module()
    clock = Clock()
    controller, scheduler, _, observed = make_controller(
        module.CursorPoint(100, 100), clock=clock
    )
    controller.start()
    controller.pause()
    controller.synchronize_pose(0.0, 0.0)
    pending_before = len(scheduler.pending)

    controller.resume()
    controller.resume()

    assert controller.pose == (0.0, 0.0)
    assert observed == []
    assert len(scheduler.pending) == pending_before + 1
    assert scheduler.pending[-1][0] == 33


def test_center_target_snaps_and_emits_exact_center_once() -> None:
    module = _module()
    clock = Clock()
    controller, scheduler, _, observed = make_controller(None, clock=clock)
    controller.start()
    controller.pause()
    controller.synchronize_pose(0.005, -0.005)
    controller.resume()
    clock.value = 0.033

    while scheduler.pending and scheduler.pending[0][1][0] in scheduler.cancelled:
        scheduler.pending.pop(0)
    scheduler.run_one()
    clock.value = 0.066
    scheduler.run_one()

    assert controller.pose == (0.0, 0.0)
    assert observed == [(0.0, 0.0)]

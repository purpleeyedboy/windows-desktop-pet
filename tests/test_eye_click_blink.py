from __future__ import annotations

from collections.abc import Callable

from desktop_pet.assets import load_neutral_eye_source_probe
from desktop_pet.blink import (
    MAX_BLINK_INTERVAL_SECONDS,
    MIN_BLINK_INTERVAL_SECONDS,
    NaturalBlinkMotion,
)
from desktop_pet.eye_follow import CursorPoint
from desktop_pet.eye_runtime import RuntimeEyeSession, SessionResult
from desktop_pet.head_neck_deformation import (
    ContinuousHeadNeckCompositor,
    HeadPose,
)
from desktop_pet.model import ACTIONS, ActionCycle, Rect
from desktop_pet.window import PetWindow, _CachedCenterCompositor


class Clock:
    def __init__(self, value: float = 10.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class Scheduler:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.pending: list[tuple[object, Callable[[], None]]] = []
        self.cancelled: list[object] = []

    def __call__(self, _delay_ms: int, callback: Callable[[], None]) -> object:
        token = object()
        self.pending.append((token, callback))
        return token

    def cancel(self, token: object) -> None:
        self.cancelled.append(token)

    def run_next(self, advance_ms: int = 33) -> None:
        while self.pending:
            token, callback = self.pending.pop(0)
            if token in self.cancelled:
                continue
            self.clock.value += advance_ms / 1000.0
            callback()
            return
        raise AssertionError("no live blink callback")


class Cursor:
    def __init__(self, point: CursorPoint) -> None:
        self.point = point

    def position(self) -> CursorPoint:
        return self.point


class BlinkRequestRecorder:
    def __init__(self) -> None:
        self.calls = 0

    def request_blink(self) -> SessionResult:
        self.calls += 1
        return SessionResult.ACCEPTED


def test_cached_window_compositor_preserves_real_blink_and_eye_regions() -> None:
    head = ContinuousHeadNeckCompositor(load_neutral_eye_source_probe())
    cached = _CachedCenterCompositor(head)

    assert len(cached.eye_interaction_boxes) == 2
    assert callable(getattr(cached, "compose_head_blink", None))

    center = cached.compose_head_blink(0.0, 0.0, HeadPose(0.0, 0.0), 0.0)
    closed = cached.compose_head_blink(0.0, 0.0, HeadPose(0.0, 0.0), 1.0)

    assert center is cached.center_frame
    assert closed.tobytes() != center.tobytes()


def test_runtime_click_request_restarts_one_blink_without_pausing_follow() -> None:
    clock = Clock()
    scheduler = Scheduler(clock)
    base = load_neutral_eye_source_probe()
    compositor = _CachedCenterCompositor(
        ContinuousHeadNeckCompositor(base)
    )
    midpoint_x, midpoint_y = compositor.eye_midpoint
    motion = NaturalBlinkMotion(lambda _low, _high: 12.0)
    displayed: list[object] = []
    session = RuntimeEyeSession(
        compositor=compositor,
        cursor_provider=Cursor(
            CursorPoint(round(midpoint_x), round(midpoint_y))
        ),
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
        head_follow=True,
        blink_motion=motion,
    )

    assert session.start() is SessionResult.ACCEPTED
    original_cooldown = motion.next_blink_at
    assert original_cooldown == 22.0

    assert session.request_blink() is SessionResult.ACCEPTED
    assert session.state == "following"
    assert motion.next_blink_at == 10.0

    scheduler.run_next()
    assert session.state == "following"
    assert len(displayed) == 2
    assert displayed[-1].tobytes() != displayed[0].tobytes()

    for _ in range(6):
        scheduler.run_next()

    assert motion.next_blink_at is not None
    assert clock.value + MIN_BLINK_INTERVAL_SECONDS <= motion.next_blink_at
    assert motion.next_blink_at <= clock.value + MAX_BLINK_INTERVAL_SECONDS


def test_eye_click_routes_to_blink_body_click_keeps_action_and_drag_is_inert() -> None:
    base = load_neutral_eye_source_probe()
    window = object.__new__(PetWindow)
    window._window_rect = Rect(-300, 120, 256, 384)
    window._eye_source_size = base.source_size
    window._eye_interaction_boxes = base.eye_interaction_boxes
    window._legacy_fallback = False
    session = BlinkRequestRecorder()
    window.eye_session = session
    actions: list[str] = []
    window.trigger_next_action = lambda: actions.append("action")

    left, top, right, bottom = base.eye_interaction_boxes[0]
    eye_point = (
        window._window_rect.x
        + round((left + right) * window._window_rect.width / 1024),
        window._window_rect.y
        + round((top + bottom) * window._window_rect.height / 1536),
    )
    body_point = (
        window._window_rect.x + window._window_rect.width // 2,
        window._window_rect.y + round(650 * window._window_rect.height / 768),
    )

    window.handle_left_release(eye_point, (eye_point[0] + 1, eye_point[1] + 1))
    window.handle_left_release(body_point, (body_point[0] + 1, body_point[1]))
    window.handle_left_release(eye_point, (eye_point[0] + 8, eye_point[1]))

    assert session.calls == 1
    assert actions == ["action"]


def test_eye_click_never_falls_through_to_body_action_during_fallback() -> None:
    base = load_neutral_eye_source_probe()
    window = object.__new__(PetWindow)
    window._window_rect = Rect(100, 200, 512, 768)
    window._eye_source_size = base.source_size
    window._eye_interaction_boxes = base.eye_interaction_boxes
    window._legacy_fallback = True
    session = BlinkRequestRecorder()
    window.eye_session = session
    actions: list[str] = []
    window.trigger_next_action = lambda: actions.append("action")

    left, top, right, bottom = base.eye_interaction_boxes[1]
    point = ((left + right) // 2 + 100, (top + bottom) // 2 + 200)
    window.handle_left_release(point, point)

    assert session.calls == 0
    assert actions == []

from __future__ import annotations

from dataclasses import dataclass

import pytest

from desktop_pet.eye_runtime import RuntimeEyeSession, SessionResult
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.idle_head_tilt import (
    APPROACH_SECONDS,
    ARC_TRAVEL_SECONDS,
    MIN_HOLD_SECONDS,
    IdleHeadTiltMotion,
)
from desktop_pet.model import ACTIONS, ActionCycle


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Cursor:
    def position(self):
        return None


@dataclass
class Rect:
    x: int = 0
    y: int = 0
    width: int = 187
    height: int = 280


class RecordingHeadCompositor:
    source_size = (512, 768)
    eye_midpoint = (122.5, 349.0)

    def __init__(self) -> None:
        self.calls: list[tuple[float, float, HeadPose]] = []

    def compose(self, eye_x: float, eye_y: float):
        return (eye_x, eye_y)

    def compose_head(self, eye_x: float, eye_y: float, pose: HeadPose):
        self.calls.append((eye_x, eye_y, pose))
        return (eye_x, eye_y, pose)


def make_session(clock: Clock, compositor: RecordingHeadCompositor):
    scheduled = []
    displayed = []
    motion = IdleHeadTiltMotion(
        uniform=lambda low, high: low,
        choice=lambda _: "left",
    )
    frames = {action: tuple(object() for _ in range(6)) for action in ACTIONS}
    session = RuntimeEyeSession(
        compositor=compositor,
        cursor_provider=Cursor(),
        rect_provider=Rect,
        display=displayed.append,
        scheduler=lambda delay, callback: scheduled.append(callback) or callback,
        cancel=lambda token: None,
        clock=clock,
        on_disabled=lambda: None,
        action_cycle=ActionCycle(),
        physical_frames=frames,
        play_action=lambda action: True,
        cancel_action=lambda action: True,
        choose_phrase=lambda action: action,
        present_phrase=lambda phrase: None,
        on_action_failed=lambda action, reason: None,
        head_follow=True,
        idle_tilt_motion=motion,
    )
    return session, motion, displayed


def test_idle_tilt_combines_with_current_eye_and_head_follow_pose() -> None:
    clock = Clock()
    compositor = RecordingHeadCompositor()
    session, motion, _ = make_session(clock, compositor)
    assert session.start() is SessionResult.ACCEPTED
    session._following_coordinated_pose_changed(1.4, -0.7, 0.3, -0.2)

    assert motion.next_action_at == pytest.approx(35.0)
    clock.now = 35.55
    session._following_ambient_pulse()

    eye_x, eye_y, pose = compositor.calls[-1]
    assert (eye_x, eye_y) == (1.4, -0.7)
    assert (pose.x, pose.y) == (0.3, -0.2)
    assert pose.rotation_degrees == pytest.approx(-18.0)
    assert pose.arc == 0.0
    assert session.state == "following"


def test_pointer_press_interrupts_tilt_and_restarts_its_cooldown() -> None:
    clock = Clock()
    compositor = RecordingHeadCompositor()
    session, motion, _ = make_session(clock, compositor)
    session.start()
    clock.now = 35.4
    session._following_ambient_pulse()
    assert compositor.calls[-1][2].rotation_degrees < 0.0

    clock.now = 36.0
    assert session.interrupt_idle() is SessionResult.ACCEPTED
    assert compositor.calls[-1][2].rotation_degrees == 0.0
    assert compositor.calls[-1][2].arc == 0.0
    assert motion.next_action_at == pytest.approx(71.0)


@pytest.mark.parametrize(
    ("mode", "expected_rotation"),
    (("left", -18.0), ("right", 18.0)),
)
def test_named_tilt_request_plays_the_selected_direction_immediately(
    mode: str,
    expected_rotation: float,
) -> None:
    clock = Clock()
    compositor = RecordingHeadCompositor()
    session, motion, _ = make_session(clock, compositor)
    session.start()

    assert session.request_idle_tilt(mode) is SessionResult.ACCEPTED
    assert motion.active_mode == mode
    clock.now = APPROACH_SECONDS
    session._following_ambient_pulse()

    assert compositor.calls[-1][2].rotation_degrees == expected_rotation
    assert compositor.calls[-1][2].arc == 0.0


def test_named_arc_request_plays_the_selected_arc_mode() -> None:
    clock = Clock()
    compositor = RecordingHeadCompositor()
    session, motion, _ = make_session(clock, compositor)
    session.start()
    assert session.request_idle_tilt("left_arc_right") is SessionResult.ACCEPTED
    assert motion.active_mode == "left_arc_right"

    clock.now = APPROACH_SECONDS + MIN_HOLD_SECONDS + ARC_TRAVEL_SECONDS / 2.0
    session._following_ambient_pulse()

    assert compositor.calls[-1][2].rotation_degrees == pytest.approx(0.0)
    assert compositor.calls[-1][2].arc == pytest.approx(1.0)


def test_named_tilt_rejects_invalid_mode_and_non_following_state() -> None:
    clock = Clock()
    compositor = RecordingHeadCompositor()
    session, _, _ = make_session(clock, compositor)

    assert session.request_idle_tilt("left") is SessionResult.REJECTED
    with pytest.raises(ValueError, match="mode"):
        session.request_idle_tilt("unknown")


def test_idle_tilt_is_rejected_without_head_following() -> None:
    clock = Clock()
    compositor = RecordingHeadCompositor()
    frames = {action: tuple(object() for _ in range(6)) for action in ACTIONS}
    with pytest.raises(ValueError, match="requires head following"):
        RuntimeEyeSession(
            compositor=compositor,
            cursor_provider=Cursor(),
            rect_provider=Rect,
            display=lambda frame: None,
            scheduler=lambda delay, callback: callback,
            cancel=lambda token: None,
            clock=clock,
            on_disabled=lambda: None,
            action_cycle=ActionCycle(),
            physical_frames=frames,
            play_action=lambda action: True,
            cancel_action=lambda action: True,
            choose_phrase=lambda action: action,
            present_phrase=lambda phrase: None,
            on_action_failed=lambda action, reason: None,
            idle_tilt_motion=IdleHeadTiltMotion(),
        )

from __future__ import annotations

import math

import pytest

from desktop_pet.idle_head_tilt import (
    APPROACH_SECONDS,
    ARC_TRAVEL_SECONDS,
    IdleHeadTiltMotion,
    IdleTiltPose,
    MAX_HOLD_SECONDS,
    MAX_TILT_DEGREES,
    MIN_HOLD_SECONDS,
    MIN_TILT_DEGREES,
    RETURN_SECONDS,
    TILT_MODES,
)


def lowest_uniform(low: float, high: float) -> float:
    return low


def test_first_sample_arms_an_occasional_cooldown() -> None:
    calls: list[tuple[float, float]] = []

    def uniform(low: float, high: float) -> float:
        calls.append((low, high))
        return low

    motion = IdleHeadTiltMotion(uniform=uniform)
    assert motion.sample(10.0) == IdleTiltPose()
    assert motion.next_action_at == pytest.approx(45.0)
    assert calls == [(35.0, 80.0)]


@pytest.mark.parametrize(
    ("mode", "expected_tilt"),
    (("left", -30.0), ("right", 30.0)),
)
def test_single_direction_modes_approach_hold_and_return(
    mode: str,
    expected_tilt: float,
) -> None:
    motion = IdleHeadTiltMotion(
        uniform=lowest_uniform,
        choice=lambda _: mode,
    )
    motion.reset(0.0)
    start = motion.next_action_at
    assert start is not None
    assert motion.sample(start + APPROACH_SECONDS) == IdleTiltPose(expected_tilt)
    assert motion.sample(
        start + APPROACH_SECONDS + MIN_HOLD_SECONDS / 2.0
    ) == IdleTiltPose(expected_tilt)
    returning = motion.sample(
        start + APPROACH_SECONDS + MIN_HOLD_SECONDS + RETURN_SECONDS / 2.0
    )
    assert returning.rotation_degrees == pytest.approx(expected_tilt / 2.0)
    assert returning.arc == 0.0


def test_arc_mode_moves_over_a_large_lifted_arc_and_holds_right() -> None:
    motion = IdleHeadTiltMotion(
        uniform=lowest_uniform,
        choice=lambda _: "left_arc_right",
    )
    motion.reset(0.0)
    start = motion.next_action_at
    assert start is not None
    arc_start = start + APPROACH_SECONDS + MIN_HOLD_SECONDS
    midpoint = motion.sample(arc_start + ARC_TRAVEL_SECONDS / 2.0)
    assert midpoint.rotation_degrees == pytest.approx(0.0, abs=1e-12)
    assert midpoint.arc == pytest.approx(1.0)
    right_hold = motion.sample(arc_start + ARC_TRAVEL_SECONDS + 0.4)
    assert right_hold == IdleTiltPose(30.0)


def test_completed_action_returns_to_center_and_restarts_cooldown() -> None:
    motion = IdleHeadTiltMotion(
        uniform=lowest_uniform,
        choice=lambda _: "left",
    )
    motion.reset(0.0)
    start = motion.next_action_at
    assert start is not None
    finished = (
        start + APPROACH_SECONDS + MIN_HOLD_SECONDS + RETURN_SECONDS + 1e-6
    )
    assert motion.sample(finished) == IdleTiltPose()
    assert motion.active_mode is None
    assert motion.next_action_at == pytest.approx(finished + 35.0)


def test_reset_cancels_an_active_motion() -> None:
    values = iter((35.0, MIN_TILT_DEGREES, MIN_HOLD_SECONDS, 40.0))
    motion = IdleHeadTiltMotion(
        uniform=lambda low, high: next(values),
        choice=lambda _: "left",
    )
    motion.reset(0.0)
    assert motion.sample(35.4).rotation_degrees < 0.0
    motion.reset(36.0)
    assert motion.sample(36.1) == IdleTiltPose()
    assert motion.next_action_at == pytest.approx(76.0)


@pytest.mark.parametrize(
    "pose",
    (
        lambda: IdleTiltPose(50.01, 0.0),
        lambda: IdleTiltPose(0.0, -0.01),
        lambda: IdleTiltPose(0.0, 1.01),
        lambda: IdleTiltPose(math.nan, 0.0),
    ),
)
def test_idle_pose_rejects_invalid_values(pose) -> None:
    with pytest.raises(ValueError):
        pose()


def test_motion_rejects_invalid_random_sources() -> None:
    motion = IdleHeadTiltMotion(uniform=lambda low, high: high + 1.0)
    with pytest.raises(ValueError):
        motion.reset(0.0)

    motion = IdleHeadTiltMotion(
        uniform=lowest_uniform,
        choice=lambda _: "unknown",
    )
    motion._next_action_at = 0.0
    with pytest.raises(ValueError):
        motion.sample(0.0)


def test_public_timing_and_mode_ranges_match_the_idle_contract() -> None:
    assert set(TILT_MODES) == {"left", "right", "left_arc_right"}
    assert MIN_HOLD_SECONDS == 0.8
    assert MAX_HOLD_SECONDS == 2.0
    assert MIN_TILT_DEGREES == 30.0
    assert MAX_TILT_DEGREES == 50.0

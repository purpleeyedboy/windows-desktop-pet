from __future__ import annotations

from random import Random

import pytest

from desktop_pet.idle_lick import (
    CONTACT_SECONDS,
    IDLE_INTERVAL_MAX_SECONDS,
    IDLE_INTERVAL_MIN_SECONDS,
    LICK_SECONDS,
    RAISE_SECONDS,
    RETRACT_SECONDS,
    LOWER_SECONDS,
    IdleLickMotion,
    LickPose,
)


class BoundaryRng:
    def __init__(self, count: int, side: str = "left") -> None:
        self.count = count
        self.side = side

    def uniform(self, low: float, high: float) -> float:
        assert (low, high) == (
            IDLE_INTERVAL_MIN_SECONDS,
            IDLE_INTERVAL_MAX_SECONDS,
        )
        return low

    def choice(self, values: tuple[str, ...]) -> str:
        assert self.side in values
        return self.side

    def randint(self, low: int, high: int) -> int:
        assert (low, high) == (3, 20)
        return self.count


def qualify(motion: IdleLickMotion, start: float = 0.0) -> float:
    for step in range(21):
        motion.sample(start + step / 10, (0.1, -0.1))
    return start + 2.0


def wait_until(motion: IdleLickMotion, start: float, finish: float) -> LickPose:
    pose = LickPose()
    step = start + 0.1
    while step < finish - 1e-9:
        pose = motion.sample(step, (0.1, -0.1))
        step += 0.1
    return motion.sample(finish, (0.1, -0.1))


@pytest.mark.parametrize("side", ["left", "right"])
def test_selects_each_lick_side_after_the_documented_idle_threshold(side: str) -> None:
    motion = IdleLickMotion(rng=BoundaryRng(3, side))
    stable_at = qualify(motion)

    before = wait_until(
        motion,
        stable_at,
        stable_at + IDLE_INTERVAL_MIN_SECONDS - 0.001,
    )
    started = motion.sample(stable_at + IDLE_INTERVAL_MIN_SECONDS, (0.1, -0.1))

    assert before == LickPose()
    assert started.side == side
    assert started.phase == "raise"
    assert motion.planned_licks == 3


@pytest.mark.parametrize("count", [3, 20])
def test_inclusive_lick_count_boundaries_complete_exactly(count: int) -> None:
    motion = IdleLickMotion(rng=BoundaryRng(count))
    stable_at = qualify(motion)
    now = stable_at + IDLE_INTERVAL_MIN_SECONDS
    wait_until(motion, stable_at, now)
    cycle = LICK_SECONDS + CONTACT_SECONDS + RETRACT_SECONDS
    now += RAISE_SECONDS
    motion.sample(now, (0.0, 0.0))
    for _ in range(count):
        now += cycle
        motion.sample(now, (0.0, 0.0))

    now += LOWER_SECONDS
    motion.sample(now, (0.0, 0.0))
    assert motion.completed_licks == count
    assert motion.state == "waiting"
    assert motion.pose == LickPose()
    assert 3 <= motion.planned_licks <= 20


def test_unstable_or_ineligible_input_never_accumulates_idle_time() -> None:
    motion = IdleLickMotion(rng=BoundaryRng(3))
    for step in range(800):
        now = step / 10
        target = (0.0, 0.0) if step % 2 else (0.03, 0.03)
        motion.sample(now, target, eligible=step % 7 != 0)

    assert motion.state == "waiting"
    assert motion.pose == LickPose()


def test_interrupt_exits_at_next_phase_boundary_not_at_end_of_round() -> None:
    motion = IdleLickMotion(rng=BoundaryRng(20))
    stable_at = qualify(motion)
    now = stable_at + IDLE_INTERVAL_MIN_SECONDS
    wait_until(motion, stable_at, now)
    motion.interrupt(now + RAISE_SECONDS / 2)

    still_safe = motion.sample(now + RAISE_SECONDS - 0.001, (0.0, 0.0))
    neutral = motion.sample(now + RAISE_SECONDS, (0.0, 0.0))

    assert still_safe.phase == "raise"
    assert neutral == LickPose()
    assert motion.completed_licks == 0
    assert motion.state == "waiting"


def test_clock_discontinuities_restore_neutral_and_do_not_burst_replay() -> None:
    motion = IdleLickMotion(rng=BoundaryRng(20))
    stable_at = qualify(motion)
    now = stable_at + IDLE_INTERVAL_MIN_SECONDS
    assert wait_until(motion, stable_at, now).phase == "raise"

    assert motion.sample(now + 3600.0, (0.0, 0.0)) == LickPose()
    assert motion.sample(now + 3600.1, (0.0, 0.0)) == LickPose()
    assert motion.sample(now - 1.0, (0.0, 0.0)) == LickPose()
    assert motion.state == "waiting"


def test_rng_failure_restores_every_pose_channel_to_neutral() -> None:
    class BrokenRng(BoundaryRng):
        def randint(self, low: int, high: int) -> int:
            raise RuntimeError("injected")

    motion = IdleLickMotion(rng=BrokenRng(3))
    stable_at = qualify(motion)
    now = stable_at + IDLE_INTERVAL_MIN_SECONDS

    assert wait_until(motion, stable_at, now) == LickPose()
    assert motion.state == "waiting"
    assert motion.pose.arm == 0.0
    assert motion.pose.tongue == 0.0
    assert motion.pose.eye_x == motion.pose.eye_y == 0.0
    assert motion.pose.head_x == motion.pose.head_y == 0.0


def test_fixed_seed_replays_side_count_and_full_state_sequence() -> None:
    def run() -> list[tuple[object, ...]]:
        motion = IdleLickMotion(rng=Random(7125))
        samples: list[tuple[object, ...]] = []
        for step in range(4000):
            pose = motion.sample(step / 30, (0.0, 0.0))
            samples.append(
                (motion.state, motion.side, motion.planned_licks, motion.completed_licks, pose)
            )
        return samples

    first = run()
    second = run()
    assert first == second
    assert any(item[1] in ("left", "right") for item in first)


def test_phase_samples_animate_raise_tongue_and_final_lower_channels() -> None:
    motion = IdleLickMotion(rng=BoundaryRng(3))
    stable_at = qualify(motion)
    now = stable_at + IDLE_INTERVAL_MIN_SECONDS
    wait_until(motion, stable_at, now)

    half_raise = motion.sample(now + RAISE_SECONDS / 2, (0.0, 0.0))
    licking = motion.sample(now + RAISE_SECONDS + LICK_SECONDS / 2, (0.0, 0.0))

    assert 0.0 < half_raise.arm < 1.0
    assert half_raise.tongue == 0.0
    assert licking.arm == 1.0
    assert 0.0 < licking.tongue < 1.0


def test_higher_priority_cancel_restores_neutral_immediately() -> None:
    motion = IdleLickMotion(rng=BoundaryRng(20))
    stable_at = qualify(motion)
    now = stable_at + IDLE_INTERVAL_MIN_SECONDS
    assert wait_until(motion, stable_at, now).phase == "raise"

    assert motion.cancel(now + RAISE_SECONDS / 2) == LickPose()
    assert motion.state == "waiting"

from __future__ import annotations

import pytest
from PIL import ImageChops

from desktop_pet.assets import load_neutral_eye_source_probe
from desktop_pet.head_neck_deformation import ContinuousHeadNeckCompositor, HeadPose
from desktop_pet.blink import (
    CLOSE_SECONDS,
    CLOSED_HOLD_SECONDS,
    MAX_BLINK_INTERVAL_SECONDS,
    MIN_BLINK_INTERVAL_SECONDS,
    OPEN_SECONDS,
    NaturalBlinkMotion,
)


def test_first_sample_only_arms_an_infrequent_blink() -> None:
    calls: list[tuple[float, float]] = []
    motion = NaturalBlinkMotion(
        lambda low, high: calls.append((low, high)) or 24.0
    )

    assert motion.sample(10.0) == 0.0
    assert motion.next_blink_at == 34.0
    assert calls == [
        (MIN_BLINK_INTERVAL_SECONDS, MAX_BLINK_INTERVAL_SECONDS)
    ]


def test_short_blink_closes_holds_and_reopens_symmetrically() -> None:
    motion = NaturalBlinkMotion(lambda _low, _high: 12.0)
    motion.reset(0.0)
    start = motion.next_blink_at
    assert start == 12.0

    assert motion.sample(start) == 0.0
    assert motion.sample(start + CLOSE_SECONDS / 2.0) == pytest.approx(0.5)
    assert motion.sample(start + CLOSE_SECONDS) == 1.0
    assert motion.sample(
        start + CLOSE_SECONDS + CLOSED_HOLD_SECONDS / 2.0
    ) == 1.0
    assert motion.sample(
        start + CLOSE_SECONDS + CLOSED_HOLD_SECONDS + OPEN_SECONDS / 2.0
    ) == pytest.approx(0.5)
    assert motion.sample(
        start + CLOSE_SECONDS + CLOSED_HOLD_SECONDS + OPEN_SECONDS
    ) == 0.0
    assert motion.next_blink_at == pytest.approx(
        start
        + CLOSE_SECONDS
        + CLOSED_HOLD_SECONDS
        + OPEN_SECONDS
        + 12.0
    )


@pytest.mark.parametrize("interval", [11.999, 36.001, float("nan")])
def test_invalid_interval_source_is_rejected(interval: float) -> None:
    motion = NaturalBlinkMotion(lambda _low, _high: interval)

    with pytest.raises(ValueError, match="blink interval"):
        motion.reset(0.0)


@pytest.mark.parametrize("now", [float("nan"), float("inf"), "bad"])
def test_invalid_clock_is_rejected(now: object) -> None:
    motion = NaturalBlinkMotion(lambda _low, _high: 20.0)

    with pytest.raises(ValueError, match="blink clock"):
        motion.sample(now)  # type: ignore[arg-type]


def test_zero_closure_is_pixel_identical_and_full_blink_is_local() -> None:
    compositor = load_neutral_eye_source_probe()
    tracked = compositor.compose(1.25, -0.75)
    open_blink = compositor.compose_blink(1.25, -0.75, 0.0)
    closed = compositor.compose_blink(1.25, -0.75, 1.0)

    assert open_blink.tobytes() == tracked.tobytes()
    assert closed.getchannel("A").tobytes() == tracked.getchannel("A").tobytes()
    difference = ImageChops.difference(tracked, closed)
    bbox = difference.getbbox(alpha_only=False)
    assert bbox is not None
    assert 50 <= bbox[0] < bbox[2] <= 190
    assert 320 <= bbox[1] < bbox[3] <= 380


def test_blink_is_composed_before_the_approved_head_warp() -> None:
    compositor = ContinuousHeadNeckCompositor(
        load_neutral_eye_source_probe()
    )
    pose = HeadPose(0.45, -0.25)

    established = compositor.compose(1.0, -0.5, pose)
    runtime_named = compositor.compose_head(1.0, -0.5, pose)
    open_blink = compositor.compose_head_blink(1.0, -0.5, pose, 0.0)
    closed = compositor.compose_head_blink(1.0, -0.5, pose, 1.0)

    assert runtime_named.tobytes() == established.tobytes()
    assert open_blink.tobytes() == established.tobytes()
    assert ImageChops.difference(established, closed).getbbox(
        alpha_only=False
    ) is not None

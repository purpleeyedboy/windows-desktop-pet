from __future__ import annotations

import pytest

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

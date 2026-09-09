from __future__ import annotations

from PIL import Image

from desktop_pet.groom_frames import GroomFramePlayer


class Rng:
    def uniform(self, low: float, high: float) -> float:
        assert (low, high) == (90.0, 300.0)
        return 90.0

    def randint(self, low: int, high: int) -> int:
        assert (low, high) == (3, 20)
        return 3


def frames() -> tuple[Image.Image, ...]:
    return tuple(
        Image.new("RGBA", (672, 768), (0 if index == 11 else index, 0, 0, 255))
        for index in range(12)
    )


def test_real_idle_trigger_ignores_cursor_motion_and_plays_full_frames() -> None:
    player = GroomFramePlayer(frames(), rng=Rng())
    assert player.sample(0.0) is None
    assert player.sample(60.0) is None
    assert player.sample(149.9) is None

    first = player.sample(150.0)

    assert first is not None and first.getpixel((0, 0))[0] == 0
    assert player.active is True
    assert player.sample(150.075).getpixel((0, 0))[0] == 1


def test_debug_trigger_repeats_only_lick_segment_then_restores_default() -> None:
    player = GroomFramePlayer(frames(), rng=Rng())
    assert player.trigger(10.0, repetitions=3) is True

    observed = []
    now = 10.0
    while player.active or not observed:
        frame = player.sample(now)
        if frame is not None:
            observed.append(frame.getpixel((0, 0))[0])
        now += 0.075

    assert observed[:3] == [0, 1, 2]
    assert observed.count(3) == 3
    assert observed[-3:] == [9, 10, 0]


def test_explicit_interaction_interrupts_and_restarts_true_idle() -> None:
    player = GroomFramePlayer(frames(), rng=Rng())
    player.trigger(10.0, repetitions=20)
    assert player.interrupt(10.2) is not None
    assert player.active is False
    assert player.sample(70.1) is None
    assert player.sample(160.1) is None
    assert player.sample(160.2) is not None


def test_rejects_noncanonical_or_wrong_canvas_frames() -> None:
    bad = list(frames())
    bad[-1] = Image.new("RGBA", (672, 768), (99, 0, 0, 255))
    try:
        GroomFramePlayer(tuple(bad), rng=Rng())
    except ValueError as error:
        assert "first and last" in str(error)
    else:
        raise AssertionError("noncanonical endpoints accepted")

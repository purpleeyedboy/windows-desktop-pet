from dataclasses import dataclass

import pytest

from desktop_pet.paw_press import (
    PawPressController,
    PawState,
    PointerBounds,
    PointerPoint,
)


@dataclass
class FakePointer:
    point: PointerPoint = PointerPoint(-100, 20)
    bounds: PointerBounds = PointerBounds(-1920, 0, 3840, 1080)
    clip: PointerBounds | None = PointerBounds(-500, 10, 900, 700)

    def __post_init__(self):
        self.events = []
        self.buttons = set()

    def cursor_position(self): return self.point
    def virtual_bounds(self): return self.bounds
    def current_clip(self): return self.clip
    def button_down(self, name): return name in self.buttons
    def capture(self): self.events.append("capture")
    def release_capture(self): self.events.append("release_capture")
    def set_clip(self, value): self.events.append(("clip", value)); self.clip = value
    def move(self, point): self.events.append(("move", point)); self.point = point
    def press_left(self): self.events.append("press"); self.buttons.add("left")
    def release_left(self): self.events.append("release"); self.buttons.discard("left")


def test_full_press_hold_push_release_restores_original_clip():
    adapter = FakePointer()
    original = adapter.clip
    controller = PawPressController(adapter, hold_seconds=.1, push_pixels=40)
    assert controller.start(0.0) is True
    assert controller.state is PawState.PRESSED
    assert adapter.events[:3] == ["capture", ("clip", original), "press"]
    controller.tick(.05)
    assert controller.state is PawState.HOLDING
    controller.tick(.11)
    assert ("move", PointerPoint(-100, 60)) in adapter.events
    controller.tick(.22)
    assert controller.state is PawState.IDLE
    assert adapter.events[-3:] == ["release", ("clip", original), "release_capture"]


def test_bounds_intersection_handles_negative_monitors_and_edges():
    a = PointerBounds(-1920, -200, 3840, 1280)
    b = PointerBounds(-500, 10, 900, 700)
    assert a.intersection(b) == b
    assert b.clamp(PointerPoint(999, -5)) == PointerPoint(399, 10)


@pytest.mark.parametrize("takeover", ["move", "right", "release"])
def test_user_takeover_immediately_cancels(takeover):
    adapter = FakePointer()
    controller = PawPressController(adapter)
    controller.start(0)
    if takeover == "move": adapter.point = PointerPoint(-80, 20)
    elif takeover == "right": adapter.buttons.add("right")
    else: adapter.buttons.discard("left")
    controller.tick(.01)
    assert controller.state is PawState.IDLE
    assert adapter.events[-1] == "release_capture"


def test_cancel_and_close_are_idempotent_even_when_release_raises():
    adapter = FakePointer()
    controller = PawPressController(adapter)
    controller.start(0)
    def broken_release():
        adapter.events.append("release-error")
        raise RuntimeError("boom")
    adapter.release_left = broken_release
    controller.cancel()
    controller.close()
    assert controller.state is PawState.CLOSED
    assert ("clip", PointerBounds(-500, 10, 900, 700)) in adapter.events
    assert "release_capture" in adapter.events


def test_start_exception_rolls_back_every_resource():
    adapter = FakePointer()
    def broken_press(): raise RuntimeError("boom")
    adapter.press_left = broken_press
    controller = PawPressController(adapter)
    with pytest.raises(RuntimeError): controller.start(0)
    assert controller.state is PawState.IDLE
    assert adapter.events[-2:] == [("clip", PointerBounds(-500, 10, 900, 700)), "release_capture"]


def test_one_hundred_interactions_restore_clip_capture_and_button_every_time():
    adapter = FakePointer()
    original = adapter.clip
    controller = PawPressController(adapter, hold_seconds=.01)
    for index in range(100):
        assert controller.start(float(index))
        controller.tick(float(index) + .05)
        assert controller.state is PawState.IDLE
        assert adapter.clip == original
        assert adapter.buttons == set()
    assert adapter.events.count("capture") == 100
    assert adapter.events.count("release_capture") == 100

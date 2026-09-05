from __future__ import annotations

from PIL import Image
import pytest

from desktop_pet.ear_interaction import (
    EAR_FEEDBACK,
    EarHitMasks,
    EarMotionController,
    deform_ear,
)


def test_left_and_right_masks_require_nontransparent_pixels_inside_each_ear() -> None:
    image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    image.putpixel((50, 240), (1, 2, 3, 255))
    image.putpixel((220, 240), (1, 2, 3, 1))
    image.putpixel((120, 240), (1, 2, 3, 255))
    masks = EarHitMasks.from_frame(image)

    assert masks.hit_source((50, 240)) == "left"
    assert masks.hit_source((220, 240)) == "right"
    assert masks.hit_source((120, 240)) is None
    assert masks.hit_source((49, 240)) is None


@pytest.mark.parametrize("display_size", [(512, 768), (256, 384), (768, 1152)])
def test_hit_testing_maps_dpi_scaled_display_coordinates(display_size) -> None:
    image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    image.putpixel((50, 240), (255, 255, 255, 255))
    masks = EarHitMasks.from_frame(image)
    point = (50 * display_size[0] / 512, 240 * display_size[1] / 768)

    assert masks.hit_display(point, display_size) == "left"


def test_deformation_is_neutral_identity_and_changes_only_selected_ear_region() -> None:
    image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    for y in range(210, 330):
        for x in range(30, 90):
            image.putpixel((x, y), (x, y % 256, 60, 255))
    original = image.tobytes()

    assert deform_ear(image, "left", 0).tobytes() == original
    changed = deform_ear(image, "left", 1)
    assert changed.tobytes() != original
    assert changed.crop((170, 200, 250, 340)).tobytes() == image.crop((170, 200, 250, 340)).tobytes()


class Scheduler:
    def __init__(self) -> None:
        self.items: list[tuple[object, object]] = []

    def schedule(self, delay, callback):
        token = object()
        self.items.append((token, callback))
        return token

    def cancel(self, token):
        self.items = [item for item in self.items if item[0] is not token]

    def run_all(self):
        while self.items:
            _token, callback = self.items.pop(0)
            callback()


def test_press_hold_release_and_pointer_leave_always_return_to_neutral() -> None:
    scheduler = Scheduler()
    samples = []
    motion = EarMotionController(scheduler.schedule, scheduler.cancel, samples.append)

    motion.press("left")
    assert samples[-1] == ("left", EAR_FEEDBACK.press_amount)
    scheduler.run_all()
    assert samples[-1] == ("left", EAR_FEEDBACK.hold_amount)
    motion.release("left")
    scheduler.run_all()
    assert samples[-1] == ("left", 0.0)
    assert motion.active_side is None

    motion.press("right")
    motion.pointer_left()
    scheduler.run_all()
    assert samples[-1] == ("right", 0.0)


def test_focus_loss_user_interrupt_and_shutdown_reset_both_sides() -> None:
    for reset_name in ("focus_lost", "interrupt", "stop"):
        scheduler = Scheduler()
        samples = []
        motion = EarMotionController(scheduler.schedule, scheduler.cancel, samples.append)
        motion.press("left")
        getattr(motion, reset_name)()
        scheduler.run_all()
        assert samples[-1] == ("left", 0.0)
        assert motion.active_side is None


def test_one_hundred_rapid_interactions_leave_no_stale_callback_or_deformation() -> None:
    scheduler = Scheduler()
    samples = []
    motion = EarMotionController(scheduler.schedule, scheduler.cancel, samples.append)

    for index in range(100):
        side = "left" if index % 2 == 0 else "right"
        motion.press(side)
        motion.release(side)
    scheduler.run_all()

    assert motion.active_side is None
    assert samples[-1][1] == 0.0
    assert scheduler.items == []

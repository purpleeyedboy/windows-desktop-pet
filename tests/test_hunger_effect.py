from PIL import Image, ImageChops

from desktop_pet.hunger_animation import HungerAnimationFrame, HungerVisual
from desktop_pet.hunger_effect import compose_hunger_effect


def frame(*, visual, tears, phase):
    return HungerAnimationFrame(visual, tears, phase, 1_600)


def test_animation_phase_changes_transparent_composite_without_mutating_source() -> None:
    source = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    source.paste((240, 220, 200, 255), (120, 80, 390, 740))
    before = source.tobytes()
    first = compose_hunger_effect(
        source,
        frame(visual=HungerVisual.SEVERE_HUNGRY, tears=False, phase=0),
        ((170, 250, 220, 290), (290, 250, 340, 290)),
    )
    second = compose_hunger_effect(
        source,
        frame(visual=HungerVisual.SEVERE_HUNGRY, tears=False, phase=600),
        ((170, 250, 220, 290), (290, 250, 340, 290)),
    )
    assert source.tobytes() == before
    assert ImageChops.difference(first, second).convert("RGB").getbbox() is not None
    assert first.size == source.size and first.mode == "RGBA"


def test_tears_visible_is_consumed_by_compositor_below_both_eyes() -> None:
    source = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    boxes = ((170, 250, 220, 290), (290, 250, 340, 290))
    dry = compose_hunger_effect(
        source,
        frame(visual=HungerVisual.EXTREME_HUNGRY, tears=False, phase=400),
        boxes,
    )
    wet = compose_hunger_effect(
        source,
        frame(visual=HungerVisual.EXTREME_HUNGRY, tears=True, phase=400),
        boxes,
    )
    assert ImageChops.difference(dry, wet).getbbox() is not None
    for left, _top, right, bottom in boxes:
        crop = wet.crop((left, bottom, right, bottom + 70))
        assert crop.getchannel("A").getbbox() is not None


def test_suspended_frame_returns_unmodified_pixel_copy() -> None:
    source = Image.new("RGBA", (32, 32), (1, 2, 3, 4))
    suspended = HungerAnimationFrame(HungerVisual.SUSPENDED, False, 0, 1_000)
    result = compose_hunger_effect(source, suspended, ())
    assert result is not source
    assert result.tobytes() == source.tobytes()

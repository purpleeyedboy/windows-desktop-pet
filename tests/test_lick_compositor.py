from __future__ import annotations

from PIL import Image, ImageChops

from desktop_pet.idle_lick import LickPose
from desktop_pet.lick_compositor import compose_lick


def base_frame() -> Image.Image:
    image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    image.paste((180, 135, 85, 255), (80, 220, 440, 735))
    image.paste((245, 245, 235, 255), (195, 350, 315, 650))
    return image


def changed_box(before: Image.Image, after: Image.Image):
    return ImageChops.difference(before, after).getbbox(alpha_only=False)


def test_neutral_lick_is_the_exact_same_rgba_object() -> None:
    source = base_frame()
    result = compose_lick(source, LickPose())

    assert result is source
    assert result.tobytes() == source.tobytes()


def test_arm_and_tongue_channels_produce_visible_rgba_output() -> None:
    source = base_frame()
    arm = compose_lick(source, LickPose("left", "raise", 1.0, 0.0))
    tongue = compose_lick(source, LickPose("left", "contact", 1.0, 1.0))

    assert changed_box(source, arm) is not None
    assert changed_box(arm, tongue) is not None
    assert any(r > g + 35 and r > b + 20 and a for r, g, b, a in tongue.getdata())


def test_left_and_right_are_distinct_non_mirrored_screen_locations() -> None:
    source = base_frame()
    left = compose_lick(source, LickPose("left", "contact", 1.0, 1.0))
    right = compose_lick(source, LickPose("right", "contact", 1.0, 1.0))

    left_box = changed_box(source, left)
    right_box = changed_box(source, right)
    assert left_box is not None and right_box is not None
    assert left_box[0] < right_box[0]
    assert left.tobytes() != right.tobytes()


def test_programmatic_overlay_preserves_canvas_and_clean_transparent_rgb() -> None:
    source = base_frame()
    result = compose_lick(source, LickPose("right", "lick", 0.6, 0.7))

    assert result.mode == "RGBA"
    assert result.size == source.size
    assert all(a or (r, g, b) == (0, 0, 0) for r, g, b, a in result.getdata())


def test_lick_overlay_does_not_replace_existing_eye_pixels() -> None:
    source = base_frame()
    source.paste((20, 220, 80, 255), (70, 300, 175, 380))

    result = compose_lick(source, LickPose("right", "contact", 1.0, 1.0))

    assert result.crop((70, 300, 175, 380)).tobytes() == source.crop(
        (70, 300, 175, 380)
    ).tobytes()

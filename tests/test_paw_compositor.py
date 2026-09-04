import json
import hashlib
from pathlib import Path

from PIL import Image

from desktop_pet.model import Rect
from desktop_pet.paw_compositor import PawCompositor
from desktop_pet.assets import load_paw_compositor


def mask(points):
    image = Image.new("L", (8, 8))
    for point in points: image.putpixel(point, 255)
    return image


def test_alpha_hit_testing_is_not_a_bounding_rectangle_and_maps_window_transform():
    compositor = PawCompositor(mask([(1, 1), (2, 1)]), mask([(6, 1), (6, 2)]))
    rect = Rect(-100, 50, 80, 80)
    assert compositor.hit_test("left", PointerPoint := (-85, 65), rect)
    assert not compositor.hit_test("left", (-85, 75), rect)
    assert compositor.hit_test("right", (-35, 65), rect)


def test_hit_testing_maps_the_same_alpha_pixel_at_different_dpi_scales():
    compositor = PawCompositor(mask([(2, 3)]), mask([(6, 1)]))
    assert compositor.hit_test("left", (125, 237), Rect(100, 200, 80, 80))
    assert compositor.hit_test("left", (-150, 275), Rect(-200, 200, 160, 160))
    assert not compositor.hit_test("left", (-150, 255), Rect(-200, 200, 160, 160))


def test_each_paw_moves_independently_and_outside_pixels_are_unchanged():
    source = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    source.putpixel((1, 1), (255, 0, 0, 255)); source.putpixel((6, 1), (0, 0, 255, 255))
    compositor = PawCompositor(mask([(1, 1)]), mask([(6, 1)]))
    result = compositor.compose(source, left_offset=(0, 2), right_offset=(0, 1))
    assert result.getpixel((1, 3)) == (255, 0, 0, 255)
    assert result.getpixel((6, 2)) == (0, 0, 255, 255)
    assert result.getpixel((4, 4)) == source.getpixel((4, 4))


def test_runtime_masks_are_reconstructed_from_reviewable_rle_text():
    definition = json.loads(Path("assets/paws/v1/authoring.json").read_text())
    assert definition["encoding"] == "row-rle-v1"
    assert set(definition["masks"]) == {"left", "right"}
    assert set(definition["decoded_alpha_sha256"]) == {"left", "right"}
    assert all(isinstance(run, list) and len(run) == 4
               for runs in definition["masks"].values() for run in runs)
    compositor = load_paw_compositor()
    for name in ("left", "right"):
        mask = compositor.masks[name]
        assert mask.mode == "L" and mask.size == (512, 768)
        assert mask.getbbox() is not None
        assert hashlib.sha256(mask.tobytes()).hexdigest() == (
            definition["decoded_alpha_sha256"][name]
        )
        assert sum(value > 0 for value in mask.getdata()) < (
            (mask.getbbox()[2] - mask.getbbox()[0])
            * (mask.getbbox()[3] - mask.getbbox()[1])
        )

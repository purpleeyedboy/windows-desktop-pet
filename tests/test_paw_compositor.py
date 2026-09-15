import json
import hashlib
from pathlib import Path

from PIL import Image, ImageChops

from desktop_pet.model import Rect
from desktop_pet.paw_compositor import PawCompositor
from desktop_pet.assets import load_head_neck_compositor, load_paw_compositor
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.paw_compositor import load_rle_masks


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


def test_all_authored_frames_restore_default_and_preserve_opposite_paw():
    source = load_head_neck_compositor().compose(0.0, 0.0, HeadPose(0.0, 0.0))
    compositor = load_paw_compositor()
    assert source.size == (640, 768)
    for side in ("left", "right"):
        assert len(compositor.frames[side]) == 15
        other = "right" if side == "left" else "left"
        opposite = Image.new("L", source.size)
        semantic = compositor.masks[other].copy()
        for y in range(768):
            for x in range(512):
                if (side == "left" and x > 208) or (side == "right" and x < 216):
                    semantic.putpixel((x, y), 0)
        opposite.paste(semantic, (64, 0))
        for index in range(15):
            result = compositor.compose_frame(source, side, index)
            assert result.size == source.size and result.mode == "RGBA"
            if index in (0, 14):
                assert result.tobytes() == source.tobytes()
            delta = ImageChops.difference(result, source)
            # Raised limbs can cross the lower chest. The actual head and the
            # fixed far side of the torso remain pixel-identical.
            assert result.crop((0, 0, 640, 440)).tobytes() == source.crop((0, 0, 640, 440)).tobytes()
            assert result.crop((425, 0, 640, 768)).tobytes() == source.crop((425, 0, 640, 768)).tobytes()
            for channel in delta.split():
                assert ImageChops.multiply(channel, opposite).getbbox() is None
        assert compositor.compose_frame(source, side, 3).tobytes() != source.tobytes()


def test_selected_paw_does_not_leave_old_toes_below_raised_paw():
    source = load_head_neck_compositor().compose(0.0, 0.0, HeadPose(0.0, 0.0))
    compositor = load_paw_compositor()
    for side in ("left", "right"):
        paw = compositor.frames[side][3]
        opposite = compositor.masks["right" if side == "left" else "left"]
        raised = compositor.compose_frame(source, side, 3)
        cleared = 0
        for y in range(710, 750):
            for x in range(512):
                if (compositor.masks[side].getpixel((x, y))
                        and not paw.getpixel((x, y))[3]
                        and not opposite.getpixel((x, y))):
                    assert raised.getpixel((x + 64, y))[3] == 0
                    cleared += 1
        assert cleared > 0


def test_runtime_masks_are_reconstructed_from_reviewable_rle_text():
    definition = json.loads(Path("assets/paws/v1/authoring.json").read_text())
    assert definition["encoding"] == "row-rle-v1"
    assert set(definition["masks"]) == {"left", "right"}
    assert set(definition["decoded_alpha_sha256"]) == {"left", "right"}
    assert all(isinstance(run, list) and len(run) == 4
               for runs in definition["masks"].values() for run in runs)
    masks = dict(zip(("left", "right"), load_rle_masks(Path("assets/paws/v1/authoring.json"))))
    for name in ("left", "right"):
        mask = masks[name]
        assert mask.mode == "L" and mask.size == (512, 768)
        assert mask.getbbox() is not None
        assert hashlib.sha256(mask.tobytes()).hexdigest() == (
            definition["decoded_alpha_sha256"][name]
        )
        assert sum(value > 0 for value in mask.getdata()) < (
            (mask.getbbox()[2] - mask.getbbox()[0])
            * (mask.getbbox()[3] - mask.getbbox()[1])
        )

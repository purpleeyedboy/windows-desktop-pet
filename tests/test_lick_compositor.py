from __future__ import annotations

from PIL import Image

from desktop_pet.idle_lick import LickPose
from desktop_pet.lick_compositor import GroomAssetBundle, GroomSideLayers, compose_lick


def layer(color=(0, 0, 0, 0), box=None) -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    if box is not None:
        image.paste(color, box)
    return image


def side(paw_x: int, contact_x: int) -> GroomSideLayers:
    paw = layer((160, 110, 60, 255), (paw_x, 42, paw_x + 8, 56))
    mask = Image.new("L", (64, 64), 0)
    mask.paste(255, (paw_x, 42, paw_x + 8, 56))
    fill = layer((90, 70, 50, 255), (paw_x, 42, paw_x + 8, 56))
    mouth = layer((80, 25, 20, 255), (29, 20, 35, 24))
    tongue = layer((220, 90, 110, 255), (contact_x - 2, 26, contact_x + 2, 34))
    return GroomSideLayers(
        paw, mask, fill, mouth, tongue,
        (paw_x + 4.0, 49.0), (float(contact_x), 30.0), (32.0, 22.0),
    )


def bundle() -> GroomAssetBundle:
    return GroomAssetBundle((64, 64), {"left": side(10, 27), "right": side(46, 37)})


def test_neutral_preserves_exact_approved_frame_object() -> None:
    frame = layer((120, 100, 80, 255), (0, 0, 64, 64))
    assert compose_lick(frame, LickPose(), bundle(), lambda point: point) is frame


def test_original_paw_location_is_filled_and_textured_paw_moves_to_contact() -> None:
    frame = layer((120, 100, 80, 255), (0, 0, 64, 64))
    result = compose_lick(
        frame, LickPose("left", "contact", 1.0, 1.0), bundle(), lambda point: point
    )

    assert result.getpixel((14, 49))[:3] == (90, 70, 50)
    assert result.getpixel((27, 30))[3] > 0


def test_head_anchor_mapping_moves_mouth_and_contact_together() -> None:
    frame = layer((120, 100, 80, 255), (0, 0, 64, 64))
    mapped = compose_lick(
        frame,
        LickPose("right", "contact", 1.0, 1.0),
        bundle(),
        lambda point: (point[0] + 5.0, point[1] - 3.0),
    )

    assert mapped.getpixel((37, 19))[:3] == (80, 25, 20)
    assert mapped.getpixel((42, 27))[3] > 0


def test_bundle_rejects_missing_side_and_wrong_alpha_contract() -> None:
    left = side(10, 27)
    try:
        GroomAssetBundle((64, 64), {"left": left})
    except ValueError as error:
        assert "cat-left and cat-right" in str(error)
    else:
        raise AssertionError("missing cat side was accepted")

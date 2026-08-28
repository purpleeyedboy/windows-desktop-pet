from pathlib import Path

from PIL import Image, ImageChops

from tools.build_rig_center_guides import build_guides


def test_guides_have_fixed_masks_and_preserve_outside_pixels(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.png"
    Image.new("RGBA", (512, 768), (20, 30, 40, 255)).save(canonical)
    report = build_guides(canonical, tmp_path / "source")
    assert report["landmarks"]["nose"] == [118, 397]
    masks = tmp_path / "source" / "masks"
    with Image.open(masks / "dynamic-head-neck-mask.png") as opened:
        dynamic = opened.copy()
    assert dynamic.mode == "L" and dynamic.getbbox() == (24, 202, 264, 565)
    with Image.open(masks / "body-fill-mask.png") as body_fill:
        assert body_fill.getbbox() == (88, 365, 236, 551)
        assert ImageChops.subtract(body_fill, dynamic).getbbox() is None
    with Image.open(masks / "eye-left-mask.png") as left, Image.open(masks / "eye-right-mask.png") as right:
        assert ImageChops.multiply(left, right).getbbox() is None
    with Image.open(tmp_path / "source" / "guides" / "body-fill-guide.png") as guide, Image.open(masks / "body-fill-mask.png") as mask, Image.open(canonical) as source:
        outside = ImageChops.invert(mask)
        assert ImageChops.difference(Image.composite(guide, source, outside), source).getbbox() is None

import pytest
from PIL import Image, ImageDraw

from desktop_pet.font_runs import FontRunResolver, MissingGlyphError, draw_layout


def test_kaomoji_resolver_splits_user_sample_with_fixed_priority():
    layout = FontRunResolver.for_kaomoji(40).layout("₍^. .^₎⟆", context="jump")
    assert [run.font_key for run in layout.runs] == ["noto_sans", "noto_math"]
    assert layout.runs[-1].text == "⟆"
    assert layout.total_advance <= 230


def test_character_present_in_both_fonts_uses_noto_sans():
    layout = FontRunResolver.for_kaomoji(40).layout("(^.^)")
    assert {run.font_key for run in layout.runs} == {"noto_sans"}


def test_missing_character_fails_with_context_and_codepoint():
    with pytest.raises(MissingGlyphError, match=r"shake.*U\+10FFFF"):
        FontRunResolver.for_kaomoji(40).layout("(^.^)\U0010ffff", context="shake")


def test_drawn_pixels_equal_reported_shared_ink_bbox():
    resolver = FontRunResolver.for_kaomoji(40)
    layout = resolver.layout("₍^. .^₎⟆")
    image = Image.new("L", (280, 140), 0)
    bbox = draw_layout(ImageDraw.Draw(image), layout, (25, 52, 255, 100), 255)
    actual = image.getbbox()
    assert actual is not None
    assert all(abs(actual[index] - bbox[index]) <= 1 for index in range(4))
    assert bbox[0] >= 24 and bbox[2] <= 256
    assert bbox[1] >= 51 and bbox[3] <= 101

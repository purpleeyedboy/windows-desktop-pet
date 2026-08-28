from hashlib import sha256

import pytest
from PIL import ImageFont

from desktop_pet.paths import asset_path


FONT_RELATIVE_PATH = ("assets", "fonts", "ZCOOLKuaiLe-Regular.ttf")
APPROVED_CHINESE_SAMPLE = "猫猫今天要起飞"
EXPECTED_FONT_ASSETS = (
    (
        "ZCOOLKuaiLe-Regular.ttf",
        1_514_968,
        "812a6fc1fe54b6d73a419245c32dfeba8aa33104d5be90d1cf6af082007cb71d",
    ),
    (
        "OFL.txt",
        4_398,
        "538078469839b4a2e7ad22bef4ebe41681a4e53749bb2a072144024f1d6d703d",
    ),
)


def _glyph_signature(font: ImageFont.FreeTypeFont, character: str) -> tuple[object, ...]:
    mask, offset = font.getmask2(character)
    return mask.size, offset, bytes(mask)


def test_zcool_font_loads_and_covers_approved_chinese_sample():
    font = ImageFont.truetype(asset_path(*FONT_RELATIVE_PATH), 28)

    assert font.getbbox(APPROVED_CHINESE_SAMPLE) is not None
    missing_glyph = _glyph_signature(font, "\U0010ffff")
    assert all(
        _glyph_signature(font, character) != missing_glyph
        for character in set(APPROVED_CHINESE_SAMPLE)
    )


@pytest.mark.parametrize(
    ("filename", "expected_size", "expected_sha256"), EXPECTED_FONT_ASSETS
)
def test_bundled_font_assets_match_trusted_google_fonts_release(
    filename: str, expected_size: int, expected_sha256: str
):
    path = asset_path("assets", "fonts", filename)

    assert path.stat().st_size == expected_size
    assert sha256(path.read_bytes()).hexdigest() == expected_sha256


def test_zcool_font_license_and_notice_match_bundled_asset():
    license_text = asset_path("assets", "fonts", "OFL.txt").read_text(
        encoding="utf-8"
    )
    notice_text = asset_path("THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")

    assert "SIL OPEN FONT LICENSE Version 1.1" in license_text
    assert "Copyright 2018 The ZCOOL KuaiLe Project Authors" in notice_text
    assert "SIL Open Font License 1.1" in notice_text
    for _, expected_size, expected_sha256 in EXPECTED_FONT_ASSETS:
        assert str(expected_size) in notice_text
        assert expected_sha256 in notice_text

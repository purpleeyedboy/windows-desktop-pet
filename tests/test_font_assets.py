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
        "NotoSans-Variable.ttf",
        2_049_096,
        "bfb7bb691513f12e734dc346c03a03f784912432d7e3fa8e56efcf906fe86b3d",
    ),
    (
        "NotoSansMath-Regular.ttf",
        1_015_396,
        "3f495fe933c06786e4d5f6d86b8ee70b6753a68ee3b9d87528726de0f6e2c47d",
    ),
)
EXPECTED_LICENSE_ASSETS = (
    (
        "ZCOOLKuaiLe-OFL-1.1.txt",
        4_398,
        "538078469839b4a2e7ad22bef4ebe41681a4e53749bb2a072144024f1d6d703d",
    ),
    (
        "NotoSans-OFL-1.1.txt",
        4_396,
        "cee9892f9f0cc8fe882c9e9537ee6a89621d86ee7ceaf70b02e2b2b1c25c061a",
    ),
    (
        "NotoSansMath-OFL-1.1.txt",
        4_380,
        "403a95275b469061b7d4371c328e0ada3bc7d63328abe2e88aad5cd243b2fe21",
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


@pytest.mark.parametrize(("filename", "size", "digest"), EXPECTED_FONT_ASSETS)
def test_bundled_font_binaries_match_pinned_google_fonts(filename, size, digest):
    path = asset_path("assets", "fonts", filename)

    assert path.stat().st_size == size
    assert sha256(path.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize(("filename", "size", "digest"), EXPECTED_LICENSE_ASSETS)
def test_bundled_font_licenses_match_pinned_google_fonts(filename, size, digest):
    path = asset_path("assets", "fonts", "licenses", filename)

    assert path.stat().st_size == size
    assert sha256(path.read_bytes()).hexdigest() == digest


def test_notice_lists_every_pinned_font_and_license():
    notice = asset_path("THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")

    for filename, size, digest in (*EXPECTED_FONT_ASSETS, *EXPECTED_LICENSE_ASSETS):
        assert filename in notice
        assert str(size) in notice
        assert digest in notice.lower()

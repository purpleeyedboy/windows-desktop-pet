from hashlib import sha256

from PIL import ImageFont

from desktop_pet.paths import asset_path


FONT_RELATIVE_PATH = ("assets", "fonts", "ZCOOLKuaiLe-Regular.ttf")
APPROVED_CHINESE_SAMPLE = "猫猫今天要起飞"


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


def test_zcool_font_license_and_notice_match_bundled_asset():
    font_path = asset_path(*FONT_RELATIVE_PATH)
    license_text = asset_path("assets", "fonts", "OFL.txt").read_text(
        encoding="utf-8"
    )
    notice_text = asset_path("THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")

    assert "SIL OPEN FONT LICENSE Version 1.1" in license_text
    assert "Copyright 2018 The ZCOOL KuaiLe Project Authors" in notice_text
    assert "SIL Open Font License 1.1" in notice_text
    assert str(font_path.stat().st_size) in notice_text
    assert sha256(font_path.read_bytes()).hexdigest() in notice_text

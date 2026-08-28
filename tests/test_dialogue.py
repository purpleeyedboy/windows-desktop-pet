import json
from random import Random
import subprocess
import sys

import pytest

from desktop_pet.dialogue import (
    DialogueChooser,
    is_kaomoji_phrase,
    load_phrase_pools,
    validate_phrase_rendering,
    validate_phrase_pools,
)
from desktop_pet.paths import asset_path


ACTIONS = ("jump", "squash", "shake")
FIRST_PERSON_MARKERS = ("我", "本喵", "本猫", "猫猫")


def _valid_pools() -> dict[str, tuple[str, ...]]:
    chinese = [f"{chr(0x4E00 + index)}猫猫天天开心" for index in range(540)]
    eyes = "^xoO@><;-"
    kaomoji = [f"(={left}^{right}=)" for left in eyes for right in eyes][:60]
    return {
        action: tuple(
            chinese[chinese_offset : chinese_offset + 180]
            + kaomoji[kaomoji_offset : kaomoji_offset + 20]
        )
        for action, chinese_offset, kaomoji_offset in zip(
            ACTIONS,
            (0, 180, 360),
            (0, 20, 40),
            strict=True,
        )
    }


def test_packaged_dialogue_has_three_global_unique_200_phrase_pools():
    pools = load_phrase_pools()
    assert set(pools) == {"jump", "squash", "shake"}
    assert {key: len(value) for key, value in pools.items()} == {
        "jump": 200,
        "squash": 200,
        "shake": 200,
    }
    flattened = [phrase for values in pools.values() for phrase in values]
    assert len(set(flattened)) == 600
    assert all(6 <= len(phrase) <= 10 for phrase in flattened)
    assert sum(7 <= len(phrase) <= 9 for phrase in flattened) == 596
    assert all(isinstance(values, tuple) for values in pools.values())


def test_packaged_dialogue_has_exact_180_chinese_and_20_kaomoji_per_action():
    pools = load_phrase_pools()
    for action, phrases in pools.items():
        kaomoji = [text for text in phrases if is_kaomoji_phrase(text)]
        chinese = [text for text in phrases if not is_kaomoji_phrase(text)]
        assert len(kaomoji) == 20
        assert len(chinese) == 180
        assert all(any(marker in text for marker in FIRST_PERSON_MARKERS) for text in chinese)


def test_user_kaomoji_style_is_packaged_and_uses_no_system_fallback():
    pools = load_phrase_pools()
    assert "₍^. .^₎⟆" in pools["jump"]
    assert is_kaomoji_phrase("₍^. .^₎⟆")


@pytest.mark.parametrize("text", ["猫猫冲呀(^.^)", "🎉(^.^)", "(^.^)\u200d", "ab(^.^)"])
def test_kaomoji_classifier_rejects_mixed_text_emoji_and_format_controls(text):
    assert not is_kaomoji_phrase(text)


def test_render_validation_reports_split_counts_and_widths():
    stats = validate_phrase_rendering(load_phrase_pools())
    assert stats.chinese_count == 540
    assert stats.kaomoji_count == 60
    assert 120 <= stats.chinese.minimum <= stats.chinese.maximum <= 230
    assert 60 <= stats.kaomoji.minimum <= stats.kaomoji.maximum <= 230


def test_font_coverage_validation_rejects_missing_glyph_with_action_and_phrase():
    phrase = "本喵飞飞\U0010ffff飞"

    with pytest.raises(ValueError, match=r"jump.*missing bundled glyph U\+10FFFF"):
        validate_phrase_rendering({"jump": (phrase,)})


def test_load_phrase_pools_reads_an_explicit_utf8_json_path():
    pools = load_phrase_pools(asset_path("assets", "dialogue", "phrases.json"))

    assert pools["jump"][0] == "猫猫要摸云朵啦"
    assert isinstance(pools["jump"], tuple)


def test_load_phrase_pools_normalizes_non_iterable_json_pool_to_value_error(tmp_path):
    dialogue_path = tmp_path / "phrases.json"
    dialogue_path.write_text(
        json.dumps({"jump": 17, "squash": [], "shake": []}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="jump.*sequence"):
        load_phrase_pools(dialogue_path)


def test_dialogue_cli_reports_production_width_statistics_and_action_counts():
    result = subprocess.run(
        [sys.executable, "tools/validate_dialogue.py"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    assert "jump: 180 Chinese + 20 kaomoji" in result.stdout
    assert "squash: 180 Chinese + 20 kaomoji" in result.stdout
    assert "shake: 180 Chinese + 20 kaomoji" in result.stdout
    assert "Chinese width min/median/max:" in result.stdout
    assert "Kaomoji width min/median/max:" in result.stdout


def test_dialogue_cli_reports_bad_json_pool_as_one_clean_stderr_error(tmp_path):
    dialogue_path = tmp_path / "bad-phrases.json"
    dialogue_path.write_text(
        json.dumps({"jump": 17, "squash": [], "shake": []}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/validate_dialogue.py",
            "--dialogue",
            str(dialogue_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        "dialogue validation failed: "
        "action 'jump' phrases must be a sequence\n"
    )


def test_dialogue_chooser_uses_only_requested_action_and_avoids_immediate_repeat():
    pools = {
        "jump": ("跳高高看云朵", "猫猫今天要起飞"),
        "squash": ("压成软软小团子", "回弹成功喵喵喵"),
        "shake": ("左右摇摇醒醒神", "抖抖耳朵精神啦"),
    }
    chooser = DialogueChooser(pools, Random(3))

    jump_choices = [chooser.choose("jump") for _ in range(12)]
    squash_choice = chooser.choose("squash")

    assert all(phrase in pools["jump"] for phrase in jump_choices)
    assert all(current != previous for previous, current in zip(jump_choices, jump_choices[1:]))
    assert squash_choice in pools["squash"]


def test_dialogue_chooser_rejects_empty_pools():
    with pytest.raises(ValueError, match="non-empty"):
        DialogueChooser({"jump": ()}, Random(1))


@pytest.mark.parametrize(
    ("pools", "message"),
    [
        ({"jump": (), "squash": (), "shake": (), "roll": ()}, "keys"),
        ({"jump": (), "squash": (), "shake": ()}, "jump"),
    ],
)
def test_dialogue_validation_rejects_bad_keys_and_counts(pools, message):
    with pytest.raises(ValueError, match=message):
        validate_phrase_pools(pools)


@pytest.mark.parametrize(
    ("bad_phrase", "message"),
    [
        (17, "jump.*17"),
        (" 猫猫天天开心", "jump.*猫猫天天开心"),
        ("猫猫短", "jump.*猫猫短"),
    ],
)
def test_dialogue_validation_identifies_bad_phrase_and_action(bad_phrase, message):
    pools = _valid_pools()
    pools["jump"] = (bad_phrase, *pools["jump"][1:])

    with pytest.raises(ValueError, match=message):
        validate_phrase_pools(pools)


def test_dialogue_validation_rejects_phrase_without_cat_first_person_marker():
    pools = _valid_pools()
    phrase = "今天天天真开心"
    pools["jump"] = (phrase, *pools["jump"][1:])

    with pytest.raises(ValueError, match=f"jump.*{phrase}.*first-person"):
        validate_phrase_pools(pools)


def test_dialogue_validation_rejects_global_duplicates_with_both_actions():
    pools = _valid_pools()
    duplicate = pools["jump"][0]
    pools["shake"] = (duplicate, *pools["shake"][1:])

    with pytest.raises(ValueError, match=f"shake.*{duplicate}.*jump"):
        validate_phrase_pools(pools)


def test_dialogue_validation_enforces_ninety_percent_visual_length_rule():
    pools = _valid_pools()
    flattened = [phrase for values in pools.values() for phrase in values]
    for index in range(61):
        flattened[index] = flattened[index][0] + "猫猫短短短"  # Six characters.
    pools = {
        action: tuple(flattened[offset : offset + 200])
        for action, offset in zip(ACTIONS, (0, 200, 400), strict=True)
    }

    with pytest.raises(ValueError, match="90%"):
        validate_phrase_pools(pools)

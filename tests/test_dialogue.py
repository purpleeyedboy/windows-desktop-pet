from random import Random

import pytest
from PIL import ImageFont

from desktop_pet.dialogue import DialogueChooser, load_phrase_pools, validate_phrase_pools
from desktop_pet.paths import asset_path


ACTIONS = ("jump", "squash", "shake")


def _valid_pools() -> dict[str, tuple[str, ...]]:
    phrases = [f"{chr(0x4E00 + index)}猫猫天天开心" for index in range(600)]
    return {
        action: tuple(phrases[offset : offset + 200])
        for action, offset in zip(ACTIONS, (0, 200, 400), strict=True)
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
    assert sum(7 <= len(phrase) <= 9 for phrase in flattened) >= 540
    assert all(isinstance(values, tuple) for values in pools.values())


def test_packaged_dialogue_uses_only_glyphs_in_the_bundled_font():
    pools = load_phrase_pools()
    font = ImageFont.truetype(
        asset_path("assets", "fonts", "ZCOOLKuaiLe-Regular.ttf"),
        28,
    )
    missing_mask = bytes(font.getmask(chr(0x10FFFF)))
    unsupported = sorted(
        {
            character
            for phrases in pools.values()
            for phrase in phrases
            for character in phrase
            if bytes(font.getmask(character)) == missing_mask
        }
    )

    assert unsupported == []


def test_load_phrase_pools_reads_an_explicit_utf8_json_path():
    pools = load_phrase_pools(asset_path("assets", "dialogue", "phrases.json"))

    assert pools["jump"][0] == "猫猫要摸云朵啦"
    assert isinstance(pools["jump"], tuple)


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

from random import Random

from desktop_pet.model import ActionCycle, Rect, clamp_height, choose_phrase, place_bubble


def test_clamp_height_enforces_contract():
    assert clamp_height(80) == 120
    assert clamp_height(280) == 280
    assert clamp_height(700) == 520


def test_action_cycle_repeats_fixed_order():
    cycle = ActionCycle()
    assert [cycle.next() for _ in range(5)] == [
        "jump",
        "squash",
        "shake",
        "jump",
        "squash",
    ]


def test_phrase_is_from_action_pool():
    assert choose_phrase("jump", Random(7)) in {
        "看我起飞！",
        "今天也要跳高高！",
        "猫猫升空！",
    }


def test_bubble_prefers_above_without_overlap():
    screen = Rect(0, 0, 1920, 1040)
    pet = Rect(1500, 650, 240, 360)
    result = place_bubble(pet, (180, 72), screen, gap=12)
    assert result.bottom <= pet.top - 12
    assert screen.contains(result)


def test_bubble_moves_to_side_when_top_space_is_missing():
    screen = Rect(0, 0, 800, 600)
    pet = Rect(300, 8, 180, 300)
    result = place_bubble(pet, (190, 72), screen, gap=12)
    assert not result.intersects(pet)
    assert screen.contains(result)

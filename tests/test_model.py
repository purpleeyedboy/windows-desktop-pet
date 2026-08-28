from desktop_pet.model import ActionCycle, Rect, clamp_height, place_bubble


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


def test_bubble_shrinks_to_avoid_a_large_pet_on_a_small_screen():
    screen = Rect(0, 0, 800, 600)
    pet = Rect(226, 40, 347, 520)

    result = place_bubble(pet, (260, 76), screen, gap=12)

    assert screen.contains(result)
    assert not result.intersects(pet)
    assert result.height == 76
    assert 132 <= result.width < 260


def test_bubble_can_shrink_below_132_pixels_on_a_narrow_screen():
    screen = Rect(0, 0, 600, 600)
    pet = Rect(126, 40, 347, 520)

    result = place_bubble(pet, (260, 76), screen, gap=12)

    assert result is not None
    assert screen.contains(result)
    assert not result.intersects(pet)
    assert result.width == 114


def test_bubble_returns_none_when_the_pet_leaves_no_safe_area():
    screen = Rect(0, 0, 200, 200)
    pet = Rect(0, 0, 200, 200)

    assert place_bubble(pet, (132, 76), screen, gap=12) is None


def test_bubble_returns_none_when_an_offscreen_pet_cannot_fit_a_side_bubble():
    screen = Rect(0, 0, 800, 600)
    pet = Rect(900, 100, 200, 300)

    assert place_bubble(pet, (190, 76), screen, gap=12) is None

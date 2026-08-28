from PIL import ImageChops

from desktop_pet.bubble import BubbleComposer
from desktop_pet.bubble_layout import (
    BUBBLE_BODY_SIZE,
    BUBBLE_FONT_SIZE,
    BUBBLE_TEXT_SAFE_RECT,
)
from desktop_pet.dialogue import DIALOGUE_FONT_SIZE, MAX_PHRASE_WIDTH
from desktop_pet.model import BubblePlacement, Rect, place_oriented_bubble
from desktop_pet.paths import asset_path


DIRECTIONS = ("down", "up", "left", "right")


def _opaque_component_count(image, threshold=16):
    alpha = image.getchannel("A")
    opaque = {
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if alpha.getpixel((x, y)) >= threshold
    }
    components = 0
    while opaque:
        components += 1
        pending = [opaque.pop()]
        while pending:
            x, y = pending.pop()
            for neighbor in (
                (x - 1, y - 1),
                (x, y - 1),
                (x + 1, y - 1),
                (x - 1, y),
                (x + 1, y),
                (x - 1, y + 1),
                (x, y + 1),
                (x + 1, y + 1),
            ):
                if neighbor in opaque:
                    opaque.remove(neighbor)
                    pending.append(neighbor)
    return components


def test_composer_returns_rgba_with_transparent_corners_and_visible_text():
    composer = BubbleComposer()

    image = composer.render("猫猫今天要起飞", "down")
    blank = composer.render("", "down")

    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0
    assert image.getchannel("A").getextrema() == (0, 255)
    assert (
        ImageChops.difference(image.convert("RGB"), blank.convert("RGB")).getbbox()
        is not None
    )


def test_composer_preserves_the_body_aspect_ratio_and_directional_tail_sizes():
    composer = BubbleComposer()

    assert BUBBLE_BODY_SIZE[0] == 2 * BUBBLE_BODY_SIZE[1]
    images = {direction: composer.render("猫猫今天要起飞", direction) for direction in DIRECTIONS}
    assert images["down"].width == BUBBLE_BODY_SIZE[0]
    assert images["up"].width == BUBBLE_BODY_SIZE[0]
    assert images["left"].height == BUBBLE_BODY_SIZE[1]
    assert images["right"].height == BUBBLE_BODY_SIZE[1]
    assert images["down"].height > BUBBLE_BODY_SIZE[1]
    assert images["up"].height == BUBBLE_BODY_SIZE[1]
    assert images["left"].width == BUBBLE_BODY_SIZE[0]
    assert images["right"].width == BUBBLE_BODY_SIZE[0]


def test_each_directional_tail_is_visibly_connected_to_the_body():
    composer = BubbleComposer()

    assert {
        direction: _opaque_component_count(composer.render("", direction))
        for direction in DIRECTIONS
    } == {direction: 1 for direction in DIRECTIONS}


def test_composer_uses_the_bundled_font_and_shared_production_layout_contract():
    composer = BubbleComposer()

    assert composer.font_path == asset_path(
        "assets", "fonts", "ZCOOLKuaiLe-Regular.ttf"
    )
    assert DIALOGUE_FONT_SIZE == BUBBLE_FONT_SIZE == 28
    assert MAX_PHRASE_WIDTH == BUBBLE_TEXT_SAFE_RECT[2] - BUBBLE_TEXT_SAFE_RECT[0]


def test_oriented_placement_points_tail_toward_pet():
    result = place_oriented_bubble(
        Rect(500, 500, 200, 300),
        {direction: (280, 116) for direction in DIRECTIONS},
        Rect(0, 0, 1200, 900),
    )

    assert result == BubblePlacement(Rect(460, 372, 280, 116), "down")
    assert result.rect.bottom <= 488


def test_oriented_placement_uses_matching_side_and_below_tail_directions():
    sizes = {direction: (280, 116) for direction in DIRECTIONS}

    left = place_oriented_bubble(
        Rect(500, 20, 200, 300), sizes, Rect(0, 0, 1200, 900)
    )
    right = place_oriented_bubble(
        Rect(20, 20, 200, 300), sizes, Rect(0, 0, 1200, 900)
    )
    below = place_oriented_bubble(
        Rect(0, 20, 1200, 300), sizes, Rect(0, 0, 1200, 900)
    )

    assert left is not None and left.tail_direction == "right"
    assert right is not None and right.tail_direction == "left"
    assert below is not None and below.tail_direction == "up"
    assert not left.rect.intersects(Rect(500, 20, 200, 300))
    assert not right.rect.intersects(Rect(20, 20, 200, 300))
    assert not below.rect.intersects(Rect(0, 20, 1200, 300))


def test_oriented_placement_keeps_safe_side_fallback_for_small_screens():
    pet = Rect(226, 40, 347, 520)
    result = place_oriented_bubble(
        pet,
        {direction: (298, 140) for direction in DIRECTIONS},
        Rect(0, 0, 800, 600),
    )

    assert result is not None
    assert result.tail_direction == "right"
    assert result.rect.width < 298
    assert not result.rect.intersects(pet)

from PIL import Image

from tools.process_sprites import (
    clear_border_chroma,
    normalize_sprite,
    remove_small_components,
    split_grid,
)


def test_split_grid_returns_six_equal_cells():
    sheet = Image.new("RGB", (300, 200), "blue")
    cells = split_grid(sheet, columns=3, rows=2)
    assert len(cells) == 6
    assert {cell.size for cell in cells} == {(100, 100)}


def test_split_grid_rejects_inexact_dimensions():
    sheet = Image.new("RGB", (301, 200), "blue")
    try:
        split_grid(sheet, columns=3, rows=2)
    except ValueError as error:
        assert "divisible" in str(error)
    else:
        raise AssertionError("inexact grid dimensions must fail")


def test_clear_border_chroma_preserves_center_subject():
    image = Image.new("RGB", (12, 12), (0, 0, 255))
    for x in range(4, 8):
        for y in range(3, 10):
            image.putpixel((x, y), (230, 170, 110))
    result = clear_border_chroma(image, tolerance=55)
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((5, 5))[3] == 255


def test_clear_border_chroma_softens_and_despills_blue_edge():
    image = Image.new("RGB", (5, 5), (0, 0, 255))
    image.putpixel((2, 2), (230, 170, 110))
    image.putpixel((2, 1), (40, 40, 230))
    result = clear_border_chroma(image, tolerance=55)
    red, green, blue, alpha = result.getpixel((2, 1))
    assert 0 < alpha < 255
    assert blue <= max(red, green)


def test_normalize_sprite_uses_runtime_canvas_and_baseline():
    image = Image.new("RGBA", (80, 120), (0, 0, 0, 0))
    for x in range(20, 60):
        for y in range(10, 110):
            image.putpixel((x, y), (255, 120, 30, 255))
    result = normalize_sprite(image, canvas=(512, 768), margin=32)
    assert result.size == (512, 768)
    assert result.mode == "RGBA"
    assert result.getbbox()[3] == 736


def test_remove_small_components_drops_isolated_speck():
    image = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    for x in range(6, 14):
        for y in range(5, 18):
            image.putpixel((x, y), (220, 160, 90, 255))
    image.putpixel((1, 1), (220, 160, 90, 255))
    result = remove_small_components(image, min_pixels=4, min_ratio=0.01)
    assert result.getpixel((1, 1))[3] == 0
    assert result.getpixel((10, 10))[3] == 255


def test_remove_small_components_uses_subject_relative_threshold():
    image = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    for x in range(50, 250):
        for y in range(50, 250):
            image.putpixel((x, y), (220, 160, 90, 255))
    for x in range(5, 13):
        for y in range(5, 15):
            image.putpixel((x, y), (220, 160, 90, 255))
    result = remove_small_components(image)
    assert result.getpixel((8, 8))[3] == 0
    assert result.getpixel((100, 100))[3] == 255

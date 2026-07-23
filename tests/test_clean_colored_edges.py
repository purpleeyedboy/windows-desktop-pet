from pathlib import Path

from PIL import Image
import pytest

from tools.clean_colored_edges import (
    clean_colored_edge,
    clean_directory,
    contamination_mask,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_edge_sample() -> Image.Image:
    image = Image.new("RGBA", (11, 11), (23, 45, 67, 0))
    pixels = image.load()
    tan = (170, 140, 105, 255)
    for y in range(2, 9):
        for x in range(2, 9):
            pixels[x, y] = tan

    # A normal cool-gray fur stripe reaches the silhouette and must survive.
    pixels[2, 3] = (100, 115, 130, 180)
    pixels[3, 3] = (102, 116, 129, 255)

    # Four one-pixel chroma spills touch the transparent background.
    pixels[2, 5] = (30, 230, 35, 210)   # green
    pixels[5, 2] = (20, 220, 230, 150)  # cyan
    pixels[8, 5] = (230, 20, 220, 190)  # magenta
    pixels[5, 8] = (25, 40, 230, 170)   # blue

    # The green eye is deliberately inside the subject and must not be touched.
    pixels[5, 5] = (125, 165, 105, 255)
    return image


def test_cleanup_replaces_only_colored_boundary_spill_and_preserves_alpha() -> None:
    source = make_edge_sample()

    mask = contamination_mask(source)
    assert sum(1 for value in mask.getdata() if value) == 4

    cleaned, report = clean_colored_edge(source)

    assert cleaned.getchannel("A").tobytes() == source.getchannel("A").tobytes()
    assert cleaned.getpixel((5, 5)) == source.getpixel((5, 5))
    assert cleaned.getpixel((2, 3)) == source.getpixel((2, 3))
    assert cleaned.getpixel((3, 3)) == source.getpixel((3, 3))
    assert cleaned.getpixel((2, 5))[:3] == (170, 140, 105)
    assert cleaned.getpixel((5, 2))[:3] == (170, 140, 105)
    assert cleaned.getpixel((8, 5))[:3] == (170, 140, 105)
    assert cleaned.getpixel((5, 8))[:3] == (170, 140, 105)
    assert cleaned.getpixel((0, 0)) == (0, 0, 0, 0)
    assert report["changed_pixels"] == 4
    assert sum(1 for value in contamination_mask(cleaned).getdata() if value) == 0


def test_cleanup_makes_thick_green_matte_between_legs_transparent() -> None:
    image = Image.new("RGBA", (17, 17), (0, 0, 0, 0))
    pixels = image.load()
    tan = (170, 140, 105, 255)
    for y in range(2, 8):
        for x in range(2, 15):
            pixels[x, y] = tan
    for y in range(8, 16):
        for x in range(2, 7):
            pixels[x, y] = tan
        for x in range(10, 15):
            pixels[x, y] = tan

    # A thick chroma remnant fills the otherwise transparent leg gap.
    for x in range(7, 10):
        pixels[x, 8] = (28, 25, 30, 180)
    for y in range(9, 16):
        for x in range(7, 10):
            pixels[x, y] = (12, 31, 0, 255) if y < 12 else (22, 93, 35, 255)

    # A natural green eye remains safely inside the head.
    pixels[8, 4] = (125, 165, 105, 255)

    cleaned, report = clean_colored_edge(image)

    for x in range(7, 10):
        assert cleaned.getpixel((x, 8)) == (0, 0, 0, 0)
    for y in range(9, 16):
        for x in range(7, 10):
            assert cleaned.getpixel((x, y)) == (0, 0, 0, 0)
    assert cleaned.getpixel((8, 4)) == image.getpixel((8, 4))
    assert cleaned.getpixel((6, 12)) == tan
    assert cleaned.getpixel((10, 12)) == tan
    assert report["removed_matte_pixels"] == 24
    assert report["matte_bbox"] == [7, 8, 10, 16]


def test_cleanup_removes_detached_colored_speck_that_cannot_be_inpainted() -> None:
    image = Image.new("RGBA", (3, 3), (0, 0, 0, 0))
    image.putpixel((1, 1), (230, 20, 220, 96))

    cleaned, report = clean_colored_edge(image)

    assert cleaned.getpixel((1, 1)) == (0, 0, 0, 0)
    assert report["removed_detached_pixels"] == 1
    assert report["unresolved_pixels"] == 0


def test_cleanup_removes_neon_yellow_edge_artifacts_without_touching_fur() -> None:
    image = Image.new("RGBA", (13, 13), (0, 0, 0, 0))
    pixels = image.load()
    tan = (170, 140, 105, 255)
    for y in range(3, 10):
        for x in range(3, 10):
            pixels[x, y] = tan

    pixels[3, 6] = (255, 245, 0, 180)
    pixels[6, 3] = (230, 170, 70, 220)
    pixels[0, 11] = (255, 255, 0, 120)
    pixels[1, 11] = (255, 255, 0, 80)

    cleaned, report = clean_colored_edge(image)

    assert cleaned.getpixel((3, 6))[:3] == tan[:3]
    assert cleaned.getpixel((3, 6))[3] == 180
    assert cleaned.getpixel((6, 3)) == (230, 170, 70, 220)
    assert cleaned.getpixel((0, 11)) == (0, 0, 0, 0)
    assert cleaned.getpixel((1, 11)) == (0, 0, 0, 0)
    assert report["yellow_artifact_pixels"] == 3


def test_cleanup_preserves_opaque_neon_gold_on_the_silhouette() -> None:
    image = Image.new("RGBA", (7, 7), (0, 0, 0, 0))
    for y in range(2, 5):
        for x in range(2, 5):
            image.putpixel((x, y), (170, 140, 105, 255))
    gold = (255, 235, 20, 255)
    image.putpixel((2, 3), gold)

    cleaned, report = clean_colored_edge(image)

    assert cleaned.getpixel((2, 3)) == gold
    assert report["yellow_artifact_pixels"] == 0


def test_clean_directory_writes_relative_pngs_and_a_combined_report(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source" / "jump"
    source.mkdir(parents=True)
    image = make_edge_sample()
    image.save(source / "00.png")
    output = tmp_path / "output"

    report = clean_directory(tmp_path / "source", output)

    with Image.open(output / "jump" / "00.png") as cleaned:
        assert cleaned.mode == "RGBA"
        assert sum(1 for value in contamination_mask(cleaned).getdata() if value) == 0
    assert report["file_count"] == 1
    assert report["files"][0]["path"] == "jump/00.png"


@pytest.mark.parametrize("index", (6, 17))
def test_real_shake_keyframe_has_no_detectable_spill_after_one_cleanup(index: int) -> None:
    source_path = PROJECT_ROOT / "assets" / "pet" / "shake" / f"{index:02d}.png"
    with Image.open(source_path) as source:
        cleaned, _ = clean_colored_edge(source)

    assert sum(1 for value in contamination_mask(cleaned).getdata() if value) == 0

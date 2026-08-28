from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUBBLE_ROOT = PROJECT_ROOT / "assets" / "bubble"
EXPECTED = {
    "cat-ear-bow-body.png": (768, 384),
    "tail-down.png": (80, 80),
    "tail-up.png": (80, 80),
    "tail-left.png": (80, 80),
    "tail-right.png": (80, 80),
}


def test_bubble_component_assets_are_clean_rgba_sprites() -> None:
    """Every exported component is an inset RGBA sprite with clean transparency."""
    problems: list[str] = []
    for name, expected_size in EXPECTED.items():
        path = BUBBLE_ROOT / name
        if not path.is_file():
            problems.append(f"missing: {name}")
            continue
        with Image.open(path) as source:
            image = source.convert("RGBA")
            if source.mode != "RGBA":
                problems.append(f"not RGBA: {name} ({source.mode})")
            if image.size != expected_size:
                problems.append(f"wrong size: {name} ({image.size})")
            alpha = image.getchannel("A")
            alpha_values = list(alpha.getdata())
            if min(alpha_values) != 0 or max(alpha_values) != 255:
                problems.append(f"alpha extrema missing: {name}")
            width, height = image.size
            border = [
                *(image.getpixel((x, 0)) for x in range(width)),
                *(image.getpixel((x, height - 1)) for x in range(width)),
                *(image.getpixel((0, y)) for y in range(height)),
                *(image.getpixel((width - 1, y)) for y in range(height)),
            ]
            if any(pixel[3] != 0 for pixel in border):
                problems.append(f"opaque outer border: {name}")
            if any(pixel[:3] != (0, 0, 0) for pixel in image.getdata() if pixel[3] == 0):
                problems.append(f"transparent RGB residue: {name}")
    assert not problems, "\n".join(problems)


def test_bubble_component_assets_have_no_visible_turquoise_chroma_spill() -> None:
    """Opaque-enough pixels must not retain the turquoise production backdrop."""
    contaminated: list[str] = []
    for name in EXPECTED:
        path = BUBBLE_ROOT / name
        with Image.open(path) as source:
            for index, (red, green, blue, alpha) in enumerate(source.convert("RGBA").getdata()):
                if alpha >= 64 and green - red >= 35 and green - blue >= 20:
                    contaminated.append(f"{name}@{index}=({red},{green},{blue},{alpha})")
    assert contaminated == []

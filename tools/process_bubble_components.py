from __future__ import annotations

import argparse
from collections import deque
import colorsys
from pathlib import Path
from statistics import median_low

from PIL import Image, ImageDraw


SOURCE_BOXES = {
    "cat-ear-bow-body.png": (220, 50, 1366, 634),
    "tail-left.png": (220, 714, 370, 922),
    "tail-down.png": (505, 754, 680, 936),
    "tail-right.png": (820, 750, 1040, 896),
    "tail-up.png": (1138, 756, 1345, 902),
}
OUTPUT_SIZES = {
    "cat-ear-bow-body.png": (768, 384),
    "tail-down.png": (80, 80),
    "tail-up.png": (80, 80),
    "tail-left.png": (80, 80),
    "tail-right.png": (80, 80),
}
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))
ALL_NEIGHBORS = tuple(
    (dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx, dy) != (0, 0)
)


def is_chroma_background(pixel: tuple[int, int, int]) -> bool:
    """Accept only the slightly varying turquoise screen near #00FFB7."""
    red, green, blue = pixel
    hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    return (
        0.40 <= hue <= 0.53
        and saturation >= 0.68
        and value >= 0.72
        and green >= 180
        and green - red >= 95
        and green - blue >= 36
    )


def boundary_background_mask(image: Image.Image) -> list[bool]:
    """Find only chroma pixels connected to the outside of the source image."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = list(rgb.getdata())
    mask = [False] * (width * height)
    queue: deque[int] = deque()
    for x in range(width):
        queue.extend((x, (height - 1) * width + x))
    for y in range(1, height - 1):
        queue.extend((y * width, y * width + width - 1))

    while queue:
        index = queue.popleft()
        if mask[index] or not is_chroma_background(pixels[index]):
            continue
        mask[index] = True
        x, y = index % width, index // width
        for dx, dy in NEIGHBORS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                queue.append(ny * width + nx)
    return mask


def is_visible_turquoise_spill(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    # The composite can reveal a green key fringe at any non-zero opacity.
    # Do not leave low-alpha pixels outside the same cleanup contract.
    return alpha > 0 and green - red >= 35 and green - blue >= 20


def suppress_visible_turquoise_spill(image: Image.Image) -> Image.Image:
    """Rebuild turquoise-key remnants at every non-zero opacity from safe neighbours."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = list(rgba.getdata())
    for _ in range(4):
        pending = {index for index, pixel in enumerate(pixels) if is_visible_turquoise_spill(pixel)}
        while pending:
            replacements: dict[int, tuple[int, int, int, int]] = {}
            for index in pending:
                x, y = index % width, index // width
                neighbors = []
                for dx, dy in ALL_NEIGHBORS:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    pixel = pixels[ny * width + nx]
                    if pixel[3] > 0 and not is_visible_turquoise_spill(pixel):
                        neighbors.append(pixel[:3])
                if neighbors:
                    median = tuple(median_low(color[channel] for color in neighbors) for channel in range(3))
                    # Use an observed neighbour rather than a channel-wise synthetic
                    # colour: the latter can accidentally reintroduce a turquoise hue.
                    color = min(
                        neighbors,
                        key=lambda candidate: sum(
                            abs(candidate[channel] - median[channel]) for channel in range(3)
                        ),
                    )
                    replacements[index] = (*color, pixels[index][3])
            if not replacements:
                break
            for index, pixel in replacements.items():
                pixels[index] = pixel
            pending.difference_update(replacements)
        if not any(is_visible_turquoise_spill(pixel) for pixel in pixels):
            break
    # A residual run with no safe coloured neighbor cannot be trustworthy artwork.
    for index, pixel in enumerate(pixels):
        if is_visible_turquoise_spill(pixel):
            pixels[index] = (0, 0, 0, 0)
    return Image.frombytes("RGBA", rgba.size, bytes(channel for pixel in pixels for channel in pixel))


def extract_component(source: Image.Image, box: tuple[int, int, int, int], size: tuple[int, int]) -> Image.Image:
    rgb = source.convert("RGB")
    width, height = rgb.size
    pixels = list(rgb.getdata())
    background = boundary_background_mask(rgb)
    rgba: list[tuple[int, int, int, int]] = []
    for index, pixel in enumerate(pixels):
        if background[index]:
            rgba.append((0, 0, 0, 0))
            continue
        red, green, blue = pixel
        # Edge opacity is inferred from distance from the turquoise key. This keeps
        # antialiasing while excluding the coloured matte; opaque pixels remain intact.
        chroma_distance = ((red - 8) ** 2 + (green - 246) ** 2 + (blue - 180) ** 2) ** 0.5
        alpha = max(0, min(255, round((chroma_distance - 34) * 2.25)))
        if alpha < 12:
            rgba.append((0, 0, 0, 0))
        else:
            # Remove the known green-screen contribution to prevent teal halos.
            opacity = alpha / 255
            cleaned = tuple(
                max(0, min(255, round((channel - (1 - opacity) * background_channel) / opacity)))
                for channel, background_channel in zip((red, green, blue), (8, 246, 180))
            )
            rgba.append((*cleaned, alpha))
    transparent = Image.new("RGBA", (width, height))
    transparent.putdata(rgba)
    cropped = transparent.crop(box)
    cropped.thumbnail((size[0] - 6, size[1] - 6), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", size, (0, 0, 0, 0))
    result.alpha_composite(cropped, ((size[0] - cropped.width) // 2, (size[1] - cropped.height) // 2))
    result = suppress_visible_turquoise_spill(result)
    # Pillow interpolation may leave RGB data below a fully transparent alpha value.
    result.putdata([(0, 0, 0, 0) if alpha == 0 else (red, green, blue, alpha) for red, green, blue, alpha in result.getdata()])
    return result


def make_contact_sheet(components: dict[str, Image.Image], target: Path) -> None:
    panel_width, panel_height = 1120, 256
    sheet = Image.new("RGB", (panel_width, panel_height * 2), (46, 50, 56))
    draw = ImageDraw.Draw(sheet)
    tail_names = ("tail-down.png", "tail-up.png", "tail-left.png", "tail-right.png")
    for row, color in enumerate(((46, 50, 56), (222, 225, 230))):
        top = row * panel_height
        draw.rectangle((0, top, panel_width - 1, top + panel_height - 1), fill=color)
        body = components["cat-ear-bow-body.png"].copy()
        body.thumbnail((560, panel_height - 26), Image.Resampling.LANCZOS)
        sheet.paste(body, (18, top + (panel_height - body.height) // 2), body)
        for index, name in enumerate(tail_names):
            tail = components[name]
            x = 630 + index * 120 + (80 - tail.width) // 2
            y = top + (panel_height - tail.height) // 2
            sheet.paste(tail, (x, y), tail)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, "PNG")


def process(source_path: Path, output_dir: Path, contact_sheet: Path) -> None:
    with Image.open(source_path) as source:
        components = {
            name: extract_component(source, SOURCE_BOXES[name], OUTPUT_SIZES[name])
            for name in OUTPUT_SIZES
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, image in components.items():
        image.save(output_dir / name, "PNG")
    make_contact_sheet(components, contact_sheet)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract transparent cat-ear bubble components.")
    parser.add_argument("--source", type=Path, default=Path("qa/staging/cat-ear-bubble-components-chroma.png"))
    parser.add_argument("--output-dir", type=Path, default=Path("assets/bubble"))
    parser.add_argument("--contact-sheet", type=Path, default=Path("qa/cat-ear-bubble-assets.png"))
    args = parser.parse_args()
    process(args.source, args.output_dir, args.contact_sheet)
    print("OK: extracted cat-ear bubble body and four directional tails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

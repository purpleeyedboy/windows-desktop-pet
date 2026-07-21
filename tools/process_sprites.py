from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw


CANVAS = (512, 768)
FRAME_COUNT = 6
ACTIONS = ("jump", "squash", "shake")


def split_grid(sheet: Image.Image, columns: int = 3, rows: int = 2) -> list[Image.Image]:
    if sheet.width % columns or sheet.height % rows:
        raise ValueError("sheet dimensions must be divisible by the grid")
    width, height = sheet.width // columns, sheet.height // rows
    return [
        sheet.crop((x * width, y * height, (x + 1) * width, (y + 1) * height))
        for y in range(rows)
        for x in range(columns)
    ]


def clear_border_chroma(
    image: Image.Image,
    tolerance: int = 55,
    key: tuple[int, int, int] = (0, 0, 255),
) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    opaque_threshold = 240
    for y in range(height):
        for x in range(width):
            red, green, blue, source_alpha = pixels[x, y]
            distance = sum(
                abs(channel - key[index])
                for index, channel in enumerate((red, green, blue))
            )
            if distance <= tolerance:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            if distance >= opaque_threshold:
                continue
            alpha_ratio = (distance - tolerance) / (opaque_threshold - tolerance)
            alpha = max(1, min(source_alpha, round(255 * alpha_ratio)))
            red = min(255, round(red / alpha_ratio))
            green = min(255, round(green / alpha_ratio))
            recovered_blue = round((blue - (1 - alpha_ratio) * key[2]) / alpha_ratio)
            blue = max(0, min(255, recovered_blue, max(red, green)))
            pixels[x, y] = (red, green, blue, alpha)
    return rgba


def normalize_sprite(
    image: Image.Image,
    canvas: tuple[int, int] = CANVAS,
    margin: int = 32,
) -> Image.Image:
    bbox = image.getbbox()
    if bbox is None:
        raise ValueError("sprite is empty after background removal")
    subject = image.crop(bbox)
    max_width, max_height = canvas[0] - 2 * margin, canvas[1] - 2 * margin
    scale = min(max_width / subject.width, max_height / subject.height)
    size = (
        max(1, round(subject.width * scale)),
        max(1, round(subject.height * scale)),
    )
    subject = subject.resize(size, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", canvas, (0, 0, 0, 0))
    output.alpha_composite(
        subject,
        ((canvas[0] - size[0]) // 2, canvas[1] - margin - size[1]),
    )
    return output


def remove_small_components(
    image: Image.Image,
    min_pixels: int = 24,
    min_ratio: float = 0.003,
) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    width, height = rgba.size
    visited: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for y in range(height):
        for x in range(width):
            if (x, y) in visited or alpha.getpixel((x, y)) <= 8:
                continue
            queue = deque([(x, y)])
            visited.add((x, y))
            component: list[tuple[int, int]] = []
            while queue:
                current_x, current_y = queue.popleft()
                component.append((current_x, current_y))
                for neighbor_y in range(max(0, current_y - 1), min(height, current_y + 2)):
                    for neighbor_x in range(max(0, current_x - 1), min(width, current_x + 2)):
                        neighbor = (neighbor_x, neighbor_y)
                        if neighbor in visited or alpha.getpixel(neighbor) <= 8:
                            continue
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    if not components:
        return rgba
    threshold = max(min_pixels, round(max(map(len, components)) * min_ratio))
    pixels = rgba.load()
    for component in components:
        if len(component) >= threshold:
            continue
        for x, y in component:
            pixels[x, y] = (0, 0, 0, 0)
    return rgba


def process_sheet(sheet: Image.Image, action: str) -> list[Image.Image]:
    if action not in ACTIONS:
        raise ValueError(f"unknown action: {action}")
    return [
        normalize_sprite(remove_small_components(clear_border_chroma(cell)))
        for cell in split_grid(sheet)
    ]


def save_action_frames(frames: list[Image.Image], action: str, output_dir: Path) -> None:
    action_dir = output_dir / action
    action_dir.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        frame.save(action_dir / f"{index:02d}.png", optimize=True)


def make_contact_sheet(frames: dict[str, list[Image.Image]], output: Path) -> None:
    thumb_size = (192, 288)
    label_height = 28
    sheet = Image.new(
        "RGBA",
        (thumb_size[0] * FRAME_COUNT, (thumb_size[1] + label_height) * len(ACTIONS)),
        (32, 36, 44, 255),
    )
    draw = ImageDraw.Draw(sheet)
    for row, action in enumerate(ACTIONS):
        top = row * (thumb_size[1] + label_height)
        draw.text((8, top + 7), action, fill=(255, 255, 255, 255))
        for column, frame in enumerate(frames[action]):
            preview = frame.resize(thumb_size, Image.Resampling.LANCZOS)
            checker = Image.new("RGBA", thumb_size, (218, 222, 229, 255))
            checker.alpha_composite(preview)
            sheet.alpha_composite(checker, (column * thumb_size[0], top + label_height))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(output, quality=92)


def make_gif(frames: list[Image.Image], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = []
    for frame in frames:
        canvas = Image.new("RGBA", CANVAS, (226, 229, 235, 255))
        canvas.alpha_composite(frame)
        rendered.append(canvas.convert("RGB").resize((256, 384), Image.Resampling.LANCZOS))
    rendered[0].save(output, save_all=True, append_images=rendered[1:], duration=110, loop=0)


def build_assets(input_dir: Path, output_dir: Path, qa_dir: Path) -> None:
    processed: dict[str, list[Image.Image]] = {}
    for action in ACTIONS:
        source = input_dir / f"{action}.png"
        if not source.is_file():
            raise FileNotFoundError(f"missing generated sheet: {source}")
        with Image.open(source) as sheet:
            frames = process_sheet(sheet, action)
        processed[action] = frames
        save_action_frames(frames, action, output_dir)
        make_gif(frames, qa_dir / f"{action}.gif")
    processed["jump"][0].save(output_dir / "idle.png", optimize=True)
    make_contact_sheet(processed, qa_dir / "action-contact-sheet.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--qa-dir", type=Path, required=True)
    args = parser.parse_args()
    build_assets(args.input_dir, args.output_dir, args.qa_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

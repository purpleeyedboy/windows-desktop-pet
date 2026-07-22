from __future__ import annotations

import argparse
import shutil
from collections import deque
from pathlib import Path

from PIL import Image

from tools.animation_qa import write_action_qa
from tools.process_sprites import (
    clear_border_chroma,
    remove_small_components,
    split_grid,
)


FRAME_SIZE = (512, 768)
INTERMEDIATE_COUNTS = (5, 5, 4, 5, 5)
FINAL_POSITIONS = (0, 6, 12, 17, 23, 29)


def extract_transition_cells(sheet: Image.Image, count: int) -> list[Image.Image]:
    if not 1 <= count <= 6:
        raise ValueError("transition count must be between 1 and 6")
    return split_grid(sheet, columns=3, rows=2)[:count]


def interpolate_bbox(
    start: tuple[int, int, int, int],
    end: tuple[int, int, int, int],
    t: float,
) -> tuple[int, int, int, int]:
    if not 0.0 <= t <= 1.0:
        raise ValueError("interpolation position must be between 0 and 1")
    eased = t * t * (3.0 - 2.0 * t)
    return tuple(
        round(first + (second - first) * eased)
        for first, second in zip(start, end, strict=True)
    )


def clean_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    rgba.putdata(
        [
            (0, 0, 0, 0) if alpha == 0 else (red, green, blue, alpha)
            for red, green, blue, alpha in rgba.getdata()
        ]
    )
    return rgba


def despill_connected_blue(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    blue_mask = bytearray(width * height)
    transparent_mask = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            index = y * width + x
            blue_mask[index] = alpha > 0 and blue > max(red, green)
            transparent_mask[index] = alpha == 0

    queue: deque[tuple[int, int]] = deque()
    visited = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if not blue_mask[index]:
                continue
            touches_transparency = any(
                transparent_mask[neighbor_y * width + neighbor_x]
                for neighbor_y in range(max(0, y - 1), min(height, y + 2))
                for neighbor_x in range(max(0, x - 1), min(width, x + 2))
            )
            if touches_transparency:
                queue.append((x, y))
                visited[index] = 1

    while queue:
        x, y = queue.popleft()
        red, green, _blue, alpha = pixels[x, y]
        pixels[x, y] = (red, green, max(red, green), alpha)
        for neighbor_y in range(max(0, y - 1), min(height, y + 2)):
            for neighbor_x in range(max(0, x - 1), min(width, x + 2)):
                index = neighbor_y * width + neighbor_x
                if visited[index] or not blue_mask[index]:
                    continue
                visited[index] = 1
                queue.append((neighbor_x, neighbor_y))
    return rgba


def render_transition_cell(
    cell: Image.Image,
    target_bbox: tuple[int, int, int, int],
) -> Image.Image:
    left, top, right, bottom = target_bbox
    if not (0 <= left < right <= FRAME_SIZE[0] and 0 <= top < bottom <= FRAME_SIZE[1]):
        raise ValueError("target bbox must fit inside the 512x768 canvas")

    keyed = clear_border_chroma(cell, tolerance=70)
    cleaned = despill_connected_blue(remove_small_components(keyed))
    subject_bbox = cleaned.getchannel("A").getbbox()
    if subject_bbox is None:
        raise ValueError("transition cell is empty after chroma removal")
    subject = cleaned.crop(subject_bbox)

    target_width = right - left
    target_height = bottom - top
    scale = min(target_width / subject.width, target_height / subject.height)
    size = (
        max(1, round(subject.width * scale)),
        max(1, round(subject.height * scale)),
    )
    subject = subject.resize(size, Image.Resampling.LANCZOS)
    x = left + (target_width - size[0]) // 2
    y = bottom - size[1]
    output = Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0))
    output.alpha_composite(subject, (x, y))
    output = despill_connected_blue(clean_transparent_rgb(output))
    pixels = output.load()
    for y in range(output.height):
        for x in range(output.width):
            red, green, blue, alpha = pixels[x, y]
            if 0 < alpha < 255 and blue > max(red, green):
                pixels[x, y] = (red, green, max(red, green), alpha)
    return output


def _load_keyframes(keyframe_dir: Path) -> list[Image.Image]:
    paths = [keyframe_dir / f"{index:02d}.png" for index in range(6)]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing keyframes: {', '.join(missing)}")
    frames: list[Image.Image] = []
    for path in paths:
        with Image.open(path) as image:
            frame = image.copy()
        if frame.mode != "RGBA" or frame.size != FRAME_SIZE:
            raise ValueError(f"keyframe must be 512x768 RGBA: {path}")
        if frame.getchannel("A").getbbox() is None:
            raise ValueError(f"keyframe has no visible subject: {path}")
        frames.append(frame)
    return frames


def _assert_distinct_roots(*roots: Path) -> None:
    resolved = [root.resolve() for root in roots]
    if len(set(resolved)) != len(resolved):
        raise ValueError("keyframe_dir, source_dir, output_dir, and qa_dir must be distinct")


def assemble_action(
    keyframe_dir: Path,
    source_dir: Path,
    output_dir: Path,
    qa_dir: Path,
    action: str,
) -> dict[str, object]:
    _assert_distinct_roots(keyframe_dir, source_dir, output_dir, qa_dir)
    keyframes = _load_keyframes(keyframe_dir)
    bboxes = [frame.getchannel("A").getbbox() for frame in keyframes]
    output_dir.mkdir(parents=True, exist_ok=True)
    for index in range(30):
        (output_dir / f"{index:02d}.png").unlink(missing_ok=True)

    for segment, count in enumerate(INTERMEDIATE_COUNTS):
        source_path = source_dir / f"segment_{segment:02d}_{segment + 1:02d}.png"
        if not source_path.is_file():
            raise FileNotFoundError(f"missing transition sheet: {source_path}")
        with Image.open(source_path) as sheet:
            cells = extract_transition_cells(sheet, count)

        start_position = FINAL_POSITIONS[segment]
        shutil.copy2(
            keyframe_dir / f"{segment:02d}.png",
            output_dir / f"{start_position:02d}.png",
        )
        for offset, cell in enumerate(cells, start=1):
            t = offset / (count + 1)
            target_bbox = interpolate_bbox(bboxes[segment], bboxes[segment + 1], t)
            rendered = render_transition_cell(cell, target_bbox)
            rendered.save(output_dir / f"{start_position + offset:02d}.png", optimize=True)

    shutil.copy2(keyframe_dir / "05.png", output_dir / "29.png")
    runtime_frames: list[Image.Image] = []
    for index in range(30):
        with Image.open(output_dir / f"{index:02d}.png") as image:
            runtime_frames.append(image.copy())
    return write_action_qa(runtime_frames, qa_dir, action)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyframes", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--action", required=True)
    args = parser.parse_args()
    assemble_action(args.keyframes, args.sources, args.output, args.qa, args.action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import shutil
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops

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


def extract_complete_transition_cells(
    sheet: Image.Image,
    count: int,
    margin: int = 24,
) -> list[Image.Image]:
    if not 1 <= count <= 6:
        raise ValueError("transition count must be between 1 and 6")
    if sheet.width % 3 or sheet.height % 2:
        raise ValueError("sheet dimensions must be divisible by the grid")
    cell_size = (sheet.width // 3, sheet.height // 2)
    if margin < 0 or margin * 2 >= min(cell_size):
        raise ValueError("margin must leave positive space inside each cell")

    keyed = remove_small_components(clear_border_chroma(sheet, tolerance=70))
    alpha = keyed.getchannel("A")
    width, height = keyed.size
    values = alpha.tobytes()
    visited = bytearray(width * height)
    components: list[list[int]] = []
    for index, value in enumerate(values):
        if value == 0 or visited[index]:
            continue
        visited[index] = 1
        pending = [index]
        component: list[int] = []
        while pending:
            current = pending.pop()
            component.append(current)
            current_x = current % width
            current_y = current // width
            for neighbor_y in range(max(0, current_y - 1), min(height, current_y + 2)):
                row = neighbor_y * width
                for neighbor_x in range(max(0, current_x - 1), min(width, current_x + 2)):
                    neighbor = row + neighbor_x
                    if visited[neighbor] or values[neighbor] == 0:
                        continue
                    visited[neighbor] = 1
                    pending.append(neighbor)
        components.append(component)
    if len(components) < count:
        raise ValueError(f"expected {count} complete subjects, found {len(components)}")

    selected = sorted(components, key=len, reverse=True)[:count]

    def centroid(component: list[int]) -> tuple[float, float]:
        return (
            sum(index % width for index in component) / len(component),
            sum(index // width for index in component) / len(component),
        )

    by_row = sorted(selected, key=lambda component: centroid(component)[1])
    top_count = min(3, count)
    ordered = sorted(by_row[:top_count], key=lambda component: centroid(component)[0])
    ordered += sorted(by_row[top_count:], key=lambda component: centroid(component)[0])

    cells: list[Image.Image] = []
    for component in ordered:
        xs = [index % width for index in component]
        ys = [index // width for index in component]
        left, top = min(xs), min(ys)
        right, bottom = max(xs) + 1, max(ys) + 1
        subject = keyed.crop((left, top, right, bottom))
        subject_width, subject_height = subject.size
        component_mask = bytearray(subject_width * subject_height)
        for index in component:
            x = index % width - left
            y = index // width - top
            component_mask[y * subject_width + x] = 255
        mask = Image.frombytes("L", subject.size, bytes(component_mask))
        subject.putalpha(ImageChops.multiply(subject.getchannel("A"), mask))
        subject.paste((0, 0, 0, 0), mask=ImageChops.invert(mask))

        available = (cell_size[0] - 2 * margin, cell_size[1] - 2 * margin)
        scale = min(1.0, available[0] / subject.width, available[1] / subject.height)
        if scale < 1.0:
            subject = subject.resize(
                (
                    max(1, round(subject.width * scale)),
                    max(1, round(subject.height * scale)),
                ),
                Image.Resampling.LANCZOS,
            )
        cell = Image.new("RGBA", cell_size, (0, 0, 0, 0))
        cell.alpha_composite(
            subject,
            (
                (cell_size[0] - subject.width) // 2,
                (cell_size[1] - subject.height) // 2,
            ),
        )
        cells.append(clean_transparent_rgb(cell))
    return cells


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


def keep_largest_alpha_component(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return rgba
    width, height = rgba.size
    values = alpha.tobytes()
    visited = bytearray(width * height)
    largest: list[int] = []
    left, top, right, bottom = bbox
    for y in range(top, bottom):
        for x in range(left, right):
            start = y * width + x
            if visited[start] or values[start] == 0:
                continue
            visited[start] = 1
            pending = [start]
            component: list[int] = []
            while pending:
                index = pending.pop()
                component.append(index)
                current_x = index % width
                current_y = index // width
                for neighbor_y in range(max(top, current_y - 1), min(bottom, current_y + 2)):
                    row = neighbor_y * width
                    for neighbor_x in range(max(left, current_x - 1), min(right, current_x + 2)):
                        neighbor = row + neighbor_x
                        if visited[neighbor] or values[neighbor] == 0:
                            continue
                        visited[neighbor] = 1
                        pending.append(neighbor)
            if len(component) > len(largest):
                largest = component

    keep = bytearray(width * height)
    for index in largest:
        keep[index] = 255
    keep_mask = Image.frombytes("L", rgba.size, bytes(keep))
    rgba.paste((0, 0, 0, 0), mask=ImageChops.invert(keep_mask))
    return rgba


def render_transition_cell(
    cell: Image.Image,
    target_bbox: tuple[int, int, int, int],
) -> Image.Image:
    left, top, right, bottom = target_bbox
    if not (0 <= left < right <= FRAME_SIZE[0] and 0 <= top < bottom <= FRAME_SIZE[1]):
        raise ValueError("target bbox must fit inside the 512x768 canvas")

    keyed = clear_border_chroma(cell, tolerance=70)
    cleaned = keep_largest_alpha_component(
        despill_connected_blue(remove_small_components(keyed))
    )
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
    y = top + (target_height - size[1]) // 2
    output = Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0))
    output.alpha_composite(subject, (x, y))
    output = keep_largest_alpha_component(
        despill_connected_blue(clean_transparent_rgb(output))
    )
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
            cells = extract_complete_transition_cells(sheet, count)

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

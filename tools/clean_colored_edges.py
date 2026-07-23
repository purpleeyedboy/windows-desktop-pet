from __future__ import annotations

import argparse
from collections import Counter, deque
import json
from pathlib import Path
from statistics import median_low

from PIL import Image


_NEIGHBORS = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


def _spill_family(red: int, green: int, blue: int) -> str | None:
    maximum = max(red, green, blue)
    minimum = min(red, green, blue)
    spread = maximum - minimum
    # Green-screen remnants can be very dark after antialiasing or compositing.
    if (
        green >= 20
        and green - red >= 8
        and green - blue >= 8
        and spread * 100 >= maximum * 30
    ):
        return "green"
    if maximum < 48 or spread < 26 or spread * 100 < maximum * 32:
        return None
    if red - green >= 24 and blue - green >= 24:
        return "magenta"
    if green - red >= 24 and blue - red >= 24:
        return "cyan"
    if blue - red >= 24 and blue - green >= 12:
        return "blue"
    return None


def _connected_spill(image: Image.Image) -> tuple[list[bool], list[str | None]]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = list(rgba.getdata())
    families: list[str | None] = [None] * len(pixels)
    raw = [False] * len(pixels)
    seeds: deque[int] = deque()

    for index, (red, green, blue, alpha) in enumerate(pixels):
        if alpha == 0:
            continue
        family = _spill_family(red, green, blue)
        if family is None:
            continue
        families[index] = family
        raw[index] = True
        x = index % width
        y = index // width
        for dx, dy in _NEIGHBORS:
            nx, ny = x + dx, y + dy
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                seeds.append(index)
                break
            if pixels[ny * width + nx][3] == 0:
                seeds.append(index)
                break

    connected = [False] * len(pixels)
    while seeds:
        index = seeds.popleft()
        if connected[index]:
            continue
        connected[index] = True
        x = index % width
        y = index // width
        for dx, dy in _NEIGHBORS:
            nx, ny = x + dx, y + dy
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                continue
            neighbor = ny * width + nx
            if raw[neighbor] and not connected[neighbor]:
                seeds.append(neighbor)
    return connected, families


def contamination_mask(image: Image.Image) -> Image.Image:
    connected, _ = _connected_spill(image)
    mask = Image.new("L", image.size, 0)
    mask.putdata([255 if value else 0 for value in connected])
    return mask


def _green_matte_indices(
    connected: list[bool],
    families: list[str | None],
    pixels: list[tuple[int, int, int, int]],
    width: int,
    height: int,
) -> set[int]:
    green = {
        index
        for index, value in enumerate(connected)
        if value and families[index] == "green"
    }
    pending = set(green)
    matte: set[int] = set()
    while pending:
        start = pending.pop()
        component = {start}
        queue = deque([start])
        while queue:
            index = queue.popleft()
            x = index % width
            y = index // width
            for dx, dy in _NEIGHBORS:
                nx, ny = x + dx, y + dy
                if nx < 0 or nx >= width or ny < 0 or ny >= height:
                    continue
                neighbor = ny * width + nx
                if neighbor in pending:
                    pending.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)

        touches_transparency = False
        contains_three_by_three = False
        for index in component:
            x = index % width
            y = index // width
            if any(
                nx < 0
                or nx >= width
                or ny < 0
                or ny >= height
                or pixels[ny * width + nx][3] == 0
                for dx, dy in _NEIGHBORS
                for nx, ny in ((x + dx, y + dy),)
            ):
                touches_transparency = True
            if all(
                0 <= x + dx < width
                and 0 <= y + dy < height
                and (y + dy) * width + x + dx in component
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
            ):
                contains_three_by_three = True
            if touches_transparency and contains_three_by_three:
                matte.update(component)
                xs = [value % width for value in component]
                ys = [value // width for value in component]
                left = max(0, min(xs) - 4)
                right = min(width - 1, max(xs) + 4)
                top = max(0, min(ys) - 40)
                bottom = min(height - 1, max(ys) + 4)
                expansion = deque(component)
                expanded = set(component)
                while expansion:
                    value = expansion.popleft()
                    x = value % width
                    y = value // width
                    for dx, dy in _NEIGHBORS:
                        nx, ny = x + dx, y + dy
                        if nx < left or nx > right or ny < top or ny > bottom:
                            continue
                        neighbor = ny * width + nx
                        if neighbor in expanded:
                            continue
                        red, green_value, blue, alpha = pixels[neighbor]
                        if alpha == 0 or alpha >= 250:
                            continue
                        if max(red, green_value, blue) >= 96 and _spill_family(
                            red, green_value, blue
                        ) != "green":
                            continue
                        expanded.add(neighbor)
                        expansion.append(neighbor)
                matte.update(expanded)
                break
    return matte


def _clean_colored_edge_once(image: Image.Image) -> tuple[Image.Image, dict[str, object]]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = list(rgba.getdata())
    connected, families = _connected_spill(rgba)
    remaining = {index for index, value in enumerate(connected) if value}
    family_counts = Counter(families[index] for index in remaining)
    matte = _green_matte_indices(connected, families, pixels, width, height)
    for index in matte:
        pixels[index] = (0, 0, 0, 0)
    remaining.difference_update(matte)
    changed = 0

    while remaining:
        replacements: dict[int, tuple[int, int, int]] = {}
        for index in remaining:
            x = index % width
            y = index // width
            neighbors: list[tuple[int, int, int]] = []
            for dx, dy in _NEIGHBORS:
                nx, ny = x + dx, y + dy
                if nx < 0 or nx >= width or ny < 0 or ny >= height:
                    continue
                neighbor = ny * width + nx
                if (
                    neighbor in remaining
                    or pixels[neighbor][3] == 0
                    or families[neighbor] is not None
                ):
                    continue
                neighbors.append(pixels[neighbor][:3])
            if neighbors:
                median = tuple(
                    median_low(color[channel] for color in neighbors)
                    for channel in range(3)
                )
                replacements[index] = min(
                    neighbors,
                    key=lambda color: sum(
                        abs(color[channel] - median[channel]) for channel in range(3)
                    ),
                )
        if not replacements:
            break
        for index, color in replacements.items():
            alpha = pixels[index][3]
            if pixels[index][:3] != color:
                changed += 1
            pixels[index] = (*color, alpha)
        remaining.difference_update(replacements)

    detached = set(remaining)
    for index in detached:
        pixels[index] = (0, 0, 0, 0)
    remaining.clear()

    for index, (_, _, _, alpha) in enumerate(pixels):
        if alpha == 0:
            pixels[index] = (0, 0, 0, 0)

    cleaned = Image.new("RGBA", rgba.size)
    cleaned.putdata(pixels)
    matte_bbox = None
    if matte:
        matte_bbox = [
            min(index % width for index in matte),
            min(index // width for index in matte),
            max(index % width for index in matte) + 1,
            max(index // width for index in matte) + 1,
        ]
    return cleaned, {
        "detected_pixels": sum(1 for value in connected if value),
        "changed_pixels": changed,
        "removed_matte_pixels": len(matte),
        "matte_bbox": matte_bbox,
        "removed_detached_pixels": len(detached),
        "unresolved_pixels": len(remaining),
        "family_counts": dict(sorted(family_counts.items())),
    }


def _is_neon_yellow(red: int, green: int, blue: int) -> bool:
    return (
        red >= 235
        and green >= 210
        and blue <= 50
        and abs(red - green) <= 45
    )


def _clean_neon_yellow_edge(
    image: Image.Image,
) -> tuple[Image.Image, dict[str, int]]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = list(rgba.getdata())
    raw = {
        index
        for index, (red, green, blue, alpha) in enumerate(pixels)
        if 0 < alpha < 255 and _is_neon_yellow(red, green, blue)
    }
    pending = set(raw)
    selected: set[int] = set()
    while pending:
        start = pending.pop()
        component = {start}
        queue = deque([start])
        touches_transparency = False
        while queue:
            index = queue.popleft()
            x = index % width
            y = index // width
            for dx, dy in _NEIGHBORS:
                nx, ny = x + dx, y + dy
                if nx < 0 or nx >= width or ny < 0 or ny >= height:
                    touches_transparency = True
                    continue
                neighbor = ny * width + nx
                if pixels[neighbor][3] == 0:
                    touches_transparency = True
                if neighbor in pending:
                    pending.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        if touches_transparency and len(component) <= 128:
            selected.update(component)

    remaining = set(selected)
    changed = 0
    while remaining:
        replacements: dict[int, tuple[int, int, int]] = {}
        for index in remaining:
            x = index % width
            y = index // width
            neighbors = []
            for dx, dy in _NEIGHBORS:
                nx, ny = x + dx, y + dy
                if nx < 0 or nx >= width or ny < 0 or ny >= height:
                    continue
                neighbor = ny * width + nx
                red, green, blue, alpha = pixels[neighbor]
                if (
                    neighbor in remaining
                    or alpha == 0
                    or _is_neon_yellow(red, green, blue)
                ):
                    continue
                neighbors.append((red, green, blue))
            if neighbors:
                replacements[index] = tuple(
                    median_low(color[channel] for color in neighbors)
                    for channel in range(3)
                )
        if not replacements:
            break
        for index, color in replacements.items():
            alpha = pixels[index][3]
            pixels[index] = (*color, alpha)
            changed += 1
        remaining.difference_update(replacements)

    removed = len(remaining)
    for index in remaining:
        pixels[index] = (0, 0, 0, 0)
    for index, (_, _, _, alpha) in enumerate(pixels):
        if alpha == 0:
            pixels[index] = (0, 0, 0, 0)

    cleaned = Image.new("RGBA", rgba.size)
    cleaned.putdata(pixels)
    return cleaned, {
        "yellow_artifact_pixels": len(selected),
        "yellow_changed_pixels": changed,
        "yellow_removed_pixels": removed,
    }


def clean_colored_edge(image: Image.Image) -> tuple[Image.Image, dict[str, object]]:
    current = image.convert("RGBA")
    combined: dict[str, object] | None = None
    post_detected = 0
    passes = 0
    for passes in range(1, 5):
        current, report = _clean_colored_edge_once(current)
        if combined is None:
            combined = report.copy()
        else:
            for key in (
                "changed_pixels",
                "removed_matte_pixels",
                "removed_detached_pixels",
            ):
                combined[key] = int(combined[key]) + int(report[key])
            first_bbox = combined["matte_bbox"]
            next_bbox = report["matte_bbox"]
            if first_bbox is None:
                combined["matte_bbox"] = next_bbox
            elif next_bbox is not None:
                combined["matte_bbox"] = [
                    min(first_bbox[0], next_bbox[0]),
                    min(first_bbox[1], next_bbox[1]),
                    max(first_bbox[2], next_bbox[2]),
                    max(first_bbox[3], next_bbox[3]),
                ]
        connected, _ = _connected_spill(current)
        post_detected = sum(1 for value in connected if value)
        if post_detected == 0:
            break

    assert combined is not None
    combined["passes"] = passes
    combined["post_detected_pixels"] = post_detected
    combined["unresolved_pixels"] = post_detected
    current, yellow_report = _clean_neon_yellow_edge(current)
    combined.update(yellow_report)
    return current, combined


def clean_directory(source_root: Path, output_root: Path) -> dict[str, object]:
    source_root = Path(source_root)
    output_root = Path(output_root)
    paths = sorted(path for path in source_root.rglob("*.png") if path.is_file())
    if not paths:
        raise ValueError(f"no PNG files found under {source_root}")

    files: list[dict[str, object]] = []
    for source in paths:
        relative = source.relative_to(source_root)
        target = output_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            cleaned, details = clean_colored_edge(image)
        cleaned.save(target, "PNG")
        files.append({"path": relative.as_posix(), **details})

    return {
        "source": str(source_root),
        "output": str(output_root),
        "file_count": len(files),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove connected colored edge contamination from RGBA PNGs."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    report = clean_directory(arguments.source, arguments.output)
    if arguments.report is not None:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"OK: cleaned {report['file_count']} PNG files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

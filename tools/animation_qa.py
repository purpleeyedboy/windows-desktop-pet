"""Write deterministic visual and numeric QA for a 30-frame action."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageDraw


FRAME_COUNT = 30
EXPECTED_SIZE = (512, 768)
NORMAL_DURATION_MS = 33
SLOW_DURATION_MS = 132
ARTIFACT_NAMES = (
    "contact-sheet.png",
    "normal.gif",
    "slow.gif",
    "stats.json",
)


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as error:  # pragma: no cover - exercised by environment setup
        raise RuntimeError("animation QA requires requirements-assets.txt") from error
    return np


def _png_sha256(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def _alpha_centroid(alpha: Any) -> list[float] | None:
    np = _numpy()
    total = float(alpha.sum())
    if total <= 0.0:
        return None
    y_coordinates, x_coordinates = np.indices(alpha.shape, dtype=np.float64)
    return [
        round(float((x_coordinates * alpha).sum() / total), 6),
        round(float((y_coordinates * alpha).sum() / total), 6),
    ]


def _largest_component_ratio(mask: Any) -> float:
    np = _numpy()
    total = int(mask.sum())
    if total == 0:
        return 0.0
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    largest = 0
    for start_y, start_x in zip(*np.nonzero(mask & ~visited), strict=True):
        if visited[start_y, start_x]:
            continue
        stack = [(int(start_y), int(start_x))]
        visited[start_y, start_x] = True
        component_size = 0
        while stack:
            y, x = stack.pop()
            component_size += 1
            for next_y, next_x in (
                (y - 1, x),
                (y + 1, x),
                (y, x - 1),
                (y, x + 1),
            ):
                if (
                    0 <= next_y < height
                    and 0 <= next_x < width
                    and mask[next_y, next_x]
                    and not visited[next_y, next_x]
                ):
                    visited[next_y, next_x] = True
                    stack.append((next_y, next_x))
        largest = max(largest, component_size)
    return round(largest / total, 6)


def _edge_chroma_count(rgba: Any) -> int:
    np = _numpy()
    alpha = rgba[..., 3]
    edge = (alpha > 0) & (alpha < 255)
    rgb = rgba[..., :3].astype(np.int16)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    return int((edge & (chroma >= 24)).sum())


def _shift_mask(mask: Any, delta_x: int, delta_y: int) -> Any:
    np = _numpy()
    shifted = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape
    source_x0 = max(0, -delta_x)
    source_x1 = min(width, width - delta_x)
    source_y0 = max(0, -delta_y)
    source_y1 = min(height, height - delta_y)
    if source_x0 >= source_x1 or source_y0 >= source_y1:
        return shifted
    target_x0 = source_x0 + delta_x
    target_x1 = source_x1 + delta_x
    target_y0 = source_y0 + delta_y
    target_y1 = source_y1 + delta_y
    shifted[target_y0:target_y1, target_x0:target_x1] = mask[
        source_y0:source_y1, source_x0:source_x1
    ]
    return shifted


def _aligned_mask_iou(
    previous_mask: Any,
    previous_centroid: list[float] | None,
    current_mask: Any,
    current_centroid: list[float] | None,
) -> float | None:
    np = _numpy()
    if previous_centroid is None or current_centroid is None:
        return None
    delta_x = round(current_centroid[0] - previous_centroid[0])
    delta_y = round(current_centroid[1] - previous_centroid[1])
    aligned_previous = _shift_mask(previous_mask, delta_x, delta_y)
    union = np.logical_or(aligned_previous, current_mask)
    union_size = int(union.sum())
    if union_size == 0:
        return None
    intersection_size = int(np.logical_and(aligned_previous, current_mask).sum())
    return round(intersection_size / union_size, 6)


def _frame_stats(
    image: Image.Image,
    index: int,
    previous_mask: Any | None,
    previous_centroid: list[float] | None,
) -> tuple[dict[str, object], Any, list[float] | None]:
    np = _numpy()
    rgba = np.asarray(image, dtype=np.uint8)
    alpha = rgba[..., 3].astype(np.float64)
    mask = alpha > 0
    centroid = _alpha_centroid(alpha)
    bbox = image.getchannel("A").getbbox()
    aligned_iou = None
    if previous_mask is not None:
        aligned_iou = _aligned_mask_iou(
            previous_mask, previous_centroid, mask, centroid
        )
    stats = {
        "index": index,
        "name": f"{index:02d}.png",
        "sha256": _png_sha256(image),
        "alpha_bbox": list(bbox) if bbox is not None else None,
        "alpha_centroid": centroid,
        "effective_area": round(float(alpha.sum() / 255.0), 6),
        "largest_component_ratio": _largest_component_ratio(mask),
        "edge_chroma_count": _edge_chroma_count(rgba),
        "aligned_mask_iou": aligned_iou,
    }
    return stats, mask, centroid


def _checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    background = Image.new("RGBA", size, (236, 236, 236, 255))
    draw = ImageDraw.Draw(background)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, min(x + cell - 1, size[0] - 1), min(y + cell - 1, size[1] - 1)),
                    fill=(204, 204, 204, 255),
                )
    return background


def _write_contact_sheet(frames: Sequence[Image.Image], path: Path) -> None:
    columns = 6
    rows = 5
    tile_size = (128, 192)
    label_height = 20
    sheet = Image.new(
        "RGB",
        (columns * tile_size[0], rows * (tile_size[1] + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        column = index % columns
        row = index // columns
        left = column * tile_size[0]
        top = row * (tile_size[1] + label_height)
        tile = _checkerboard(tile_size)
        thumbnail = frame.resize(tile_size, Image.Resampling.LANCZOS)
        tile.alpha_composite(thumbnail)
        sheet.paste(tile.convert("RGB"), (left, top))
        draw.text((left + 4, top + tile_size[1] + 3), f"{index:02d}", fill="black")
    sheet.save(path, "PNG")


def _write_gif(frames: Sequence[Image.Image], path: Path, duration_ms: int) -> None:
    gif_frames = [frame.convert("RGBA") for frame in frames]
    gif_frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
        optimize=False,
    )


def write_action_qa(
    frames: Sequence[Image.Image], output_dir: Path, action: str
) -> dict[str, object]:
    if len(frames) != FRAME_COUNT:
        raise ValueError("animation QA requires exactly 30 frames")
    normalized = []
    for index, frame in enumerate(frames):
        if frame.mode != "RGBA" or frame.size != EXPECTED_SIZE:
            raise ValueError(f"frame {index:02d}: expected 512x768 RGBA")
        normalized.append(frame.copy())

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_contact_sheet(normalized, output_dir / "contact-sheet.png")
    _write_gif(normalized, output_dir / "normal.gif", NORMAL_DURATION_MS)
    _write_gif(normalized, output_dir / "slow.gif", SLOW_DURATION_MS)

    frame_reports = []
    previous_mask = None
    previous_centroid = None
    for index, frame in enumerate(normalized):
        stats, previous_mask, previous_centroid = _frame_stats(
            frame, index, previous_mask, previous_centroid
        )
        frame_reports.append(stats)

    report: dict[str, object] = {
        "action": action,
        "frame_count": FRAME_COUNT,
        "normal_duration_ms": NORMAL_DURATION_MS,
        "slow_duration_ms": SLOW_DURATION_MS,
        "artifacts": list(ARTIFACT_NAMES),
        "frames": frame_reports,
    }
    (output_dir / "stats.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report

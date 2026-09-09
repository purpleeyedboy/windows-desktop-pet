"""Deterministically rebuild approved grooming runtime frames from one source sheet."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter


SHEET_SIZE = (1448, 1086)
GRID = (4, 3)
# The approved atlas is arranged visually, not clipped to mathematical cells:
# some ear tips and hindquarters cross a cell boundary by up to three pixels.
CELL_BLEED = 8
ART_SIZE = (512, 768)
RUNTIME_SIZE = (672, 768)
RUNTIME_OFFSET = (80, 0)
CANONICAL_SHA256 = "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_alpha(mask: Image.Image) -> Image.Image:
    """Make the exterior transparent while keeping enclosed/narrow ink opaque.

    The delivered Alpha reference contains dark paw-detail strokes.  A small
    morphological close is used only to identify the exterior; original edge
    gray values are retained and classified interior strokes become opaque.
    """

    gray = mask.convert("L")
    close_size = 9 if min(gray.size) >= 64 else 3
    closed = gray.filter(ImageFilter.MaxFilter(close_size)).filter(
        ImageFilter.MinFilter(close_size)
    )
    open_pixel = closed.point(lambda value: 255 if value < 128 else 0)
    width, height = gray.size
    exterior = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        queue.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        queue.extend(((0, y), (width - 1, y)))
    while queue:
        x, y = queue.popleft()
        index = y * width + x
        if exterior[index] or not open_pixel.getpixel((x, y)):
            continue
        exterior[index] = 1
        if x: queue.append((x - 1, y))
        if x + 1 < width: queue.append((x + 1, y))
        if y: queue.append((x, y - 1))
        if y + 1 < height: queue.append((x, y + 1))
    source = gray.load()
    interior_mask = Image.new("L", gray.size, 0)
    interior_pixels = interior_mask.load()
    for y in range(height):
        for x in range(width):
            if not exterior[y * width + x]:
                interior_pixels[x, y] = 255
    edge_band = interior_mask.filter(ImageFilter.MaxFilter(5)).load()
    result = Image.new("L", gray.size, 0)
    target = result.load()
    for y in range(height):
        for x in range(width):
            if not exterior[y * width + x]:
                target[x, y] = max(source[x, y], 255)
            elif edge_band[x, y] and source[x, y] >= 8:
                target[x, y] = source[x, y]
    return result


def combine_delivered_sheets(color_path: Path, alpha_path: Path) -> Image.Image:
    """Combine the two delivered 1448x1086 attachments without color edits."""

    color = Image.open(color_path).convert("RGB")
    alpha_reference = Image.open(alpha_path).convert("L")
    if color.size != SHEET_SIZE or alpha_reference.size != SHEET_SIZE:
        raise ValueError("delivered grooming sheets must be 1448x1086")
    color.putalpha(build_alpha(alpha_reference))
    return color


def _largest_component(alpha: Image.Image) -> tuple[list[tuple[int, int]], tuple[int, int]]:
    mask = alpha.convert("L").point(lambda value: 255 if value >= 128 else 0)
    pixels = mask.load()
    width, height = mask.size
    seen = bytearray(width * height)
    largest: list[tuple[int, int]] = []
    for y in range(height):
        for x in range(width):
            offset = y * width + x
            if seen[offset] or not pixels[x, y]:
                continue
            seen[offset] = 1
            pending = [(x, y)]
            component: list[tuple[int, int]] = []
            while pending:
                px, py = pending.pop()
                component.append((px, py))
                for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        neighbor = ny * width + nx
                        if not seen[neighbor] and pixels[nx, ny]:
                            seen[neighbor] = 1
                            pending.append((nx, ny))
            if len(component) > len(largest):
                largest = component
    return largest, (width, height)


def primary_subject_box(alpha: Image.Image) -> tuple[int, int, int, int] | None:
    """Return the largest opaque connected component, excluding adjacent-cell debris."""
    largest, (width, height) = _largest_component(alpha)
    if not largest:
        return None
    left = max(0, min(x for x, _ in largest) - 2)
    top = max(0, min(y for _, y in largest) - 2)
    right = min(width, max(x for x, _ in largest) + 3)
    bottom = min(height, max(y for _, y in largest) + 3)
    return left, top, right, bottom


def isolate_primary_subject(cell: Image.Image) -> Image.Image:
    """Clear every neighboring sprite fragment outside the selected subject."""
    largest, (width, height) = _largest_component(cell.getchannel("A"))
    if not largest:
        raise ValueError("approved grooming cell is empty")
    core = Image.new("L", (width, height), 0)
    core_pixels = core.load()
    for x, y in largest:
        core_pixels[x, y] = 255
    keep = core.filter(ImageFilter.MaxFilter(5))
    clean = cell.copy()
    clean.putalpha(Image.composite(cell.getchannel("A"), Image.new("L", cell.size), keep))
    box = primary_subject_box(clean.getchannel("A"))
    assert box is not None
    return clean.crop(box)


def extract_sheet_subject(sheet: Image.Image, index: int) -> Image.Image:
    """Keep the complete sprite, including approved pixels across grid lines."""
    if sheet.size != SHEET_SIZE or not 0 <= index < GRID[0] * GRID[1]:
        raise ValueError("invalid approved grooming sheet or frame index")
    width, height = sheet.size
    cell_width, cell_height = width // GRID[0], height // GRID[1]
    column, row = index % GRID[0], index // GRID[0]
    cell = sheet.crop((
        max(0, column * cell_width - CELL_BLEED),
        max(0, row * cell_height - CELL_BLEED),
        min(width, (column + 1) * cell_width + CELL_BLEED),
        min(height, (row + 1) * cell_height + CELL_BLEED),
    ))
    largest, size = _largest_component(cell.getchannel("A"))
    if not largest:
        raise ValueError(f"approved grooming cell {index} is empty")
    if any(x in (0, size[0] - 1) or y in (0, size[1] - 1) for x, y in largest):
        raise ValueError(f"approved grooming cell {index} clips its primary subject")
    return isolate_primary_subject(cell)


def opaque_subject_box(image: Image.Image) -> tuple[int, int, int, int]:
    box = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0).getbbox()
    if box is None:
        raise ValueError("grooming subject has no opaque pixels")
    return box


def import_groom_frames(manifest_path: Path, output_dir: Path) -> tuple[Image.Image, ...]:
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    source = root / data["source"]
    canonical = manifest_path.parents[2] / "rig/v1/source/canonical-idle.png"
    encoded = "".join(source.read_text(encoding="ascii").splitlines())
    png_bytes = base64.b64decode(encoded, validate=True)
    if hashlib.sha256(png_bytes).hexdigest() != data["decoded_png_sha256"]:
        raise ValueError("approved grooming source SHA-256 mismatch")
    if sha256_file(canonical) != CANONICAL_SHA256:
        raise ValueError("canonical idle SHA-256 mismatch")
    from io import BytesIO
    sheet = Image.open(BytesIO(png_bytes)).convert("RGBA")
    if sheet.size != SHEET_SIZE:
        raise ValueError("approved grooming source must be 1448x1086")
    canonical_image = Image.open(canonical).convert("RGBA")
    canonical_box = opaque_subject_box(canonical_image)
    subjects = tuple(extract_sheet_subject(sheet, index) for index in range(12))
    reference_box = opaque_subject_box(subjects[0])
    # Use one scale for the entire action. Per-frame bbox normalization changes
    # body size when ears or a lifted paw change a silhouette's extent.
    scale = (canonical_box[3] - canonical_box[1]) / (reference_box[3] - reference_box[1])
    frames: list[Image.Image] = []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for index in range(12):
        if index in (0, 11):
            art = canonical_image.copy()
        else:
            subject = subjects[index]
            size = (max(1, round(subject.width * scale)), max(1, round(subject.height * scale)))
            subject = subject.resize(size, Image.Resampling.LANCZOS)
            subject_box = opaque_subject_box(subject)
            art = Image.new("RGBA", ART_SIZE)
            x = round((canonical_box[0] + canonical_box[2] - subject_box[0] - subject_box[2]) / 2)
            # Anchor opaque feet, not the transparent crop padding or resampling
            # fringe, to the default pose's ground line.
            y = canonical_box[3] - subject_box[3]
            art.alpha_composite(subject, (x, y))
        runtime = Image.new("RGBA", RUNTIME_SIZE)
        runtime.alpha_composite(art, RUNTIME_OFFSET)
        frames.append(runtime)
        runtime.save(output_dir / f"{index:02d}.png", optimize=True, compress_level=9)
    return tuple(frames)

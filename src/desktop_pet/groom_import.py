"""Deterministically rebuild approved grooming runtime frames from one source sheet."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


SHEET_SIZE = (1448, 1086)
RIGHT_SHEET_SIZE = (1180, 1333)
GRID = (4, 3)
# The approved atlas is arranged visually, not clipped to mathematical cells:
# some ear tips and hindquarters cross a cell boundary by up to three pixels.
CELL_BLEED = 8
ART_SIZE = (512, 768)
RUNTIME_SIZE = (640, 768)
RUNTIME_OFFSET = (64, 0)
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


def extract_sheet_subject(
    sheet: Image.Image, index: int, *, sheet_size: tuple[int, int] = SHEET_SIZE,
) -> Image.Image:
    """Keep the complete sprite, including approved pixels across grid lines."""
    if sheet_size not in (SHEET_SIZE, RIGHT_SHEET_SIZE) or sheet.size != sheet_size or not 0 <= index < GRID[0] * GRID[1]:
        raise ValueError("invalid approved grooming sheet or frame index")
    width, height = sheet.size
    column, row = index % GRID[0], index // GRID[0]
    cell = sheet.crop((
        max(0, column * width // GRID[0] - CELL_BLEED),
        max(0, row * height // GRID[1] - CELL_BLEED),
        min(width, (column + 1) * width // GRID[0] + CELL_BLEED),
        min(height, (row + 1) * height // GRID[1] + CELL_BLEED),
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


def right_replacement_masks() -> tuple[Image.Image, Image.Image, Image.Image]:
    """Reviewed local regions; the generated head, hips and extra foot stay out."""
    action = Image.new("L", RUNTIME_SIZE)
    draw = ImageDraw.Draw(action)
    draw.ellipse((160, 385, 251, 456), fill=255)
    draw.polygon([(175, 430), (290, 410), (370, 454), (392, 550),
                  (400, 749), (253, 749), (253, 680), (282, 600),
                  (219, 563), (175, 531)], fill=255)
    action = action.filter(ImageFilter.GaussianBlur(4))
    # A stray source bell below the mouth is not part of the licking gesture.
    exclusion = Image.new("L", RUNTIME_SIZE)
    ImageDraw.Draw(exclusion).rectangle((120, 417, 172, 449), fill=255)
    action = ImageChops.subtract(action, exclusion.filter(ImageFilter.GaussianBlur(3)))
    body = Image.new("L", RUNTIME_SIZE)
    ImageDraw.Draw(body).rectangle((246, 620, 408, 747), fill=255)
    body = body.filter(ImageFilter.GaussianBlur(4))
    returning_paw = Image.new("L", RUNTIME_SIZE)
    ImageDraw.Draw(returning_paw).polygon(
        [(292, 600), (368, 600), (364, 750), (262, 750), (268, 680)], fill=255,
    )
    return action, body, returning_paw.filter(ImageFilter.GaussianBlur(6))


def _right_underbelly(root: Path, data: dict, neutral: Image.Image) -> Image.Image:
    from io import BytesIO
    composition = data.get("composition", {})
    if composition.get("mode") != "right-local-limb-and-mouth-v1":
        raise ValueError("right grooming requires the reviewed local replacement composition")
    if hashlib.sha256(neutral.tobytes()).hexdigest() != composition["neutral_rgba_sha256"]:
        raise ValueError("right grooming neutral differs from the reviewed runtime renderer")
    if composition.get("source_translation") != [-44, 0]:
        raise ValueError("right grooming source alignment has changed")
    spec = composition["underbelly"]
    encoded = "".join((root / spec["source"]).read_text("ascii").splitlines())
    payload = base64.b64decode(encoded, validate=True)
    if hashlib.sha256(payload).hexdigest() != spec["decoded_png_sha256"]:
        raise ValueError("right grooming underbelly PNG hash mismatch")
    patch = Image.open(BytesIO(payload)).convert("RGBA")
    if hashlib.sha256(patch.tobytes()).hexdigest() != spec["decoded_rgba_sha256"]:
        raise ValueError("right grooming underbelly RGBA hash mismatch")
    if spec["crop"] != [232, 606, 423, 762] or patch.size != (191, 156):
        raise ValueError("right grooming underbelly crop has changed")
    layer = Image.new("RGBA", RUNTIME_SIZE)
    layer.paste(patch, (232, 606))
    return layer


def _right_local_frame(source: Image.Image, neutral: Image.Image,
                       underbelly: Image.Image, index: int) -> Image.Image:
    action, body, returning_paw = right_replacement_masks()
    aligned = Image.new("RGBA", RUNTIME_SIZE)
    aligned.alpha_composite(source, (-44, 0))
    result = neutral.copy()
    # RGBA replacement is intentional: alpha-composite would retain the old
    # grounded paw in the newly exposed transparent gap.
    result.paste(aligned, (0, 0), action)
    result.paste(underbelly, (0, 0), body)
    if index == 10:
        result.paste(neutral, (0, 0), returning_paw)
    changed = ImageChops.lighter(action, body)
    # Remove the last magenta chroma only at the new silhouette's edge. Keep
    # its alpha and the canonical image entirely intact (no mask erosion).
    exterior = result.getchannel("A").point(lambda a: 255 if a <= 16 else 0)
    band = exterior.filter(ImageFilter.MaxFilter(7))
    # The generated inner-leg plate has reflected backdrop color a few pixels
    # inside its fur fringe; widen only that lower-body color band, not alpha.
    lower_band = exterior.filter(ImageFilter.MaxFilter(25))
    pixels, edge, lower_edge, local = result.load(), band.load(), lower_band.load(), changed.load()
    box = changed.getbbox()
    assert box is not None
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if not local[x, y]:
                continue
            r, g, b, a = pixels[x, y]
            if a == 0:
                pixels[x, y] = (0, 0, 0, 0)
            elif (lower_edge[x, y] if y >= 560 else edge[x, y]) and r > g + 8 and b > g + 8:
                spill = min(r - g, b - g)
                pixels[x, y] = (r - spill, g, b - spill, a)
    return result


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
    sheet_size = tuple(data.get("sheet_size", SHEET_SIZE))
    if sheet_size not in (SHEET_SIZE, RIGHT_SHEET_SIZE) or sheet.size != sheet_size:
        raise ValueError("approved grooming source does not match a reviewed sheet size")
    if data.get("grid") != list(GRID):
        raise ValueError("approved grooming source must use the reviewed 4x3 grid")
    canonical_image = Image.open(canonical).convert("RGBA")
    # The approved runtime has neutral-eye layers that differ from the older
    # flat canonical image. Restore the actual following renderer at endpoints.
    from .assets import load_head_neck_compositor
    from .head_neck_deformation import HeadPose
    neutral = load_head_neck_compositor().compose(0.0, 0.0, HeadPose(0.0, 0.0))
    if neutral.size != RUNTIME_SIZE:
        raise ValueError("groom canvas must match the actual following renderer")
    underbelly = _right_underbelly(root, data, neutral) if sheet_size == RIGHT_SHEET_SIZE else None
    canonical_box = opaque_subject_box(canonical_image)
    subjects = tuple(extract_sheet_subject(sheet, index, sheet_size=sheet_size) for index in range(12))
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
        if index in (0, 11):
            runtime = neutral.copy()
        elif underbelly is not None:
            runtime = _right_local_frame(runtime, neutral, underbelly, index)
        frames.append(runtime)
        runtime.save(output_dir / f"{index:02d}.png", optimize=True, compress_level=9)
    return tuple(frames)

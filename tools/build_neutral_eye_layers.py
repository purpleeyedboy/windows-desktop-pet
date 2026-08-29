from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Final

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


CANONICAL_SHA256: Final = (
    "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"
)
CANVAS_SIZE: Final = (512, 768)
MOTION_LIMITS: Final = {"x": 1.5, "y": 1.0}
EYE_ANCHORS: Final = {"left": (82.0, 351.0), "right": (163.0, 347.0)}
WARP_FALLOFF: Final = "smoothstep normalized distance-to-boundary"
SHARED_NEUTRAL_SOURCE_BOUNDS: Final = (154, 334, 175, 363)
EYES: Final = ("left", "right")
SUPERSAMPLE: Final = 8
EYE_INTERIOR_POLYGONS: Final = {
    "left": (
        (62, 351),
        (63, 346),
        (65, 341),
        (72, 336),
        (80, 336),
        (85, 336),
        (90, 338),
        (93, 342),
        (95, 348),
        (95, 354),
        (92, 360),
        (88, 364),
        (81, 366),
        (73, 364),
        (67, 361),
        (64, 357),
    ),
    "right": (
        (148, 348),
        (149, 343),
        (153, 338),
        (159, 335),
        (166, 333),
        (171, 333),
        (175, 335),
        (178, 340),
        (179, 344),
        (180, 350),
        (178, 355),
        (176, 359),
        (171, 361),
        (158, 361),
        (152, 358),
        (150, 354),
    ),
}
EYE_FIXED_EXCLUSION_BOXES: Final = {
    "left": ((65, 328, 100, 335), (65, 369, 100, 376)),
    "right": ((147, 323, 181, 333), (147, 363, 181, 371)),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save_png(image: Image.Image, path: Path) -> None:
    image.save(path, format="PNG", optimize=False, compress_level=9)


def _write_json(payload: dict, path: Path) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _reviewed_mask(
    points: tuple[tuple[int, int], ...],
    fixed_exclusions: tuple[tuple[int, int, int, int], ...],
) -> tuple[Image.Image, Image.Image]:
    large = Image.new(
        "L", (CANVAS_SIZE[0] * SUPERSAMPLE, CANVAS_SIZE[1] * SUPERSAMPLE), 0
    )
    ImageDraw.Draw(large).polygon(
        [(x * SUPERSAMPLE, y * SUPERSAMPLE) for x, y in points], fill=255
    )
    antialiased = large.resize(CANVAS_SIZE, Image.Resampling.LANCZOS)
    mask = antialiased.point(
        lambda value: 0 if value < 8 else (255 if value >= 248 else value)
    )
    draw = ImageDraw.Draw(mask)
    for left, top, right, bottom in fixed_exclusions:
        draw.rectangle((left, top, right - 1, bottom - 1), fill=0)
    plateau = mask.point(lambda value: 255 if value == 255 else 0)
    return mask, plateau


def _canonical_surface(canonical: Image.Image, mask: Image.Image) -> Image.Image:
    support = mask.point(lambda value: 255 if value else 0)
    rgb = Image.composite(
        canonical.convert("RGB"), Image.new("RGB", CANVAS_SIZE), support
    )
    surface = rgb.convert("RGBA")
    surface.putalpha(mask)
    return surface


def _support_boundary(mask: Image.Image) -> list[tuple[int, int]]:
    support = mask.point(lambda value: 255 if value else 0)
    boundary = ImageChops.subtract(
        support, support.filter(ImageFilter.MinFilter(3))
    )
    bbox = boundary.getbbox()
    if bbox is None:
        return []
    return [
        (x, y)
        for y in range(bbox[1], bbox[3])
        for x in range(bbox[0], bbox[2])
        if boundary.getpixel((x, y))
    ]


def _bilinear(values: list[int], size: tuple[int, int], x: float, y: float) -> float:
    width, height = size
    x = min(max(x, 0.0), width - 1.0)
    y = min(max(y, 0.0), height - 1.0)
    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    x1 = min(x0 + 1, width - 1)
    y1 = min(y0 + 1, height - 1)
    tx = x - x0
    ty = y - y0
    top = values[y0 * width + x0] * (1.0 - tx) + values[y0 * width + x1] * tx
    bottom = values[y1 * width + x0] * (1.0 - tx) + values[y1 * width + x1] * tx
    return top * (1.0 - ty) + bottom * ty


def _aperture_relative_warp(
    surface: Image.Image,
    aperture: Image.Image,
    anchor: tuple[float, float],
    dx: float,
    dy: float,
) -> Image.Image:
    if dx == 0.0 and dy == 0.0:
        return surface.copy()

    bbox = aperture.getbbox()
    if bbox is None:
        return Image.new("RGBA", CANVAS_SIZE)
    padding = 2
    crop_box = (
        max(0, bbox[0] - padding),
        max(0, bbox[1] - padding),
        min(CANVAS_SIZE[0], bbox[2] + padding),
        min(CANVAS_SIZE[1], bbox[3] + padding),
    )
    cropped = surface.crop(crop_box)
    cropped_alpha = cropped.getchannel("A")
    premultiplied_values = [
        list(ImageChops.multiply(channel, cropped_alpha).getdata())
        for channel in cropped.convert("RGB").split()
    ]
    source_alpha_values = list(cropped_alpha.getdata())
    aperture_crop = aperture.crop(crop_box)
    output_alpha_values = list(aperture_crop.getdata())

    boundary_points = _support_boundary(aperture)
    boundary_set = set(boundary_points)
    anchor_distance = min(
        math.hypot(anchor[0] - x, anchor[1] - y) for x, y in boundary_points
    )
    output_values: list[tuple[int, int, int, int]] = []
    for local_y in range(cropped.height):
        for local_x in range(cropped.width):
            index = local_y * cropped.width + local_x
            output_alpha = output_alpha_values[index]
            if output_alpha == 0:
                output_values.append((0, 0, 0, 0))
                continue

            global_point = (local_x + crop_box[0], local_y + crop_box[1])
            if global_point in boundary_set:
                output_values.append(cropped.getpixel((local_x, local_y)))
                continue

            distance = min(
                math.hypot(global_point[0] - x, global_point[1] - y)
                for x, y in boundary_points
            )
            normalized = min(1.0, distance / anchor_distance)
            weight = normalized * normalized * (3.0 - 2.0 * normalized)
            source_x = local_x - dx * weight
            source_y = local_y - dy * weight
            sampled_alpha = _bilinear(
                source_alpha_values, cropped.size, source_x, source_y
            )
            if sampled_alpha <= 0.0:
                output_values.append((0, 0, 0, output_alpha))
                continue
            rgb = tuple(
                min(
                    255,
                    max(
                        0,
                        round(
                            _bilinear(values, cropped.size, source_x, source_y)
                            * 255.0
                            / sampled_alpha
                        ),
                    ),
                )
                for values in premultiplied_values
            )
            output_values.append((*rgb, output_alpha))

    warped_crop = Image.new("RGBA", cropped.size)
    warped_crop.putdata(output_values)
    warped = Image.new("RGBA", CANVAS_SIZE)
    warped.paste(warped_crop, crop_box[:2])
    return warped


def _remap_shared_neutral_target(
    normalized_target: Image.Image,
    source_bounds: tuple[int, int, int, int],
    target_bounds: tuple[int, int, int, int],
) -> Image.Image:
    remapped = normalized_target.copy()
    source_values = [list(channel.getdata()) for channel in normalized_target.split()]
    source_width = source_bounds[2] - source_bounds[0]
    source_height = source_bounds[3] - source_bounds[1]
    target_width = target_bounds[2] - target_bounds[0]
    target_height = target_bounds[3] - target_bounds[1]
    pixels = remapped.load()
    for y in range(target_bounds[1], target_bounds[3]):
        normalized_y = (y - target_bounds[1]) / max(1, target_height - 1)
        source_y = source_bounds[1] + normalized_y * (source_height - 1)
        for x in range(target_bounds[0], target_bounds[2]):
            normalized_x = (x - target_bounds[0]) / max(1, target_width - 1)
            source_x = source_bounds[0] + normalized_x * (source_width - 1)
            pixels[x, y] = tuple(
                round(
                    _bilinear(
                        values, normalized_target.size, source_x, source_y
                    )
                )
                for values in source_values
            )
    return remapped


def build_assets(
    canonical_path: Path, neutral_candidate_path: Path, output_dir: Path
) -> dict:
    canonical_path = Path(canonical_path)
    neutral_candidate_path = Path(neutral_candidate_path)
    output_dir = Path(output_dir)

    canonical_hash = _sha256(canonical_path)
    if canonical_hash != CANONICAL_SHA256:
        raise ValueError(
            f"canonical SHA-256 mismatch: expected {CANONICAL_SHA256}, got {canonical_hash}"
        )

    canonical_source = Image.open(canonical_path)
    neutral_source = Image.open(neutral_candidate_path)
    if canonical_source.mode != "RGBA" or canonical_source.size != CANVAS_SIZE:
        raise ValueError("canonical source must be RGBA 512x768")
    if neutral_source.mode != "RGB" or neutral_source.size != (1024, 1536):
        raise ValueError("neutral candidate must be RGB 1024x1536")

    canonical = canonical_source.copy()
    normalized_target = neutral_source.resize(
        CANVAS_SIZE, Image.Resampling.LANCZOS
    ).filter(ImageFilter.GaussianBlur(radius=2.0))
    masks = {}
    reviewed_plateaus = {}
    for eye, polygon in EYE_INTERIOR_POLYGONS.items():
        masks[eye], reviewed_plateaus[eye] = _reviewed_mask(
            polygon, EYE_FIXED_EXCLUSION_BOXES[eye]
        )
    shared_source_bounds = SHARED_NEUTRAL_SOURCE_BOUNDS
    underlay_rgb = canonical.convert("RGB").copy()
    for eye, mask in masks.items():
        target_bounds = mask.getbbox()
        assert target_bounds is not None
        eye_target = _remap_shared_neutral_target(
            normalized_target, shared_source_bounds, target_bounds
        )
        underlay_rgb.paste(eye_target, mask=mask)
    underlay = underlay_rgb.convert("RGBA")
    underlay.putalpha(canonical.getchannel("A"))
    surfaces = {
        eye: _canonical_surface(canonical, mask) for eye, mask in masks.items()
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    authored_images = {"underlay.png": underlay}
    for eye in EYES:
        authored_images[f"eye-{eye}.png"] = surfaces[eye]
        authored_images[f"eye-{eye}-mask.png"] = masks[eye]
    for filename, image in authored_images.items():
        _save_png(image, output_dir / filename)

    eyes_metadata = {}
    for eye, mask in masks.items():
        bbox = mask.getbbox()
        assert bbox is not None
        eyes_metadata[eye] = {
            "movement_anchor": list(EYE_ANCHORS[eye]),
            "neutral_texture": "shared generated diffuse globe remapped across full reviewed interior",
            "reviewed_bounds": list(bbox),
            "reviewed_plateau_bounds": list(reviewed_plateaus[eye].getbbox()),
            "reviewed_method": "independently reviewed supersampled eye-interior polygon",
            "fixed_exclusion_boxes": [
                list(box) for box in EYE_FIXED_EXCLUSION_BOXES[eye]
            ],
            "reviewed_polygon": [list(point) for point in EYE_INTERIOR_POLYGONS[eye]],
        }

    metadata = {
        "canonical": {
            "mode": canonical_source.mode,
            "sha256": canonical_hash,
            "size": list(canonical_source.size),
            "source": "assets/rig/v1/source/canonical-idle.png",
        },
        "neutral_candidate": {
            "mode": neutral_source.mode,
            "sha256": _sha256(neutral_candidate_path),
            "size": list(neutral_source.size),
            "source": "assets/rig/v1/source/ai/neutral-eyeball-generated-v1.png",
        },
        "normalized_target": {
            "resampling": "Lanczos RGB resize at exact 1:2 geometry; 2 px Gaussian diffuse-only smoothing",
            "shared_source_bounds": list(shared_source_bounds),
            "shared_source_eye": "right",
            "size": list(normalized_target.size),
        },
        "eyes": eyes_metadata,
        "motion_limits": MOTION_LIMITS,
        "motion_resampling": "premultiplied-alpha bilinear aperture-relative inverse warp",
        "warp": {
            "boundary_displacement": 0.0,
            "falloff": WARP_FALLOFF,
            "shared_field_shape": True,
        },
        "outputs": {
            filename: {
                "mode": image.mode,
                "sha256": _sha256(output_dir / filename),
                "size": list(image.size),
            }
            for filename, image in sorted(authored_images.items())
        },
    }
    _write_json(metadata, output_dir / "authoring.json")
    return metadata


def compose_pose(asset_dir: Path, eye_x: float, eye_y: float) -> Image.Image:
    asset_dir = Path(asset_dir)
    if abs(eye_x) > MOTION_LIMITS["x"] or abs(eye_y) > MOTION_LIMITS["y"]:
        raise ValueError(
            f"eye offset exceeds motion limits ±{MOTION_LIMITS['x']} x and ±{MOTION_LIMITS['y']} y"
        )

    composed = Image.open(asset_dir / "underlay.png").convert("RGBA").copy()
    for eye in EYES:
        surface = Image.open(asset_dir / f"eye-{eye}.png").convert("RGBA")
        aperture = Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L")
        warped = _aperture_relative_warp(
            surface,
            aperture,
            EYE_ANCHORS[eye],
            float(eye_x),
            float(eye_y),
        )
        support = aperture.point(lambda value: 255 if value else 0)
        composed_rgb = Image.composite(
            warped.convert("RGB"), composed.convert("RGB"), support
        )
        alpha = composed.getchannel("A")
        composed = composed_rgb.convert("RGBA")
        composed.putalpha(alpha)
    return composed


def _different_pixel_count(first: Image.Image, second: Image.Image) -> int:
    difference = ImageChops.difference(first, second)
    return sum(pixel != (0, 0, 0, 0) for pixel in difference.getdata())


def _maximum_channel_delta(first: Image.Image, second: Image.Image) -> int:
    return max(channel_max for _, channel_max in ImageChops.difference(first, second).getextrema())


def _checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    board = Image.new("RGBA", size, (78, 78, 78, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(108, 108, 108, 255))
    return board


def build_contact_sheet(asset_dir: Path, qa_dir: Path) -> dict:
    asset_dir = Path(asset_dir)
    qa_dir = Path(qa_dir)
    qa_dir.mkdir(parents=True, exist_ok=True)
    poses = {
        "center": (0.0, 0.0),
        "left": (-1.5, 0.0),
        "right": (1.5, 0.0),
        "up": (0.0, -1.0),
        "down": (0.0, 1.0),
    }
    rendered = {
        name: compose_pose(asset_dir, *offset) for name, offset in poses.items()
    }
    for name, image in rendered.items():
        _save_png(image, qa_dir / f"{name}.png")

    sheet = Image.new("RGBA", (2800, 1500), (28, 30, 34, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((32, 22), "NEUTRAL EYE V1 — STATIC FIXED-APERTURE PROOF", fill="white", font=font)
    draw.text((32, 52), "Full-cat poses", fill=(205, 210, 218), font=font)
    names = list(poses)
    column_width = 560
    for column, name in enumerate(names):
        x = column * column_width + 157
        thumb = rendered[name].resize((246, 369), Image.Resampling.LANCZOS)
        sheet.alpha_composite(thumb, (x, 82))
        draw.text((column * column_width + 255, 460), name.upper(), fill="white", font=font)

    draw.text((32, 505), "4x canonical eye close-ups", fill=(205, 210, 218), font=font)
    eye_crop = (52, 310, 192, 386)
    for column, name in enumerate(names):
        closeup = rendered[name].crop(eye_crop).resize(
            (560, 304), Image.Resampling.NEAREST
        )
        sheet.alpha_composite(closeup, (column * column_width, 535))
        draw.text(
            (column * column_width + 248, 848), name.upper(), fill="white", font=font
        )

    draw.text((32, 895), "Authored layer close-ups", fill=(205, 210, 218), font=font)
    layer_specs = [
        ("UNDERLAY", Image.open(asset_dir / "underlay.png").convert("RGBA")),
        ("LEFT SURFACE", Image.open(asset_dir / "eye-left.png").convert("RGBA")),
        ("RIGHT SURFACE", Image.open(asset_dir / "eye-right.png").convert("RGBA")),
        ("LEFT MASK", Image.open(asset_dir / "eye-left-mask.png").convert("RGBA")),
        ("RIGHT MASK", Image.open(asset_dir / "eye-right-mask.png").convert("RGBA")),
    ]
    for column, (label, layer) in enumerate(layer_specs):
        closeup = layer.crop(eye_crop).resize((560, 304), Image.Resampling.NEAREST)
        panel = _checkerboard(closeup.size)
        panel.alpha_composite(closeup)
        sheet.alpha_composite(panel, (column * column_width, 925))
        draw.text(
            (column * column_width + 225, 1238), label, fill="white", font=font
        )
    draw.text(
        (32, 1418),
        "Fixed eyelids/rims. Shared target limits: horizontal ±1.5 px, vertical ±1.0 px.",
        fill=(205, 210, 218),
        font=font,
    )
    _save_png(sheet, qa_dir / "layer-contact-sheet.png")

    metadata = json.loads((asset_dir / "authoring.json").read_text(encoding="utf-8"))
    canonical_path = Path(__file__).resolve().parents[1] / metadata["canonical"]["source"]
    canonical = Image.open(canonical_path).convert("RGBA")
    stats = {
        "center": {
            "changed_pixels": _different_pixel_count(rendered["center"], canonical),
            "maximum_channel_delta": _maximum_channel_delta(rendered["center"], canonical),
        },
        "poses": {
            name: {
                "anchor_displacement": list(offset),
                "offset": list(offset),
                "sha256": _sha256(qa_dir / f"{name}.png"),
            }
            for name, offset in poses.items()
        },
        "contact_sheet": {
            "sha256": _sha256(qa_dir / "layer-contact-sheet.png"),
            "size": list(sheet.size),
        },
        "motion_limits": MOTION_LIMITS,
        "warp": {
            "boundary_displacement": 0.0,
            "falloff": WARP_FALLOFF,
        },
        "r5_status": "BLOCKED pending explicit static visual approval",
    }
    _write_json(stats, qa_dir / "stats.json")
    return stats


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build neutral eye layers and static QA evidence")
    parser.add_argument(
        "--canonical",
        type=Path,
        default=root / "assets/rig/v1/source/canonical-idle.png",
    )
    parser.add_argument(
        "--neutral-candidate",
        type=Path,
        default=root / "assets/rig/v1/source/ai/neutral-eyeball-generated-v1.png",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "assets/rig/v1/source/eye-neutral-v1",
    )
    parser.add_argument(
        "--qa-dir", type=Path, default=root / "qa/neutral-eye-v1/candidate"
    )
    arguments = parser.parse_args()
    build_assets(arguments.canonical, arguments.neutral_candidate, arguments.output_dir)
    build_contact_sheet(arguments.output_dir, arguments.qa_dir)


if __name__ == "__main__":
    main()

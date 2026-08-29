from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ARTIFACTS = (
    "center-contact-sheet.png",
    "center-backgrounds.png",
    "center-closeups.png",
    "center-difference.png",
    "center-stats.json",
)
DISPLAY_HEIGHTS = (180, 280, 420)
BACKGROUNDS = ((255, 255, 255), (128, 128, 128), (0, 0, 0))
CLOSEUPS = {
    "eyes": (48, 304, 194, 390),
    "neck_seam": (72, 420, 236, 580),
    "ears": (20, 196, 254, 326),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _open_rgba(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        return opened.convert("RGBA")


def _render_on(
    image: Image.Image, height: int, color: tuple[int, int, int]
) -> Image.Image:
    width = round(image.width * height / image.height)
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    background = Image.new("RGBA", (width, height), (*color, 255))
    background.alpha_composite(resized)
    return background.convert("RGB")


def _contact_sheet(items: list[tuple[str, Image.Image]]) -> Image.Image:
    thumb = (160, 240)
    margin, label_height = 10, 24
    sheet = Image.new(
        "RGB",
        ((thumb[0] + margin) * len(items) + margin, thumb[1] + label_height + 2 * margin),
        (42, 42, 48),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (label, image) in enumerate(items):
        x = margin + index * (thumb[0] + margin)
        checker = Image.new("RGBA", thumb, (196, 196, 196, 255))
        checker.alpha_composite(image.resize(thumb, Image.Resampling.LANCZOS))
        sheet.paste(checker.convert("RGB"), (x, margin + label_height))
        draw.text((x, margin + 5), label, fill=(255, 255, 255), font=font)
    return sheet


def _background_sheet(composite: Image.Image) -> Image.Image:
    columns = []
    for height in DISPLAY_HEIGHTS:
        rows = [_render_on(composite, height, color) for color in BACKGROUNDS]
        width = max(row.width for row in rows)
        column = Image.new(
            "RGB", (width, sum(row.height for row in rows)), (32, 32, 32)
        )
        top = 0
        for row in rows:
            column.paste(row, ((width - row.width) // 2, top))
            top += row.height
        columns.append(column)
    sheet = Image.new(
        "RGB",
        (sum(column.width for column in columns), max(column.height for column in columns)),
        (32, 32, 32),
    )
    left = 0
    for column in columns:
        sheet.paste(column, (left, 0))
        left += column.width
    return sheet


def _closeup_sheet(canonical: Image.Image, composite: Image.Image) -> Image.Image:
    panels = []
    for label, box in CLOSEUPS.items():
        size = ((box[2] - box[0]) * 4, (box[3] - box[1]) * 4)
        first = canonical.crop(box).resize(size, Image.Resampling.NEAREST)
        second = composite.crop(box).resize(size, Image.Resampling.NEAREST)
        panel = Image.new("RGB", (first.width * 2, first.height + 24), (32, 32, 32))
        panel.paste(first.convert("RGB"), (0, 24))
        panel.paste(second.convert("RGB"), (first.width, 24))
        ImageDraw.Draw(panel).text(
            (5, 6),
            f"{label}: canonical | composite",
            fill=(255, 255, 255),
            font=ImageFont.load_default(),
        )
        panels.append(panel)
    width = max(panel.width for panel in panels)
    sheet = Image.new("RGB", (width, sum(panel.height for panel in panels)), (32, 32, 32))
    top = 0
    for panel in panels:
        sheet.paste(panel, (0, top))
        top += panel.height
    return sheet


def _alpha_evidence(images: dict[str, Image.Image]) -> dict[str, object]:
    per_image: dict[str, dict[str, object]] = {}
    hidden_rgb = 0
    all_borders_transparent = True
    for name, image in images.items():
        violations = sum(
            1
            for r, g, b, a in image.getdata()
            if a == 0 and (r, g, b) != (0, 0, 0)
        )
        border_boxes = (
            (0, 0, image.width, 1),
            (0, image.height - 1, image.width, image.height),
            (0, 0, 1, image.height),
            (image.width - 1, 0, image.width, image.height),
        )
        border_transparent = all(
            image.getchannel("A").crop(box).getbbox() is None for box in border_boxes
        )
        hidden_rgb += violations
        all_borders_transparent = all_borders_transparent and border_transparent
        per_image[name] = {
            "mode": image.mode,
            "size": list(image.size),
            "alpha_zero_rgb_violations": violations,
            "outer_border_transparent": border_transparent,
        }
    return {
        "alpha_zero_rgb_violations": hidden_rgb,
        "outer_border_transparent": all_borders_transparent,
        "canonical_composite_alpha_matches": (
            images["canonical"].getchannel("A").tobytes()
            == images["composite"].getchannel("A").tobytes()
        ),
        "images": per_image,
    }


def _count_clipped_pixels_outside_mask(
    generated_path: Path, mask: Image.Image, canvas: tuple[int, int]
) -> int:
    if not generated_path.is_file():
        return 0
    generated = _open_rgba(generated_path)
    if generated.size != canvas:
        generated = generated.resize(canvas, Image.Resampling.LANCZOS)
    clipped_alpha = ImageChops.multiply(generated.getchannel("A"), mask)
    return sum(
        1
        for clipped, allowed in zip(clipped_alpha.getdata(), mask.getdata())
        if clipped and not allowed
    )


def _ai_containment(source_root: Path, canvas: tuple[int, int]) -> dict[str, object]:
    masks_root = source_root / "masks"
    with Image.open(masks_root / "body-fill-mask.png") as opened:
        body_mask = opened.convert("L")
    with Image.open(masks_root / "eye-left-mask.png") as opened:
        eye_left = opened.convert("L")
    with Image.open(masks_root / "eye-right-mask.png") as opened:
        eye_right = opened.convert("L")
    eye_masks = ImageChops.lighter(eye_left, eye_right)
    body_outside = _count_clipped_pixels_outside_mask(
        source_root / "ai" / "body-fill-raw.png", body_mask, canvas
    )
    eye_outside = _count_clipped_pixels_outside_mask(
        source_root / "ai" / "eye-fill-raw.png", eye_masks, canvas
    )
    return {
        "body_fill_outside_mask_pixels": body_outside,
        "eye_fill_outside_masks_pixels": eye_outside,
        "passed": body_outside == 0 and eye_outside == 0,
    }


def write_center_qa(
    source_root: Path, sample_root: Path, qa_root: Path
) -> dict[str, object]:
    source_root = Path(source_root)
    sample_root = Path(sample_root)
    qa_root = Path(qa_root)
    qa_root.mkdir(parents=True, exist_ok=True)
    layers_root = source_root / "layers"
    paths = {
        "canonical": source_root / "canonical-idle.png",
        "body_base": layers_root / "body_base.png",
        "head_neck": layers_root / "head_neck_base.png",
        "eye_left": layers_root / "eye_left.png",
        "eye_right": layers_root / "eye_right.png",
        "composite": sample_root / "composite.png",
    }
    images = {name: _open_rgba(path) for name, path in paths.items()}
    difference = ImageChops.difference(images["canonical"], images["composite"])
    difference_pixels = list(difference.getdata())
    changed_pixels = sum(pixel != (0, 0, 0, 0) for pixel in difference_pixels)
    maximum_delta = max(max(pixel) for pixel in difference_pixels)
    exact_recomposition = {
        "matches": changed_pixels == 0 and maximum_delta == 0,
        "changed_pixels": changed_pixels,
        "maximum_channel_delta": maximum_delta,
    }
    alpha = _alpha_evidence(images)

    _contact_sheet(
        [
            ("canonical", images["canonical"]),
            ("body_base", images["body_base"]),
            ("head_neck", images["head_neck"]),
            ("eye_left", images["eye_left"]),
            ("eye_right", images["eye_right"]),
            ("composite", images["composite"]),
        ]
    ).save(qa_root / "center-contact-sheet.png")
    _background_sheet(images["composite"]).save(qa_root / "center-backgrounds.png")
    _closeup_sheet(images["canonical"], images["composite"]).save(
        qa_root / "center-closeups.png"
    )
    difference.convert("RGB").point(lambda value: min(255, value * 16)).save(
        qa_root / "center-difference.png"
    )

    mask_paths = {
        "eye_left_mask.png": layers_root / "eye_left_mask.png",
        "eye_right_mask.png": layers_root / "eye_right_mask.png",
    }
    mask_boxes: dict[str, list[int]] = {}
    for name, path in mask_paths.items():
        with Image.open(path) as mask:
            mask_boxes[name] = list(mask.getbbox() or ())

    report = {
        "artifacts": list(ARTIFACTS),
        "exact_recomposition": exact_recomposition,
        "changed_pixels": changed_pixels,
        "maximum_channel_delta": maximum_delta,
        "alpha": alpha,
        "alpha_zero_rgb_violations": alpha["alpha_zero_rgb_violations"],
        "outer_border_transparent": alpha["outer_border_transparent"],
        "canonical_sha256": _sha256(paths["canonical"]),
        "layer_sha256": {
            name: _sha256(path) for name, path in paths.items() if name != "canonical"
        },
        "mask_sha256": {name: _sha256(path) for name, path in mask_paths.items()},
        "mask_boxes": mask_boxes,
        "ai_containment": _ai_containment(source_root, images["canonical"].size),
    }
    (qa_root / "center-stats.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report

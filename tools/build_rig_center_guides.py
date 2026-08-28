from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


CANVAS = (512, 768)
DYNAMIC_POLYGON = ((24, 202), (246, 202), (263, 370), (242, 455), (221, 564), (105, 564), (80, 470), (32, 430))
BODY_FILL_POLYGON = ((96, 390), (168, 365), (220, 390), (235, 450), (215, 550), (112, 550), (88, 470))
EYE_LEFT = (60, 325, 104, 380)
EYE_RIGHT = (139, 319, 184, 375)
LANDMARKS = {
    "ear_left_tip": [38, 222], "ear_left_root": [87, 310],
    "ear_right_tip": [223, 213], "ear_right_root": [194, 312],
    "eye_left": [82, 351], "eye_right": [161, 347],
    "nose": [118, 397], "jaw": [122, 451],
    "neck_left": [93, 454], "neck_right": [205, 454],
    "chest_left": [108, 555], "chest_right": [207, 555],
}


def _polygon(points: tuple[tuple[int, int], ...]) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask


def _ellipse(box: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    return mask


def _guide(source: Image.Image, mask: Image.Image) -> Image.Image:
    marker = Image.new("RGBA", CANVAS, (0, 255, 0, 255))
    return Image.composite(marker, source, mask)


def build_guides(canonical_path: Path, output_root: Path) -> dict[str, object]:
    with Image.open(canonical_path) as opened:
        canonical = opened.convert("RGBA")
    output_root = Path(output_root)
    masks = output_root / "masks"
    guides = output_root / "guides"
    masks.mkdir(parents=True, exist_ok=True)
    guides.mkdir(parents=True, exist_ok=True)
    generated = {
        "dynamic-head-neck-mask.png": _polygon(DYNAMIC_POLYGON),
        "body-fill-mask.png": _polygon(BODY_FILL_POLYGON),
        "eye-left-mask.png": _ellipse(EYE_LEFT),
        "eye-right-mask.png": _ellipse(EYE_RIGHT),
    }
    subject = canonical.getchannel("A").point(lambda value: 255 if value else 0)
    for name in ("body-fill-mask.png", "eye-left-mask.png", "eye-right-mask.png"):
        if ImageChops.subtract(generated[name], subject).getbbox() is not None:
            raise RuntimeError(f"{name} extends outside canonical subject; NEEDS_CONTEXT")
    for name, image in generated.items():
        image.save(masks / name)
    _guide(canonical, generated["body-fill-mask.png"]).save(guides / "body-fill-guide.png")
    eye_union = ImageChops.lighter(generated["eye-left-mask.png"], generated["eye-right-mask.png"])
    _guide(canonical, eye_union).save(guides / "eye-fill-guide.png")
    report = {"canvas": list(CANVAS), "landmarks": LANDMARKS, "masks": sorted(generated)}
    (output_root / "authoring.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report

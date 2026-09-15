#!/usr/bin/env python3
"""Deterministically rebuild runtime hunger frames from one RGBA sprite source."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys

from PIL import Image, ImageDraw, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "assets/hunger/source"
RUNTIME_ROOT = ROOT / "assets/hunger/v1"
CANONICAL = ROOT / "assets/rig/v1/source/canonical-idle.png"
CANONICAL_SHA256 = "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"
CANVAS = (512, 768)
RUNTIME_CANVAS = (640, 768)
RUNTIME_OFFSET = (64, 0)
FIXED_BASE_RGBA_SHA256 = "e02f052cb970d2ebed4946ad0f09038adbce4d41da3a730e09e56783054e5eb0"
MUTABLE_RUNTIME_REGIONS = ((138, 386, 224, 442), (128, 355, 166, 424), (211, 352, 254, 424))
FACE_LANDMARKS = {
    "hungry_open": ((202, 372), (175, 339), (261, 339)),
    "severe_tears": ((201, 369), (175, 338), (261, 339)),
    "critical_open": ((202, 363), (172, 330), (261, 333)),
    "critical_closed": ((202, 371), (174, 338), (262, 341)),
}


def _fixed_runtime_base() -> Image.Image:
    sys.path.insert(0, str(ROOT / "src"))
    from desktop_pet.assets import load_head_neck_compositor
    from desktop_pet.head_neck_deformation import HeadPose
    base = load_head_neck_compositor().compose(0.0, 0.0, HeadPose(0.0, 0.0))
    if base.size != RUNTIME_CANVAS or _sha(base.tobytes()) != FIXED_BASE_RGBA_SHA256:
        raise ValueError("actual accepted runtime neutral does not match the fixed composition base")
    return base


def _compose_local_expression(base: Image.Image, authored: Image.Image, name: str) -> Image.Image:
    """Use only generated mouth/tear pixels, keeping the complete base alpha."""
    source = Image.new("RGBA", RUNTIME_CANVAS, (0, 0, 0, 0))
    source.alpha_composite(authored, RUNTIME_OFFSET)
    result = base.copy()
    solid_base = base.getchannel("A").point(lambda alpha: 255 if alpha == 255 else 0)

    def apply_patch(source_point, target_point, box, y_scale=1.0):
        transformed = source.transform(
            RUNTIME_CANVAS, Image.Transform.AFFINE,
            (1, 0, source_point[0] - target_point[0],
             0, 1 / y_scale, source_point[1] - target_point[1] / y_scale),
            Image.Resampling.BICUBIC,
        )
        mask = Image.new("L", RUNTIME_CANVAS, 0)
        ImageDraw.Draw(mask).ellipse(box, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(1.5))
        mask = ImageChops.multiply(mask, solid_base)
        mask = ImageChops.multiply(mask, transformed.getchannel("A"))
        result.paste(transformed, (0, 0), mask)
        result.putalpha(base.getchannel("A"))

    nose, left_eye, right_eye = FACE_LANDMARKS[name]
    if name != "critical_closed":
        apply_patch(nose, (170, 383), (142, 390, 219, 437), 0.88)
    if name != "hungry_open":
        bottom = 391 if name == "severe_tears" else 419
        apply_patch(left_eye, (143, 350), (132, 359, 161, bottom))
        apply_patch(right_eye, (225, 349), (215, 356, 249, bottom))
    # Keep the original frame-library format; adding its declared 64px padding
    # reconstructs the true 640px base exactly, rather than canonical-idle.png.
    authored_result = result.crop((64, 0, 576, 768))
    repadded = Image.new("RGBA", RUNTIME_CANVAS)
    repadded.alpha_composite(authored_result, RUNTIME_OFFSET)
    if repadded.tobytes() != result.tobytes():
        raise ValueError("fixed runtime composition cannot be represented by the declared padding")
    return authored_result



def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _png(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, "PNG", optimize=False, compress_level=9)
    return stream.getvalue()


def _read_source(manifest: dict) -> Image.Image:
    path = SOURCE_ROOT / manifest["source_file"]
    encoded = b"".join(path.read_bytes().split())
    data = base64.b64decode(encoded, validate=True)
    if _sha(data) != manifest["source_webp_sha256"]:
        raise ValueError("hunger source WebP hash does not match source manifest")
    with Image.open(io.BytesIO(data)) as opened:
        if opened.format != "WEBP":
            raise ValueError("hunger source must use lossless WebP encoding")
        image = opened.convert("RGBA")
    if list(image.size) != manifest["source_canvas"]:
        raise ValueError("hunger source must use the declared sprite canvas")
    if _sha(image.tobytes()) != manifest["source_rgba_sha256"]:
        raise ValueError("decoded hunger RGBA pixels do not match source manifest")
    return image


def _normalize_pose(source: Image.Image, box: list[int]) -> Image.Image:
    cell = source.crop(tuple(box))
    alpha = cell.getchannel("A")
    subject = alpha.point(lambda value: 255 if value >= 16 else 0).getbbox()
    if subject is None:
        raise ValueError(f"empty hunger pose cell: {box}")
    pose = cell.crop(subject)
    canonical_bbox = (32, 212, 480, 736)
    # Preserve the supplied pose's aspect ratio. Fit it inside the canonical
    # connected-cat bounds, then align its feet and horizontal centre.
    maximum_width = canonical_bbox[2] - canonical_bbox[0]
    maximum_height = canonical_bbox[3] - canonical_bbox[1]
    scale = min(maximum_width / pose.width, maximum_height / pose.height)
    target_size = (round(pose.width * scale), round(pose.height * scale))
    pose = pose.resize(target_size, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    target_x = CANVAS[0] // 2 - target_size[0] // 2
    target_y = canonical_bbox[3] - target_size[1]
    output.alpha_composite(pose, (target_x, target_y))
    normalized_alpha = output.getchannel("A").point(
        lambda value: 255 if value >= 16 else 0
    )
    normalized_bbox = normalized_alpha.getbbox()
    if normalized_bbox is None:
        raise ValueError(f"normalized pose is empty: {box}")
    left, top, right, bottom = normalized_bbox
    if bottom != canonical_bbox[3] or abs((left + right) - CANVAS[0]) > 1:
        raise ValueError(f"normalized pose missed foot or centre anchor: {box}")
    if left < canonical_bbox[0] or top < canonical_bbox[1] or right > canonical_bbox[2]:
        raise ValueError(f"normalized pose exceeds canonical fit bounds: {box}")
    corners = ((0, 0), (511, 0), (0, 767), (511, 767))
    if any(output.getpixel(point)[3] for point in corners):
        raise ValueError(f"normalized pose has an opaque canvas corner: {box}")
    return output


def _checkerboard() -> Image.Image:
    image = Image.new("RGBA", CANVAS, "white")
    draw = ImageDraw.Draw(image)
    for y in range(0, CANVAS[1], 16):
        for x in range(0, CANVAS[0], 16):
            if (x // 16 + y // 16) % 2:
                draw.rectangle((x, y, x + 15, y + 15), fill="#b8b8b8")
    return image


def _write_qa(
    poses: dict[str, Image.Image],
    qa_root: Path,
    runtime_root: Path,
    sequences: dict[str, list[dict]],
) -> None:
    qa_root.mkdir(parents=True, exist_ok=True)
    backgrounds = {"black": "black", "white": "white"}
    for name, color in backgrounds.items():
        sheet = Image.new("RGB", (CANVAS[0] * 2, CANVAS[1] * 2), color)
        for index, pose in enumerate(poses.values()):
            backdrop = Image.new("RGBA", CANVAS, color)
            backdrop.alpha_composite(pose)
            sheet.paste(backdrop.convert("RGB"), ((index % 2) * 512, (index // 2) * 768))
        sheet.save(qa_root / f"hunger-contact-{name}.png", compress_level=9)
    checker = Image.new("RGB", (CANVAS[0] * 2, CANVAS[1] * 2), "white")
    for index, pose in enumerate(poses.values()):
        backdrop = _checkerboard()
        backdrop.alpha_composite(pose)
        checker.paste(backdrop.convert("RGB"), ((index % 2) * 512, (index // 2) * 768))
    checker.save(qa_root / "hunger-contact-checker.png", compress_level=9)
    for name, entries in sequences.items():
        previews = []
        for entry in entries:
            with Image.open(runtime_root / entry["file"]) as opened:
                backdrop = _checkerboard()
                backdrop.alpha_composite(opened.convert("RGBA"))
                previews.append(backdrop.convert("RGB"))
        previews[0].save(
            qa_root / f"hunger-{name}.gif",
            save_all=True,
            append_images=previews[1:],
            duration=[entry["duration_ms"] for entry in entries],
            loop=0,
            disposal=2,
        )


def build(runtime_root: Path, qa_root: Path | None) -> dict:
    source_manifest = json.loads((SOURCE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    if source_manifest.get("version") != 1:
        raise ValueError("unsupported hunger source manifest")
    canonical_data = CANONICAL.read_bytes()
    if _sha(canonical_data) != CANONICAL_SHA256:
        raise ValueError("approved canonical idle hash does not match")
    source = _read_source(source_manifest)
    generated_poses = {
        pose["id"]: _normalize_pose(source, pose["cell"])
        for pose in source_manifest["poses"]
    }
    fixed_base = _fixed_runtime_base()
    canonical_frame = fixed_base.crop((64, 0, 576, 768))
    poses = {
        name: _compose_local_expression(fixed_base, authored, name)
        for name, authored in generated_poses.items()
    }
    staged = runtime_root.with_name(runtime_root.name + ".building")
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)
    sequences: dict[str, list[dict]] = {}
    try:
        for sequence, entries in source_manifest["sequences"].items():
            sequences[sequence] = []
            for index, entry in enumerate(entries):
                image = (
                    canonical_frame
                    if entry["pose"] == "canonical"
                    else poses[entry["pose"]]
                )
                data = _png(image)
                relative = f"poses/{entry['pose']}.png"
                target = staged / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                sequences[sequence].append({
                    "file": relative,
                    "phase": entry["phase"],
                    "duration_ms": entry["duration_ms"],
                    "png_sha256": _sha(data),
                })
        manifest = {
            "version": 1,
            "frame_type": "full-frame",
            "encoding": "png",
            "canvas": list(CANVAS),
            "anchor": [256, 768],
            "runtime_canvas": list(RUNTIME_CANVAS),
            "runtime_offset": list(RUNTIME_OFFSET),
            "canonical_idle_sha256": CANONICAL_SHA256,
            "source_webp_sha256": source_manifest["source_webp_sha256"],
            "source_rgba_sha256": source_manifest["source_rgba_sha256"],
            "composition": "fixed-runtime-neutral-with-local-generated-mouth-and-tears",
            "fixed_base_rgba_sha256": FIXED_BASE_RGBA_SHA256,
            "mutable_runtime_regions": [list(region) for region in MUTABLE_RUNTIME_REGIONS],
            "alpha_policy": "identical-to-fixed-base",
            "sequences": sequences,
        }
        (staged / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if runtime_root.exists():
            shutil.rmtree(runtime_root)
        staged.replace(runtime_root)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    if qa_root is not None:
        _write_qa(poses, qa_root, runtime_root, sequences)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--qa-dir", type=Path)
    args = parser.parse_args()
    manifest = build(args.runtime_dir, args.qa_dir)
    print(json.dumps({
        "runtime_dir": str(args.runtime_dir),
        "source_webp_sha256": manifest["source_webp_sha256"],
        "frames": sum(len(items) for items in manifest["sequences"].values()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

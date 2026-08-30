from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Final

from PIL import Image, ImageChops, ImageFilter

try:
    from tools.build_neutral_eye_layers import (
        CANONICAL_SHA256,
        CANVAS_SIZE,
        MOTION_LIMITS,
        NeutralEyeCompositor,
        ValidatedNeutralEyeSnapshot,
        compose_pose,
    )
except ModuleNotFoundError:  # Direct `python tools/build_neutral_eye_preview.py` CLI use.
    from build_neutral_eye_layers import (  # type: ignore[no-redef]
        CANONICAL_SHA256,
        CANVAS_SIZE,
        MOTION_LIMITS,
        NeutralEyeCompositor,
        ValidatedNeutralEyeSnapshot,
        compose_pose,
    )


FRAME_COUNT: Final = 90
FPS: Final = 30
DT_SECONDS: Final = 1 / FPS
TIME_CONSTANT_SECONDS: Final = 0.060
ALPHA: Final = 1 - math.exp(-DT_SECONDS / TIME_CONSTANT_SECONDS)
MATTE_RGB: Final = (31, 33, 36)
SOURCE_DURATIONS_MS: Final = (30, 30, 40) * 30
VIRTUAL_CURSOR_ACTIVATION_RADIUS: Final = 100.0
CURSOR_MAPPING_FORMULA: Final = "radial-clamped-elliptical-v1"
EYES: Final = ("left", "right")
OUTPUTS: Final = {
    "underlay.png": "RGBA",
    "eye-left.png": "RGBA",
    "eye-right.png": "RGBA",
    "eye-left-mask.png": "L",
    "eye-right-mask.png": "L",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(payload: dict, path: Path) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cursor_target(
    cursor_dx: float, cursor_dy: float, activation_radius: float
) -> tuple[float, float]:
    if (
        not math.isfinite(cursor_dx)
        or not math.isfinite(cursor_dy)
        or not math.isfinite(activation_radius)
        or activation_radius <= 0.0
    ):
        raise ValueError("cursor coordinates and activation radius must be finite, with positive radius")
    if cursor_dx == 0.0 and cursor_dy == 0.0:
        return (0.0, 0.0)
    scale = max(abs(cursor_dx), abs(cursor_dy))
    scaled_x = cursor_dx / scale
    scaled_y = cursor_dy / scale
    scaled_distance = math.hypot(scaled_x, scaled_y)
    if scale >= activation_radius:
        strength = 1.0
    else:
        strength = min((scale / activation_radius) * scaled_distance, 1.0)
    return (
        MOTION_LIMITS["x"] * scaled_x / scaled_distance * strength,
        MOTION_LIMITS["y"] * scaled_y / scaled_distance * strength,
    )


def target_for_frame(frame_index: int) -> tuple[float, float]:
    if not 0 <= frame_index < FRAME_COUNT:
        raise ValueError(f"frame index must be in 0..{FRAME_COUNT - 1}")
    if frame_index <= 5 or frame_index >= 63:
        return (0.0, 0.0)
    k = frame_index - 6
    angle = math.pi + 2.0 * math.pi * k / 56
    return cursor_target(
        VIRTUAL_CURSOR_ACTIVATION_RADIUS * math.cos(angle),
        VIRTUAL_CURSOR_ACTIVATION_RADIUS * math.sin(angle),
        VIRTUAL_CURSOR_ACTIVATION_RADIUS,
    )


def preview_offsets() -> tuple[tuple[float, float], ...]:
    state = (0.0, 0.0)
    offsets: list[tuple[float, float]] = []
    for frame_index in range(FRAME_COUNT):
        if frame_index == 84:
            state = (0.0, 0.0)
        elif frame_index < 84:
            target = target_for_frame(frame_index)
            state = tuple(
                current + ALPHA * (requested - current)
                for current, requested in zip(state, target, strict=True)
            )
        offsets.append(state)
    return tuple(offsets)


def _decode_checked(data: bytes, filename: str, mode: str) -> Image.Image:
    with Image.open(BytesIO(data)) as opened:
        image = opened.copy()
    if image.mode != mode or image.size != CANVAS_SIZE:
        raise ValueError(f"invalid {filename}: expected {mode} {CANVAS_SIZE}")
    return image


def _validate_inputs(
    asset_dir: Path, canonical_path: Path
) -> tuple[
    Image.Image,
    dict,
    dict[str, Image.Image],
    dict,
    ValidatedNeutralEyeSnapshot,
]:
    try:
        canonical_bytes = canonical_path.read_bytes()
    except OSError as error:
        raise ValueError("invalid canonical image") from error
    canonical_hash = hashlib.sha256(canonical_bytes).hexdigest()
    if canonical_hash != CANONICAL_SHA256:
        raise ValueError("canonical hash does not match the binding canonical SHA-256")
    canonical = _decode_checked(canonical_bytes, canonical_path.name, "RGBA")
    snapshot = ValidatedNeutralEyeSnapshot.load(asset_dir)
    authoring = snapshot.authoring()
    images = snapshot.images()
    actual_hashes = {
        "canonical-idle.png": canonical_hash,
        "authoring.json": snapshot.authoring_sha256,
        **snapshot.output_hashes(),
    }
    return canonical, authoring, images, actual_hashes, snapshot


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _validate_output_path(asset_dir: Path, canonical_path: Path, output_dir: Path) -> None:
    output_resolved = output_dir.resolve(strict=False)
    for protected in (asset_dir.resolve(strict=False), canonical_path.resolve(strict=False)):
        if _paths_overlap(output_resolved, protected):
            raise ValueError("output directory must not overlap immutable input paths")
    if output_dir.is_symlink():
        raise ValueError("output directory must not be a symlink")
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output directory must be a non-symlink directory when it exists")


def _binary_support(images: dict[str, Image.Image]) -> tuple[Image.Image, Image.Image]:
    supports = [
        images[f"eye-{eye}-mask.png"].point(lambda value: 255 if value > 0 else 0)
        for eye in EYES
    ]
    support = ImageChops.lighter(*supports)
    ring = ImageChops.subtract(support.filter(ImageFilter.MaxFilter(7)), support)
    return support, ring


def _changed_pixel_count(first: Image.Image, second: Image.Image) -> int:
    return sum(
        pixel != (0, 0, 0, 0)
        for pixel in tuple(ImageChops.difference(first, second).getdata())
    )


def _maximum_channel_delta(first: Image.Image, second: Image.Image) -> int:
    return max(high for _, high in ImageChops.difference(first, second).getextrema())


def _validate_rendered_frames(
    frames: list[Image.Image], canonical: Image.Image, support: Image.Image, ring: Image.Image
) -> tuple[dict, dict]:
    outside = ImageChops.invert(support)
    canonical_alpha = canonical.getchannel("A").tobytes()
    outside_max = 0
    alpha_max = 0
    ring_black_max = 0
    canonical_pixels = canonical.load()
    ring_points = [
        (x, y)
        for y in range(CANVAS_SIZE[1])
        for x in range(CANVAS_SIZE[0])
        if ring.getpixel((x, y)) > 0 and max(canonical_pixels[x, y][:3]) > 24
    ]
    for frame in frames:
        outside_delta = Image.composite(
            ImageChops.difference(frame, canonical), Image.new("RGBA", CANVAS_SIZE), outside
        )
        if outside_delta.getbbox(alpha_only=False) is not None:
            outside_max = max(
                outside_max, _changed_pixel_count(outside_delta, Image.new("RGBA", CANVAS_SIZE))
            )
        frame_alpha = frame.getchannel("A").tobytes()
        if frame_alpha != canonical_alpha:
            alpha_max = max(
                alpha_max,
                sum(a != b for a, b in zip(frame_alpha, canonical_alpha, strict=True)),
            )
        rendered_pixels = frame.load()
        ring_black = sum(
            max(rendered_pixels[x, y][:3]) <= 24 for x, y in ring_points
        )
        ring_black_max = max(ring_black_max, ring_black)
    containment = {
        "outside_support_changed_pixels_max": outside_max,
        "alpha_changed_pixels_max": alpha_max,
        "ring_new_near_black_pixels_max": ring_black_max,
    }
    if any(containment.values()):
        raise ValueError(f"containment validation failed: {containment}")
    final = frames[84:90]
    final_metrics = [
        (0, 0)
        if ImageChops.difference(frame, canonical).getbbox(alpha_only=False) is None
        else (_changed_pixel_count(frame, canonical), _maximum_channel_delta(frame, canonical))
        for frame in final
    ]
    if any(changed or delta for changed, delta in final_metrics):
        raise ValueError("final six frames are not canonical-exact")
    return containment, {
        "changed_pixels": max(changed for changed, _ in final_metrics),
        "maximum_channel_delta": max(delta for _, delta in final_metrics),
        "frame_indices": [84, 85, 86, 87, 88, 89],
    }


def _fixed_palette_rgb(frame: Image.Image) -> Image.Image:
    matte = Image.new("RGB", CANVAS_SIZE, MATTE_RGB)
    matte.paste(frame, mask=frame.getchannel("A"))
    return matte.convert("P", palette=Image.Palette.WEB, dither=Image.Dither.NONE)


def _decode_gif(path: Path) -> tuple[list[Image.Image], list[int], int]:
    with Image.open(path) as opened:
        frames: list[Image.Image] = []
        durations: list[int] = []
        loop = opened.info.get("loop")
        try:
            while True:
                frames.append(opened.convert("RGB").copy())
                durations.append(opened.info.get("duration", 0))
                opened.seek(opened.tell() + 1)
        except EOFError:
            pass
    return frames, durations, loop


def _tick_schedule(frames: list[Image.Image], durations: list[int]) -> list[Image.Image]:
    ticks: list[Image.Image] = []
    for frame, duration in zip(frames, durations, strict=True):
        if duration <= 0 or duration % 10:
            raise ValueError("decoded GIF duration is not a positive 10ms multiple")
        ticks.extend([frame] * (duration // 10))
    return ticks


def _write_gif(frames: list[Image.Image], path: Path) -> dict:
    palette_frames = [_fixed_palette_rgb(frame) for frame in frames]
    palette_frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=palette_frames[1:],
        duration=list(SOURCE_DURATIONS_MS),
        loop=0,
        optimize=False,
        disposal=2,
    )
    decoded_frames, decoded_durations, loop = _decode_gif(path)
    expected_ticks = _tick_schedule([frame.convert("RGB") for frame in palette_frames], list(SOURCE_DURATIONS_MS))
    decoded_ticks = _tick_schedule(decoded_frames, decoded_durations)
    if (
        loop != 0
        or sum(decoded_durations) != 3000
        or len(expected_ticks) != len(decoded_ticks)
        or any(left.tobytes() != right.tobytes() for left, right in zip(expected_ticks, decoded_ticks, strict=True))
    ):
        raise ValueError("GIF timeline differs from fixed-palette source timeline")
    return {
        "decoded_durations_ms": decoded_durations,
        "decoded_frame_count": len(decoded_frames),
        "loop": loop,
        "sha256": _sha256(path),
    }


def _replace_output(staging: Path, output_dir: Path) -> None:
    if not output_dir.exists():
        os.replace(staging, output_dir)
        return
    backup = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.backup-", dir=output_dir.parent))
    backup.rmdir()
    installed = False
    try:
        os.replace(output_dir, backup)
        try:
            os.replace(staging, output_dir)
        except Exception:
            try:
                os.replace(backup, output_dir)
            except Exception as restore_error:
                raise OSError(
                    "failed to install staged output and restore original output; "
                    f"original output remains at {backup}"
                ) from restore_error
            raise
        installed = True
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if installed and backup.exists():
            shutil.rmtree(backup)


def build_preview(asset_dir: Path, canonical_path: Path, output_dir: Path) -> dict:
    asset_dir = Path(asset_dir)
    canonical_path = Path(canonical_path)
    output_dir = Path(output_dir)
    _validate_output_path(asset_dir, canonical_path, output_dir)
    canonical, authoring, images, input_hashes, snapshot = _validate_inputs(
        asset_dir, canonical_path
    )
    offsets = preview_offsets()
    requested_targets = tuple(target_for_frame(index) for index in range(FRAME_COUNT))
    if any(
        abs(x) > MOTION_LIMITS["x"] or abs(y) > MOTION_LIMITS["y"]
        for x, y in (*requested_targets, *offsets)
    ):
        raise ValueError("preview offset exceeds motion limits")
    if any(abs(value) > 5e-5 for value in offsets[83]):
        raise ValueError("frame 83 must settle within 5e-5 of center")
    if offsets[84:] != ((0.0, 0.0),) * 6:
        raise ValueError("frames 84..89 must be exact center")
    compositor = NeutralEyeCompositor.from_snapshot(snapshot)
    frames = [compositor.compose(eye_x, eye_y) for eye_x, eye_y in offsets]
    support, ring = _binary_support(images)
    containment, final_center = _validate_rendered_frames(frames, canonical, support, ring)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        gif = _write_gif(frames, staging / "eye-follow.gif")
        stats = {
            "constants": {
                "frame_count": FRAME_COUNT,
                "fps": FPS,
                "dt_seconds": DT_SECONDS,
                "time_constant_seconds": TIME_CONSTANT_SECONDS,
                "alpha": ALPHA,
                "motion_limits": MOTION_LIMITS,
                "cursor_mapping_formula": CURSOR_MAPPING_FORMULA,
                "virtual_cursor_activation_radius": VIRTUAL_CURSOR_ACTIVATION_RADIUS,
                "matte_rgb": list(MATTE_RGB),
                "palette": "Pillow WEB dither=NONE",
            },
            "containment": containment,
            "final_center": final_center,
            "frames": [
                {
                    "frame_index": index,
                    "requested_target": list(target_for_frame(index)),
                    "smoothed_offset": list(offset),
                }
                for index, offset in enumerate(offsets)
            ],
            "gif": gif,
            "inputs": {
                "canonical": {"path": canonical_path.name, "sha256": input_hashes["canonical-idle.png"]},
                "authoring": {"path": "authoring.json", "sha256": input_hashes["authoring.json"]},
                "immutable_files": input_hashes,
                "authoring_canonical_hash": authoring["canonical"]["sha256"],
            },
            "observed_maxima": {
                "requested_abs_x": max(abs(target_for_frame(index)[0]) for index in range(FRAME_COUNT)),
                "requested_abs_y": max(abs(target_for_frame(index)[1]) for index in range(FRAME_COUNT)),
                "smoothed_abs_x": max(abs(offset[0]) for offset in offsets),
                "smoothed_abs_y": max(abs(offset[1]) for offset in offsets),
            },
            "source_durations_ms": list(SOURCE_DURATIONS_MS),
        }
        _write_json(stats, staging / "stats.json")
        _replace_output(staging, output_dir)
        return stats
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main() -> int:
    if sys.argv[1:] == ["--show-compositor-path"]:
        module = sys.modules[NeutralEyeCompositor.__module__]
        print(Path(module.__file__).resolve())
        return 0
    parser = argparse.ArgumentParser(description="Build deterministic neutral-eye follow preview")
    parser.add_argument("--asset-dir", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_preview(args.asset_dir, args.canonical, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

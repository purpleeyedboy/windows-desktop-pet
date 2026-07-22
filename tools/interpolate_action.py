"""Build alpha-safe 30-frame actions from six immutable keyframes."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from PIL import Image


INTERMEDIATE_COUNTS = (5, 5, 4, 5, 5)
FINAL_POSITIONS = (0, 6, 12, 17, 23, 29)
EXPECTED_SIZE = (512, 768)


def _backends() -> tuple[Any, Any]:
    try:
        import cv2
        import numpy as np
    except ImportError as error:  # pragma: no cover - exercised by environment setup
        raise RuntimeError(
            "animation interpolation requires requirements-assets.txt"
        ) from error
    return np, cv2


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _flow_input(image: Image.Image) -> Any:
    np, cv2 = _backends()
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = rgba[..., 3] / 255.0
    gray = cv2.cvtColor(rgba[..., :3].astype(np.uint8), cv2.COLOR_RGB2GRAY)
    composite = gray.astype(np.float32) * alpha
    feature = composite * 0.75 + rgba[..., 3] * 0.25
    return np.clip(feature, 0.0, 255.0).astype(np.uint8)


def bidirectional_flow(first: Image.Image, second: Image.Image) -> tuple[Any, Any]:
    """Estimate independent first->second and second->first Farneback fields."""
    _, cv2 = _backends()
    first_feature = _flow_input(first)
    second_feature = _flow_input(second)
    parameters = {
        "pyr_scale": 0.5,
        "levels": 5,
        "winsize": 51,
        "iterations": 5,
        "poly_n": 7,
        "poly_sigma": 1.5,
        "flags": 0,
    }
    forward = cv2.calcOpticalFlowFarneback(
        first_feature, second_feature, None, **parameters
    )
    backward = cv2.calcOpticalFlowFarneback(
        second_feature, first_feature, None, **parameters
    )
    return forward, backward


def _premultiplied_rgba(image: Image.Image) -> Any:
    np, _ = _backends()
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0
    alpha = rgba[..., 3:4]
    return np.concatenate((rgba[..., :3] * alpha, alpha), axis=2)


def _warp(values: Any, flow: Any, amount: float) -> tuple[Any, Any]:
    np, cv2 = _backends()
    height, width = flow.shape[:2]
    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
    )
    map_x = grid_x - flow[..., 0] * amount
    map_y = grid_y - flow[..., 1] * amount
    warped = cv2.remap(
        values,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    valid = cv2.remap(
        np.ones((height, width), dtype=np.float32),
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    if warped.ndim == 2:
        warped = warped[..., None]
    return warped, valid[..., None]


def render_between(
    first: Image.Image,
    second: Image.Image,
    forward: Any,
    backward: Any,
    time: float,
) -> Image.Image:
    """Warp both endpoints to ``time`` and blend premultiplied samples."""
    np, _ = _backends()
    first_warped, first_valid = _warp(
        _premultiplied_rgba(first), forward, time
    )
    second_warped, second_valid = _warp(
        _premultiplied_rgba(second), backward, 1.0 - time
    )

    first_sample = np.divide(
        first_warped,
        first_valid,
        out=np.zeros_like(first_warped),
        where=first_valid > 1.0e-8,
    )
    second_sample = np.divide(
        second_warped,
        second_valid,
        out=np.zeros_like(second_warped),
        where=second_valid > 1.0e-8,
    )
    first_weight = (1.0 - time) * first_valid
    second_weight = time * second_valid
    weight_sum = first_weight + second_weight
    safe_weight = np.maximum(weight_sum, 1.0e-8)
    blended = (
        first_sample * first_weight + second_sample * second_weight
    ) / safe_weight
    blended = np.where(weight_sum > 1.0e-8, blended, 0.0)

    alpha = np.clip(blended[..., 3:4], 0.0, 1.0)
    rgb = np.zeros_like(blended[..., :3])
    visible = alpha[..., 0] > 1.0e-8
    rgb[visible] = blended[..., :3][visible] / alpha[visible]
    rgb = np.clip(rgb, 0.0, 1.0)

    rgba = np.concatenate((rgb, alpha), axis=2)
    pixels = np.rint(rgba * 255.0).astype(np.uint8)
    hidden = pixels[..., 3] == 0
    pixels[hidden, :3] = 0
    return Image.fromarray(pixels)


def interpolate_pair(
    first: Image.Image, second: Image.Image, count: int
) -> list[Image.Image]:
    if first.size != EXPECTED_SIZE or second.size != EXPECTED_SIZE:
        raise ValueError("interpolation requires 512x768 frames")
    if count < 0:
        raise ValueError("intermediate frame count must be non-negative")
    if count == 0:
        return []
    forward, backward = bidirectional_flow(first, second)
    return [
        render_between(
            first,
            second,
            forward,
            backward,
            smoothstep(step / (count + 1)),
        )
        for step in range(1, count + 1)
    ]


def _load_keyframes(keyframe_dir: Path) -> list[Image.Image]:
    expected_names = [f"{index:02d}.png" for index in range(6)]
    actual_names = [path.name for path in sorted(keyframe_dir.glob("*.png"))]
    if actual_names != expected_names:
        raise ValueError("keyframe directory requires exactly 00.png through 05.png")
    frames = []
    for name in expected_names:
        with Image.open(keyframe_dir / name) as image:
            if image.mode != "RGBA" or image.size != EXPECTED_SIZE:
                raise ValueError(f"{name}: expected 512x768 RGBA keyframe")
            frames.append(image.copy())
    return frames


def _prepare_output_dir(output_dir: Path) -> Path:
    output_root = output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    for candidate in output_root.glob("*.png"):
        resolved_candidate = candidate.resolve()
        if resolved_candidate.parent != output_root or not candidate.is_file():
            raise RuntimeError(f"unsafe managed PNG path: {candidate}")
        candidate.unlink()
    return output_root


def build_action(
    keyframe_dir: Path, output_dir: Path, qa_dir: Path, action: str
) -> dict[str, object]:
    """Create 30 frames and QA artifacts while byte-copying all key positions."""
    keyframe_dir = Path(keyframe_dir)
    output_dir = Path(output_dir)
    qa_dir = Path(qa_dir)
    keyframes = _load_keyframes(keyframe_dir)
    output_dir = _prepare_output_dir(output_dir)

    for pair_index, intermediate_count in enumerate(INTERMEDIATE_COUNTS):
        final_position = FINAL_POSITIONS[pair_index]
        shutil.copy2(
            keyframe_dir / f"{pair_index:02d}.png",
            output_dir / f"{final_position:02d}.png",
        )
        generated = interpolate_pair(
            keyframes[pair_index], keyframes[pair_index + 1], intermediate_count
        )
        for offset, frame in enumerate(generated, start=1):
            frame.save(output_dir / f"{final_position + offset:02d}.png", "PNG")

    shutil.copy2(keyframe_dir / "05.png", output_dir / "29.png")

    output_frames = []
    for index in range(30):
        with Image.open(output_dir / f"{index:02d}.png") as image:
            output_frames.append(image.convert("RGBA").copy())

    from tools.animation_qa import write_action_qa

    return write_action_qa(output_frames, qa_dir, action)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True)
    parser.add_argument("--keyframes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    args = parser.parse_args()
    report = build_action(args.keyframes, args.output, args.qa, args.action)
    print(
        f"OK: {report['action']}, {report['frame_count']} frames, "
        f"{len(report['artifacts'])} QA artifacts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

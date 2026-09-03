from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Final, Iterable, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter

PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]
COMMITTED_OUTPUT_DIR: Final = PROJECT_ROOT / "qa/head-neck-continuous-v1"

if __package__ in {None, ""}:  # Direct checkout CLI use.
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

if TYPE_CHECKING:
    from desktop_pet.head_neck_deformation import (  # pragma: no cover
        ContinuousHeadNeckCompositor,
        HeadPose,
    )
try:
    from desktop_pet.head_neck_deformation import (  # noqa: E402
        ContinuousHeadNeckCompositor,
        HeadPose,
    )
except ModuleNotFoundError:  # Task 2 timeline tests may run while Task 1 is staged.
    ContinuousHeadNeckCompositor = None  # type: ignore[assignment,misc]
    HeadPose = None  # type: ignore[assignment,misc]
from desktop_pet.neutral_eye_compositor import (  # noqa: E402
    CANONICAL_SHA256,
    CANVAS_SIZE,
    OUTPUTS as EYE_OUTPUTS,
    NeutralEyeCompositor,
    ValidatedNeutralEyeSnapshot,
)


FRAME_COUNT: Final = 240
RUNTIME_ASSET_DIR: Final = PROJECT_ROOT / "assets/rig/v1/runtime"
FPS: Final = 30
DT_SECONDS: Final = 1.0 / FPS
ORBIT_RADIUS: Final = 0.85
FOCUS_TIME_CONSTANT_SECONDS: Final = 0.060
HEAD_TIME_CONSTANT_SECONDS: Final = 0.220
HEAD_RENDER_GAIN: Final = 1.225
EYE_HEAD_COMPENSATION: Final = 0.35
EYE_LIMIT_X: Final = 3.0
EYE_LIMIT_Y: Final = 2.0
RENDERED_EYE_ANCHOR_LIMITS: Final = (8.0, 5.5)
MATTE_RGB: Final = (32, 32, 36)
NORMAL_DURATIONS_MS: Final = (30, 30, 40) * 80
SLOW_DURATIONS_MS: Final = (120, 120, 160) * 80
OUTPUT_FILENAMES: Final = frozenset(
    {
        "head-neck-follow.gif",
        "head-neck-follow-4x.gif",
        "landmark-overlay.gif",
        "contact-sheet-light.png",
        "contact-sheet-dark.png",
        "contact-sheet-gray.png",
        "contact-sheet-checker.png",
        "seam-closeups-400pct.png",
        "center-difference.png",
        "stats.json",
    }
)
BACKGROUND_RGB: Final = {
    "light": (245, 245, 242),
    "dark": (22, 24, 28),
    "gray": (128, 128, 128),
}
SEMANTIC_POINTS: Final = {
    "left_ear_tip": (36, 223),
    "right_ear_tip": (223, 213),
    "left_ear_root": (87, 310),
    "right_ear_root": (194, 312),
    "left_eye": (82, 351),
    "right_eye": (163, 347),
    "nose": (118, 397),
    "jaw": (122, 451),
    "left_neck_root": (96, 454),
    "right_neck_root": (205, 454),
    "left_mid_neck": (108, 515),
    "right_mid_neck": (207, 515),
    "left_chest": (139, 555),
    "right_chest": (207, 555),
}
CLEAR_HOLE_BASELINES: Final = {
    "four_connectivity": {
        "component_count": 119,
        "pixel_count": 357,
        "largest_component": 21,
        "significant_hole_count": 2,
    },
    "eight_connectivity": {
        "component_count": 15,
        "pixel_count": 37,
        "largest_component": 6,
        "significant_hole_count": 0,
    },
}
SIGNIFICANT_HOLE_MIN_AREA: Final = 16
CLOSEUP_BOXES: Final = {
    "eye-rim": (54, 323, 188, 374),
    "ear-root": (38, 286, 246, 330),
    "whisker": (20, 397, 270, 447),
    "jaw": (92, 421, 188, 474),
    "neck": (76, 474, 232, 548),
    "collar": (70, 515, 238, 568),
    "chest": (70, 548, 238, 592),
}
EYE_CROPS: Final = {
    "left": (54, 323, 102, 376),
    "right": (144, 321, 184, 373),
}
CONTACT_FRAME_INDICES: Final = (0, 30, 45, 60, 75, 90, 105, 120, 135)


@dataclass(frozen=True)
class PreviewPose:
    index: int
    target_x: float
    target_y: float
    focus_x: float
    focus_y: float
    head_x: float
    head_y: float
    eye_x: float
    eye_y: float


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_json(payload: dict[str, object], path: Path) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _save_png(image: Image.Image, path: Path) -> None:
    image.save(path, format="PNG", optimize=False, compress_level=9)


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def target_for_frame(index: int) -> tuple[float, float]:
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < FRAME_COUNT:
        raise ValueError(f"frame index must be in 0..{FRAME_COUNT - 1}")
    if index <= 11 or index >= 168:
        return (0.0, 0.0)
    if index <= 29:
        strength = _smoothstep((index - 11) / 18.0)
        return (ORBIT_RADIUS * strength, 0.0)
    if index <= 149:
        angle = 2.0 * math.pi * (index - 30) / 120.0
        return (ORBIT_RADIUS * math.cos(angle), ORBIT_RADIUS * math.sin(angle))
    final_angle = 2.0 * math.pi * 119.0 / 120.0
    remaining = 1.0 - _smoothstep((index - 149) / 18.0)
    return (
        ORBIT_RADIUS * math.cos(final_angle) * remaining,
        ORBIT_RADIUS * math.sin(final_angle) * remaining,
    )


def _radial_clamp(x: float, y: float) -> tuple[float, float]:
    magnitude = math.hypot(x, y)
    if magnitude <= 1.0:
        return (x, y)
    return (x / magnitude, y / magnitude)


def _render_head_coordinates(pose: PreviewPose) -> tuple[float, float]:
    return _radial_clamp(
        pose.head_x * HEAD_RENDER_GAIN,
        pose.head_y * HEAD_RENDER_GAIN,
    )


def coordinated_preview_poses() -> tuple[PreviewPose, ...]:
    alpha_focus = 1.0 - math.exp(-DT_SECONDS / FOCUS_TIME_CONSTANT_SECONDS)
    alpha_head = 1.0 - math.exp(-DT_SECONDS / HEAD_TIME_CONSTANT_SECONDS)
    focus_x = focus_y = head_x = head_y = 0.0
    poses: list[PreviewPose] = []
    for index in range(FRAME_COUNT):
        target_x, target_y = target_for_frame(index)
        if index >= 228:
            target_x = target_y = 0.0
            focus_x = focus_y = head_x = head_y = 0.0
            residual_x = residual_y = 0.0
        else:
            focus_x, focus_y = _radial_clamp(
                focus_x + alpha_focus * (target_x - focus_x),
                focus_y + alpha_focus * (target_y - focus_y),
            )
            head_x, head_y = _radial_clamp(
                head_x + alpha_head * (target_x - head_x),
                head_y + alpha_head * (target_y - head_y),
            )
            residual_x, residual_y = _radial_clamp(
                focus_x - EYE_HEAD_COMPENSATION * head_x,
                focus_y - EYE_HEAD_COMPENSATION * head_y,
            )
        poses.append(
            PreviewPose(
                index=index,
                target_x=target_x,
                target_y=target_y,
                focus_x=focus_x,
                focus_y=focus_y,
                head_x=head_x,
                head_y=head_y,
                eye_x=EYE_LIMIT_X * residual_x,
                eye_y=EYE_LIMIT_Y * residual_y,
            )
        )
    return tuple(poses)


def _step_response_oracle() -> dict[str, object]:
    alpha_focus = 1.0 - math.exp(-DT_SECONDS / FOCUS_TIME_CONSTANT_SECONDS)
    alpha_head = 1.0 - math.exp(-DT_SECONDS / HEAD_TIME_CONSTANT_SECONDS)
    focus = 0.0
    head = 0.0
    samples: list[dict[str, float | int]] = []
    for index in range(30):
        focus += alpha_focus * (1.0 - focus)
        head += alpha_head * (1.0 - head)
        if not focus > head:
            raise ValueError("step response focus does not remain strictly ahead")
        samples.append({"index": index, "focus_x": focus, "head_x": head})
    focus_first_90 = next(index for index, sample in enumerate(samples) if sample["focus_x"] >= 0.9)
    head_first_90 = next(index for index, sample in enumerate(samples) if sample["head_x"] >= 0.9)
    if focus_first_90 > 4 or head_first_90 < 15 or head_first_90 - focus_first_90 < 10:
        raise ValueError("step response timing is outside the eyes-lead contract")
    return {
        "sample_count": len(samples),
        "focus_first_90_index": focus_first_90,
        "head_first_90_index": head_first_90,
        "lead_frames": head_first_90 - focus_first_90,
        "focus_strictly_ahead": True,
        "samples": samples,
    }


def _decode_rgba(data: bytes, filename: str) -> Image.Image:
    try:
        with Image.open(BytesIO(data)) as opened:
            image = opened.copy()
    except OSError as error:
        raise ValueError(f"invalid {filename}") from error
    if image.mode != "RGBA" or image.size != CANVAS_SIZE:
        raise ValueError(f"invalid {filename}: expected RGBA {CANVAS_SIZE}")
    return image


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _has_existing_symlink_ancestor(path: Path) -> bool:
    absolute = path.absolute()
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            return True
    return False


def _validate_paths(eye_asset_dir: Path, canonical_path: Path, output_dir: Path) -> None:
    output_resolved = output_dir.resolve(strict=False)
    if (
        output_resolved.is_relative_to(PROJECT_ROOT)
        and output_resolved != COMMITTED_OUTPUT_DIR
    ):
        raise ValueError(
            "output directory inside the project must be qa/head-neck-continuous-v1"
        )
    for immutable in (eye_asset_dir, canonical_path, RUNTIME_ASSET_DIR):
        if _paths_overlap(output_resolved, immutable.resolve(strict=False)):
            raise ValueError("output directory must not overlap immutable input paths")
    if _has_existing_symlink_ancestor(output_dir):
        raise ValueError("output directory must not use symlink traversal")
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output directory must be a non-symlink directory when it exists")
    required_inputs = (
        canonical_path,
        eye_asset_dir / "authoring.json",
        *(eye_asset_dir / filename for filename in EYE_OUTPUTS),
    )
    for input_path in required_inputs:
        if (
            _has_existing_symlink_ancestor(input_path)
            or not input_path.exists()
            or input_path.is_symlink()
            or not input_path.is_file()
        ):
            raise ValueError(
                f"required input must be a non-symlink regular file: {input_path.name}"
            )


def _snapshot_tree(root: Path) -> tuple[tuple[str, str, str], ...]:
    root = Path(root)
    if root.is_symlink():
        return ((".", "symlink", os.readlink(root)),)
    if not root.exists():
        return ((".", "missing", ""),)
    if root.is_file():
        return ((".", "file", _sha256_path(root)),)
    if not root.is_dir():
        return ((".", "special", ""),)

    entries: list[tuple[str, str, str]] = [(".", "directory", "")]
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append((relative, "symlink", os.readlink(path)))
        elif path.is_file():
            entries.append((relative, "file", _sha256_path(path)))
        elif path.is_dir():
            entries.append((relative, "directory", ""))
        else:
            entries.append((relative, "special", ""))
    return tuple(entries)


def _runtime_tree_is_unchanged(
    runtime_root: Path, before: tuple[tuple[str, str, str], ...]
) -> bool:
    return _snapshot_tree(runtime_root) == before


def _load_snapshot(
    eye_asset_dir: Path, canonical_path: Path
) -> tuple[Image.Image, ValidatedNeutralEyeSnapshot, dict[str, str]]:
    try:
        canonical_bytes = canonical_path.read_bytes()
    except OSError as error:
        raise ValueError("invalid canonical image") from error
    canonical_sha = _sha256_bytes(canonical_bytes)
    if canonical_sha != CANONICAL_SHA256:
        raise ValueError("canonical SHA-256 does not match the approved source")
    canonical = _decode_rgba(canonical_bytes, canonical_path.name)
    snapshot = ValidatedNeutralEyeSnapshot.load(eye_asset_dir)
    hashes = {
        "canonical-idle.png": canonical_sha,
        "authoring.json": snapshot.authoring_sha256,
        **snapshot.output_hashes(),
    }
    return canonical, snapshot, hashes


def _outside_roi_changed(first: Image.Image, second: Image.Image, roi: tuple[int, int, int, int]) -> int:
    x, y, width, height = roi
    boxes = (
        (0, 0, CANVAS_SIZE[0], y),
        (0, y + height, CANVAS_SIZE[0], CANVAS_SIZE[1]),
        (0, y, x, y + height),
        (x + width, y, CANVAS_SIZE[0], y + height),
    )
    changed = 0
    for box in boxes:
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        difference = ImageChops.difference(first.crop(box), second.crop(box))
        changed += sum(pixel != (0, 0, 0, 0) for pixel in difference.getdata())
    return changed


def _geometry_masks(
    compositor: ContinuousHeadNeckCompositor,
) -> dict[str, Image.Image]:
    roi_x, roi_y, width, height = tuple(compositor.head_roi)
    dynamic = Image.new("L", (width, height), 0)
    right_strip = Image.new("L", (width, height), 0)
    lower_band = Image.new("L", (width, height), 0)
    dynamic_pixels = dynamic.load()
    right_pixels = right_strip.load()
    lower_pixels = lower_band.load()
    horizontal = HeadPose(1.0, 0.0)
    vertical = HeadPose(0.0, 1.0)
    for local_y in range(height):
        canvas_y = local_y + roi_y
        for local_x in range(width):
            canvas_x = local_x + roi_x
            if canvas_x >= 264:
                right_pixels[local_x, local_y] = 255
            if canvas_y >= 555:
                lower_pixels[local_x, local_y] = 255
            horizontal_offset = compositor.sampling_offset_at(
                (canvas_x + 0.5, canvas_y + 0.5), horizontal
            )
            vertical_offset = compositor.sampling_offset_at(
                (canvas_x + 0.5, canvas_y + 0.5), vertical
            )
            if horizontal_offset != (0.0, 0.0) or vertical_offset != (0.0, 0.0):
                dynamic_pixels[local_x, local_y] = 255
    outside_dynamic = ImageChops.invert(dynamic)
    return {
        "dynamic": dynamic,
        "outside_dynamic": outside_dynamic,
        "right_strip": right_strip,
        "lower_band": lower_band,
    }


def _changed_in_roi_mask(
    first: Image.Image,
    second: Image.Image,
    roi: tuple[int, int, int, int],
    mask: Image.Image,
) -> int:
    x, y, width, height = roi
    difference = ImageChops.difference(
        first.crop((x, y, x + width, y + height)),
        second.crop((x, y, x + width, y + height)),
    )
    return sum(
        selected != 0 and pixel != (0, 0, 0, 0)
        for selected, pixel in zip(mask.getdata(), difference.getdata(), strict=True)
    )


def _count_alpha(image: Image.Image, roi: tuple[int, int, int, int], kind: str) -> int:
    x, y, width, height = roi
    values = image.getchannel("A").crop((x, y, x + width, y + height)).getdata()
    if kind == "positive":
        return sum(value > 0 for value in values)
    if kind == "semitransparent":
        return sum(0 < value < 255 for value in values)
    raise ValueError(f"unknown Alpha count kind: {kind}")


def _ratio(numerator: int, denominator: int, name: str) -> float:
    if denominator <= 0:
        raise ValueError(f"{name} baseline is empty")
    return numerator / denominator


def _edge_energy(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    edges = image.convert("RGB").crop(box).convert("L").filter(ImageFilter.FIND_EDGES)
    return sum(edges.getdata())


def _transparent_rgb_count(image: Image.Image) -> int:
    return sum(alpha == 0 and (red != 0 or green != 0 or blue != 0) for red, green, blue, alpha in image.getdata())


def _alpha_support_count(image: Image.Image, roi: tuple[int, int, int, int]) -> int:
    x, y, width, height = roi
    return sum(value > 0 for value in image.getchannel("A").crop((x, y, x + width, y + height)).getdata())


def _enclosed_transparent_components(
    image: Image.Image,
    roi: tuple[int, int, int, int],
    *,
    connectivity: int = 4,
) -> dict[str, int]:
    if connectivity not in (4, 8):
        raise ValueError("transparency connectivity must be 4 or 8")
    x, y, width, height = roi
    alpha = image.getchannel("A").crop((x, y, x + width, y + height)).tobytes()
    parents: list[int] = []
    sizes: list[int] = []
    exterior: list[bool] = []

    def find(component: int) -> int:
        while parents[component] != component:
            parents[component] = parents[parents[component]]
            component = parents[component]
        return component

    def union(first: int, second: int) -> None:
        first_root = find(first)
        second_root = find(second)
        if first_root == second_root:
            return
        if sizes[first_root] < sizes[second_root]:
            first_root, second_root = second_root, first_root
        parents[second_root] = first_root
        sizes[first_root] += sizes[second_root]
        exterior[first_root] = exterior[first_root] or exterior[second_root]

    previous_runs: list[tuple[int, int, int]] = []
    for row_index in range(height):
        row = alpha[row_index * width : (row_index + 1) * width]
        current_runs: list[tuple[int, int, int]] = []
        for match in re.finditer(b"\x00+", row):
            start, end = match.span()
            component = len(parents)
            parents.append(component)
            sizes.append(end - start)
            exterior.append(
                row_index == 0
                or row_index == height - 1
                or start == 0
                or end == width
            )
            current_runs.append((start, end, component))

        previous_index = 0
        margin = 1 if connectivity == 8 else 0
        for start, end, component in current_runs:
            while (
                previous_index < len(previous_runs)
                and previous_runs[previous_index][1] <= start - margin
            ):
                previous_index += 1
            candidate = previous_index
            while candidate < len(previous_runs):
                previous_start, previous_end, previous_component = previous_runs[candidate]
                if previous_start >= end + margin:
                    break
                if previous_end > start - margin:
                    union(component, previous_component)
                candidate += 1
        previous_runs = current_runs

    component_sizes = [
        sizes[component]
        for component in range(len(parents))
        if find(component) == component and not exterior[component]
    ]
    return {
        "component_count": len(component_sizes),
        "pixel_count": sum(component_sizes),
        "largest_component": max(component_sizes, default=0),
        "significant_hole_count": sum(
            size >= SIGNIFICANT_HOLE_MIN_AREA for size in component_sizes
        ),
    }


def _mesh_vertices(
    mesh: Sequence[tuple[tuple[int, int, int, int], tuple[float, ...]]],
    roi: tuple[int, int, int, int],
) -> dict[tuple[int, int], tuple[float, float]]:
    roi_x, roi_y, _width, _height = roi
    vertices: dict[tuple[int, int], tuple[float, float]] = {}
    for bbox, quad in mesh:
        left, top, right, bottom = bbox
        outputs = ((left, top), (left, bottom), (right, bottom), (right, top))
        sources = tuple(zip(quad[::2], quad[1::2], strict=True))
        for output, source in zip(outputs, sources, strict=True):
            global_output = (output[0] + roi_x, output[1] + roi_y)
            global_source = (source[0] + roi_x, source[1] + roi_y)
            previous = vertices.setdefault(global_output, global_source)
            if previous != global_source:
                raise ValueError("mesh cells disagree at a shared vertex")
    return vertices


def _signed_polygon_area(points: Sequence[tuple[float, float]]) -> float:
    return (
        sum(
            first[0] * second[1] - second[0] * first[1]
            for first, second in zip(points, (*points[1:], points[0]), strict=True)
        )
        / 2.0
    )


def _mesh_metrics(compositor: ContinuousHeadNeckCompositor, poses: Iterable[HeadPose]) -> dict[str, object]:
    minimum_ratio = math.inf
    maximum_ratio = -math.inf
    minimum_area = math.inf
    maximum_area = -math.inf
    minimum_signed_ratio = math.inf
    maximum_signed_ratio = -math.inf
    minimum_signed_area = math.inf
    maximum_signed_area = -math.inf
    minimum_orientation_sign = 1
    maximum_orientation_sign = -1
    for pose in poses:
        for bbox, quad in compositor.mesh_for(pose):
            left, top, right, bottom = bbox
            output_area = (right - left) * (bottom - top)
            source_points = tuple(zip(quad[::2], quad[1::2], strict=True))
            signed_source_area = _signed_polygon_area(source_points)
            source_area = abs(signed_source_area)
            ratio = source_area / output_area
            signed_ratio = signed_source_area / output_area
            orientation_sign = 1 if signed_source_area > 0.0 else -1
            minimum_ratio = min(minimum_ratio, ratio)
            maximum_ratio = max(maximum_ratio, ratio)
            minimum_area = min(minimum_area, source_area)
            maximum_area = max(maximum_area, source_area)
            minimum_signed_ratio = min(minimum_signed_ratio, signed_ratio)
            maximum_signed_ratio = max(maximum_signed_ratio, signed_ratio)
            minimum_signed_area = min(minimum_signed_area, signed_source_area)
            maximum_signed_area = max(maximum_signed_area, signed_source_area)
            minimum_orientation_sign = min(minimum_orientation_sign, orientation_sign)
            maximum_orientation_sign = max(maximum_orientation_sign, orientation_sign)
    return {
        "source_area_min": minimum_area,
        "source_area_max": maximum_area,
        "source_output_area_ratio_min": minimum_ratio,
        "source_output_area_ratio_max": maximum_ratio,
        "signed_source_area_min": minimum_signed_area,
        "signed_source_area_max": maximum_signed_area,
        "signed_source_output_area_ratio_min": minimum_signed_ratio,
        "signed_source_output_area_ratio_max": maximum_signed_ratio,
        "orientation_sign_min": minimum_orientation_sign,
        "orientation_sign_max": maximum_orientation_sign,
    }


def _semantic_metrics(compositor: ContinuousHeadNeckCompositor) -> dict[str, object]:
    samples: dict[str, dict[str, float]] = {}
    for label, pose in {
        "left": HeadPose(-1.0, 0.0),
        "right": HeadPose(1.0, 0.0),
        "up": HeadPose(0.0, -1.0),
        "down": HeadPose(0.0, 1.0),
    }.items():
        samples[label] = {
            name: math.hypot(*compositor.sampling_offset_at(point, pose))
            for name, point in SEMANTIC_POINTS.items()
        }
    horizontal_nose = min(samples[side]["nose"] for side in ("left", "right"))
    horizontal_neck_values = [
        samples[side][name]
        for side in ("left", "right")
        for name in ("left_neck_root", "right_neck_root")
    ]
    neck_average = sum(horizontal_neck_values) / len(horizontal_neck_values)
    if horizontal_nose < 3.0 or horizontal_nose - neck_average < 1.0:
        raise ValueError("head warp is not visibly non-rigid at semantic controls")
    point_minima = {
        name: min(direction[name] for direction in samples.values())
        for name in SEMANTIC_POINTS
    }
    point_maxima = {
        name: max(direction[name] for direction in samples.values())
        for name in SEMANTIC_POINTS
    }
    return {
        "cardinal_displacements": samples,
        "cardinal_displacement_min": min(point_minima.values()),
        "cardinal_displacement_max": max(point_maxima.values()),
        "point_displacement_minima": point_minima,
        "point_displacement_maxima": point_maxima,
        "horizontal_nose_min": horizontal_nose,
        "horizontal_neck_root_min": min(horizontal_neck_values),
        "horizontal_neck_root_max": max(horizontal_neck_values),
        "horizontal_neck_root_average": neck_average,
        "nose_minus_neck_average": horizontal_nose - neck_average,
    }


def _matte_frame(frame: Image.Image, background: Image.Image | tuple[int, int, int]) -> Image.Image:
    if isinstance(background, tuple):
        matte = Image.new("RGB", frame.size, background)
    else:
        matte = background.convert("RGB").copy()
    matte.paste(frame, mask=frame.getchannel("A"))
    return matte


def _web_palette(frame: Image.Image) -> Image.Image:
    return _matte_frame(frame, MATTE_RGB).convert(
        "P", palette=Image.Palette.WEB, dither=Image.Dither.NONE
    )


def _decode_gif(path: Path) -> tuple[list[Image.Image], list[int], int | None]:
    with Image.open(path) as opened:
        frames: list[Image.Image] = []
        durations: list[int] = []
        loop = opened.info.get("loop")
        try:
            while True:
                frames.append(opened.convert("RGB").copy())
                durations.append(int(opened.info.get("duration", 0)))
                opened.seek(opened.tell() + 1)
        except EOFError:
            pass
    return frames, durations, loop


def _timeline_ticks(frames: Sequence[Image.Image], durations: Sequence[int]) -> list[bytes]:
    ticks: list[bytes] = []
    for frame, duration in zip(frames, durations, strict=True):
        if duration <= 0 or duration % 10:
            raise ValueError("GIF duration must be a positive 10ms multiple")
        ticks.extend([frame.convert("RGB").tobytes()] * (duration // 10))
    return ticks


def _write_gif(
    frames: Sequence[Image.Image], durations: Sequence[int], path: Path
) -> dict[str, object]:
    palette_frames = [_web_palette(frame) for frame in frames]
    palette_frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=palette_frames[1:],
        duration=list(durations),
        loop=0,
        optimize=False,
        disposal=2,
    )
    decoded, decoded_durations, loop = _decode_gif(path)
    expected_ticks = _timeline_ticks(
        [frame.convert("RGB") for frame in palette_frames], durations
    )
    decoded_ticks = _timeline_ticks(decoded, decoded_durations)
    if loop != 0 or expected_ticks != decoded_ticks:
        raise ValueError("decoded GIF schedule differs from the fixed-palette source")
    return {
        "decoded_frame_count": len(decoded),
        "decoded_durations_ms": decoded_durations,
        "duration_ms": sum(decoded_durations),
        "loop": loop,
        "sha256": _sha256_path(path),
    }


def _checker(size: tuple[int, int], cell: int = 16) -> Image.Image:
    image = Image.new("RGB", size, (216, 216, 216))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(168, 168, 168))
    return image


def _contact_sheet(frames: Sequence[Image.Image], background: str) -> Image.Image:
    panel_size = (256, 384)
    margin = 16
    label_height = 22
    columns = 3
    rows = 3
    sheet = Image.new(
        "RGB",
        (
            margin + columns * (panel_size[0] + margin),
            margin + rows * (panel_size[1] + label_height + margin),
        ),
        (250, 250, 250),
    )
    draw = ImageDraw.Draw(sheet)
    for position, frame_index in enumerate(CONTACT_FRAME_INDICES):
        column = position % columns
        row = position // columns
        left = margin + column * (panel_size[0] + margin)
        top = margin + row * (panel_size[1] + label_height + margin)
        if background == "checker":
            base = _checker(CANVAS_SIZE)
        else:
            base = Image.new("RGB", CANVAS_SIZE, BACKGROUND_RGB[background])
        panel = _matte_frame(frames[frame_index], base).resize(panel_size, Image.Resampling.LANCZOS)
        sheet.paste(panel, (left, top))
        draw.text((left, top + panel_size[1] + 4), f"frame {frame_index:03d}", fill=(0, 0, 0))
    return sheet


def _predicted_landmark_points(
    compositor: ContinuousHeadNeckCompositor, pose: HeadPose
) -> dict[str, tuple[float, float]]:
    predicted: dict[str, tuple[float, float]] = {}
    for name, point in SEMANTIC_POINTS.items():
        offset_x, offset_y = compositor.sampling_offset_at(point, pose)
        predicted[name] = (point[0] - offset_x, point[1] - offset_y)
    return predicted


def _landmark_frames(
    frames: Sequence[Image.Image], poses: Sequence[PreviewPose], compositor: ContinuousHeadNeckCompositor
) -> list[Image.Image]:
    colors = {
        "nose": (255, 64, 64),
        "left_eye": (64, 255, 96),
        "right_eye": (64, 255, 96),
        "left_neck_root": (64, 160, 255),
        "right_neck_root": (64, 160, 255),
        "left_chest": (255, 220, 64),
        "right_chest": (255, 220, 64),
    }
    overlays: list[Image.Image] = []
    for frame, pose in zip(frames, poses, strict=True):
        overlay = frame.copy()
        draw = ImageDraw.Draw(overlay)
        points = _predicted_landmark_points(
            compositor,
            HeadPose(*_render_head_coordinates(pose)),
        )
        for name, color in colors.items():
            if name not in points:
                continue
            x, y = points[name]
            draw.line((x - 5, y, x + 5, y), fill=(*color, 255), width=1)
            draw.line((x, y - 5, x, y + 5), fill=(*color, 255), width=1)
        overlays.append(overlay)
    return overlays


def _closeup_sheet(frames: Sequence[Image.Image]) -> Image.Image:
    pose_indices = (0, 30, 60)
    names = tuple(CLOSEUP_BOXES)
    cell_width = 1000
    cell_height = 240
    label_width = 82
    sheet = Image.new("RGB", (label_width + cell_width * 3, cell_height * len(names)), (230, 230, 230))
    draw = ImageDraw.Draw(sheet)
    for row, name in enumerate(names):
        box = CLOSEUP_BOXES[name]
        draw.text((5, row * cell_height + 8), name, fill=(0, 0, 0))
        for column, frame_index in enumerate(pose_indices):
            crop = _matte_frame(frames[frame_index], MATTE_RGB).crop(box)
            crop = crop.resize((crop.width * 4, crop.height * 4), Image.Resampling.NEAREST)
            crop.thumbnail((cell_width, cell_height - 20), Image.Resampling.LANCZOS)
            left = label_width + column * cell_width
            top = row * cell_height + 20
            sheet.paste(crop, (left, top))
            draw.text((left + 4, row * cell_height + 3), f"frame {frame_index:03d}", fill=(0, 0, 0))
    return sheet


def _changed_pixels(first: Image.Image, second: Image.Image) -> int:
    return sum(
        pixel != (0, 0, 0, 0)
        for pixel in ImageChops.difference(first, second).getdata()
    )


def _premultiplied_edge_oracle() -> dict[str, object]:
    source = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(source)
    draw.ellipse((74, 284, 238, 500), fill=(255, 183, 67, 255))

    class SyntheticCompositor:
        source_size = CANVAS_SIZE
        eye_midpoint = (122.5, 349.0)

        def compose(self, _eye_x: float, _eye_y: float) -> Image.Image:
            return source.copy()

    compositor = ContinuousHeadNeckCompositor(SyntheticCompositor())
    rendered = compositor.compose(0.0, 0.0, HeadPose(0.73, -0.41))
    semitransparent = [
        pixel for pixel in rendered.getdata() if 16 <= pixel[3] <= 239
    ]
    minimum_red = min(pixel[0] for pixel in semitransparent)
    maximum_green = max(pixel[1] for pixel in semitransparent)
    maximum_blue = max(pixel[2] for pixel in semitransparent)
    transparent_rgb = _transparent_rgb_count(rendered)
    passed = (
        bool(semitransparent)
        and minimum_red >= 248
        and min(pixel[1] for pixel in semitransparent) >= 176
        and min(pixel[2] for pixel in semitransparent) >= 62
        and transparent_rgb == 0
    )
    if not passed:
        raise ValueError("synthetic premultiplied-alpha edge oracle failed")
    return {
        "passed": passed,
        "semitransparent_pixel_count": len(semitransparent),
        "minimum_red": minimum_red,
        "maximum_green": maximum_green,
        "maximum_blue": maximum_blue,
        "minimum_green": min(pixel[1] for pixel in semitransparent),
        "minimum_blue": min(pixel[2] for pixel in semitransparent),
        "transparent_rgb_violations": transparent_rgb,
    }


def _replace_output(staging: Path, output_dir: Path) -> None:
    if not output_dir.exists():
        try:
            os.replace(staging, output_dir)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise
        return
    backup = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.backup-", dir=output_dir.parent)
    )
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
                    f"recoverable original remains at {backup}"
                ) from restore_error
            raise
        installed = True
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if installed and backup.exists():
            shutil.rmtree(backup)


def _validate_staging(staging: Path) -> None:
    actual = {path.name for path in staging.iterdir() if path.is_file()}
    if actual != OUTPUT_FILENAMES:
        raise ValueError(
            f"QA output allowlist mismatch: missing={sorted(OUTPUT_FILENAMES - actual)}, "
            f"extra={sorted(actual - OUTPUT_FILENAMES)}"
        )
    if any(path.is_symlink() or not path.is_file() for path in staging.iterdir()):
        raise ValueError("QA staging contains a non-regular file")
    for filename in OUTPUT_FILENAMES:
        path = staging / filename
        if filename.endswith(".gif"):
            frames, durations, loop = _decode_gif(path)
            if not frames or not durations or loop != 0:
                raise ValueError(f"invalid staged GIF: {filename}")
        elif filename.endswith(".png"):
            try:
                with Image.open(path) as opened:
                    opened.load()
                    if opened.width <= 0 or opened.height <= 0:
                        raise ValueError(f"empty staged PNG: {filename}")
                    if filename == "center-difference.png" and (
                        opened.mode != "RGBA" or opened.size != CANVAS_SIZE
                    ):
                        raise ValueError("center difference must be RGBA 512x768")
            except OSError as error:
                raise ValueError(f"invalid staged PNG: {filename}") from error
    try:
        recorded = json.loads((staging / "stats.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid staged stats.json") from error
    hashes = recorded.get("outputs")
    if not isinstance(hashes, dict) or set(hashes) != OUTPUT_FILENAMES - {"stats.json"}:
        raise ValueError("staged output hashes do not match the allowlist")
    for filename, expected in hashes.items():
        if _sha256_path(staging / filename) != expected:
            raise ValueError(f"staged output hash mismatch: {filename}")


def build_preview(
    eye_asset_dir: Path, canonical_path: Path, output_dir: Path
) -> dict[str, object]:
    eye_asset_dir = Path(eye_asset_dir)
    canonical_path = Path(canonical_path)
    output_dir = Path(output_dir)
    if ContinuousHeadNeckCompositor is None or HeadPose is None:
        raise ModuleNotFoundError(
            "Task 1 desktop_pet.head_neck_deformation is required to render the preview"
        )
    _validate_paths(eye_asset_dir, canonical_path, output_dir)
    runtime_before = _snapshot_tree(RUNTIME_ASSET_DIR)
    canonical, snapshot, input_hashes = _load_snapshot(eye_asset_dir, canonical_path)
    eye_compositor = NeutralEyeCompositor.from_snapshot(snapshot)
    compositor = ContinuousHeadNeckCompositor(eye_compositor)
    roi = tuple(int(value) for value in compositor.head_roi)
    if len(roi) != 4:
        raise ValueError("head ROI must contain four integers")
    poses = coordinated_preview_poses()
    rendered_head_coordinates = tuple(
        _render_head_coordinates(pose) for pose in poses
    )
    settle_magnitudes = (
        math.hypot(poses[227].focus_x, poses[227].focus_y),
        math.hypot(poses[227].head_x, poses[227].head_y),
        math.hypot(
            poses[227].eye_x / EYE_LIMIT_X,
            poses[227].eye_y / EYE_LIMIT_Y,
        ),
    )
    if max(settle_magnitudes) > 0.0001:
        raise ValueError("preview did not settle before forced-center frames")
    if any(pose != PreviewPose(pose.index, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0) for pose in poses[228:]):
        raise ValueError("final preview frames are not exact center")

    eye_only_frames: list[Image.Image] = []
    frames: list[Image.Image] = []
    geometry_masks = _geometry_masks(compositor)
    outside_changed: list[int] = []
    outside_dynamic_changed: list[int] = []
    right_strip_changed: list[int] = []
    lower_band_changed: list[int] = []
    transparent_rgb: list[int] = []
    support_deltas: list[int] = []
    positive_ratios: list[float] = []
    semitransparent_ratios: list[float] = []
    rendered_holes: dict[str, list[dict[str, int]]] = {
        label: [] for label in CLEAR_HOLE_BASELINES
    }
    hole_cache: dict[bytes, dict[str, dict[str, int]]] = {}
    canonical_holes = {
        "four_connectivity": _enclosed_transparent_components(
            canonical, roi, connectivity=4
        ),
        "eight_connectivity": _enclosed_transparent_components(
            canonical, roi, connectivity=8
        ),
    }
    if canonical_holes != CLEAR_HOLE_BASELINES:
        raise ValueError(
            f"canonical enclosed-hole baseline changed: {canonical_holes}"
        )
    rendered_eye_anchor_x: list[float] = []
    rendered_eye_anchor_y: list[float] = []
    for pose, rendered_head in zip(poses, rendered_head_coordinates, strict=True):
        eye_only = eye_compositor.compose(pose.eye_x, pose.eye_y)
        rendered = compositor.compose(
            pose.eye_x, pose.eye_y, HeadPose(*rendered_head)
        )
        eye_only_frames.append(eye_only)
        frames.append(rendered)
        outside_changed.append(_outside_roi_changed(rendered, eye_only, roi))
        outside_dynamic_changed.append(
            _changed_in_roi_mask(
                rendered, eye_only, roi, geometry_masks["outside_dynamic"]
            )
        )
        right_strip_changed.append(
            _changed_in_roi_mask(
                rendered, eye_only, roi, geometry_masks["right_strip"]
            )
        )
        lower_band_changed.append(
            _changed_in_roi_mask(
                rendered, eye_only, roi, geometry_masks["lower_band"]
            )
        )
        transparent_rgb.append(_transparent_rgb_count(rendered))
        rendered_positive = _count_alpha(rendered, roi, "positive")
        source_positive = _count_alpha(eye_only, roi, "positive")
        rendered_semitransparent = _count_alpha(rendered, roi, "semitransparent")
        source_semitransparent = _count_alpha(eye_only, roi, "semitransparent")
        support_deltas.append(rendered_positive - source_positive)
        positive_ratios.append(
            _ratio(rendered_positive, source_positive, "Alpha-positive support")
        )
        semitransparent_ratios.append(
            _ratio(
                rendered_semitransparent,
                source_semitransparent,
                "semitransparent support",
            )
        )
        rendered_alpha = rendered.getchannel("A").crop(
            (roi[0], roi[1], roi[0] + roi[2], roi[1] + roi[3])
        ).tobytes()
        holes_by_connectivity = hole_cache.get(rendered_alpha)
        if holes_by_connectivity is None:
            holes_by_connectivity = {
                "four_connectivity": _enclosed_transparent_components(
                    rendered, roi, connectivity=4
                ),
                "eight_connectivity": _enclosed_transparent_components(
                    rendered, roi, connectivity=8
                ),
            }
            hole_cache[rendered_alpha] = holes_by_connectivity
        for label, holes in holes_by_connectivity.items():
            rendered_holes[label].append(holes)
        head_pose = HeadPose(*rendered_head)
        for anchor_name in ("left_eye", "right_eye"):
            offset_x, offset_y = compositor.sampling_offset_at(
                SEMANTIC_POINTS[anchor_name], head_pose
            )
            rendered_eye_anchor_x.append(pose.eye_x - offset_x)
            rendered_eye_anchor_y.append(pose.eye_y - offset_y)
    if max(outside_changed) != 0:
        raise ValueError("head preview changed decoded pixels outside the locked ROI")
    if max(outside_dynamic_changed) != 0:
        raise ValueError("head preview changed pixels outside dynamic support")
    if max(right_strip_changed) != 0 or max(lower_band_changed) != 0:
        raise ValueError("head preview changed a protected body strip")
    if max(transparent_rgb) != 0:
        raise ValueError("head preview contains nonzero RGB under transparent pixels")
    if min(positive_ratios) < 0.97 or max(positive_ratios) > 1.03:
        raise ValueError("Alpha-positive support ratio is outside 0.97..1.03")
    if min(semitransparent_ratios) < 0.80 or max(semitransparent_ratios) > 1.25:
        raise ValueError("semitransparent support ratio is outside 0.80..1.25")
    hole_maxima = {
        label: {
            key: max(holes[key] for holes in rendered_holes[label])
            for key in baseline
        }
        for label, baseline in CLEAR_HOLE_BASELINES.items()
    }
    blocking_label = "eight_connectivity"
    hole_violations = [
        (index, holes)
        for index, holes in enumerate(rendered_holes[blocking_label])
        if holes["significant_hole_count"] != 0
    ]
    if hole_violations:
        first_index, first_metrics = hole_violations[0]
        raise ValueError(
            "head preview contains a significant enclosed transparent hole: "
            f"maxima={hole_maxima}, first_frame={first_index}, "
            f"first_metrics={first_metrics}"
        )
    eye_travel = {
        "horizontal_abs_max": max(abs(value) for value in rendered_eye_anchor_x),
        "vertical_abs_max": max(abs(value) for value in rendered_eye_anchor_y),
    }
    if (
        eye_travel["horizontal_abs_max"] > RENDERED_EYE_ANCHOR_LIMITS[0]
        or eye_travel["vertical_abs_max"] > RENDERED_EYE_ANCHOR_LIMITS[1]
    ):
        raise ValueError("total rendered eye-anchor travel exceeds the review envelope")
    if any(frame.tobytes() != canonical.tobytes() for frame in frames[228:]):
        raise ValueError("final held-center frames are not canonical-exact")

    audit_extrema = {
        "horizontal_positive": max(
            range(FRAME_COUNT), key=lambda index: rendered_head_coordinates[index][0]
        ),
        "horizontal_negative": min(
            range(FRAME_COUNT), key=lambda index: rendered_head_coordinates[index][0]
        ),
        "vertical_positive": max(
            range(FRAME_COUNT), key=lambda index: rendered_head_coordinates[index][1]
        ),
        "vertical_negative": min(
            range(FRAME_COUNT), key=lambda index: rendered_head_coordinates[index][1]
        ),
    }
    visible_motion = {
        label: _changed_pixels(frames[index], eye_only_frames[index])
        for label, index in audit_extrema.items()
    }
    if any(value < 500 for value in visible_motion.values()):
        raise ValueError("head-only extrema contain fewer than 500 changed pixels")
    eye_edge_energy: dict[str, dict[str, float | int]] = {}
    for label, index in audit_extrema.items():
        for eye, box in EYE_CROPS.items():
            source_energy = _edge_energy(eye_only_frames[index], box)
            rendered_energy = _edge_energy(frames[index], box)
            ratio = _ratio(rendered_energy, source_energy, "eye edge energy")
            if not 0.80 <= ratio <= 1.15:
                raise ValueError("eye-crop FIND_EDGES energy ratio is outside 0.80..1.15")
            eye_edge_energy[f"{label}:{eye}"] = {
                "frame_index": index,
                "source_energy": source_energy,
                "rendered_energy": rendered_energy,
                "ratio": ratio,
            }
    semantic = _semantic_metrics(compositor)
    mesh_metrics = _mesh_metrics(
        compositor,
        (HeadPose(*coordinates) for coordinates in rendered_head_coordinates),
    )
    center_difference = ImageChops.difference(frames[228], canonical)
    if center_difference.getbbox(alpha_only=False) is not None:
        raise ValueError("center difference is not exact zero")
    edge_oracle = _premultiplied_edge_oracle()

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        normal_gif = _write_gif(
            frames, NORMAL_DURATIONS_MS, staging / "head-neck-follow.gif"
        )
        slow_gif = _write_gif(
            frames, SLOW_DURATIONS_MS, staging / "head-neck-follow-4x.gif"
        )
        overlay_gif = _write_gif(
            _landmark_frames(frames, poses, compositor),
            NORMAL_DURATIONS_MS,
            staging / "landmark-overlay.gif",
        )
        for background in ("light", "dark", "gray", "checker"):
            _save_png(
                _contact_sheet(frames, background),
                staging / f"contact-sheet-{background}.png",
            )
        _save_png(_closeup_sheet(frames), staging / "seam-closeups-400pct.png")
        _save_png(center_difference, staging / "center-difference.png")

        zero_mesh = compositor.mesh_for(HeadPose(0.0, 0.0))
        x_vertices = sorted(
            {
                bbox[0] + roi[0]
                for bbox, _quad in zero_mesh
            }
            | {bbox[2] + roi[0] for bbox, _quad in zero_mesh}
        )
        y_vertices = sorted(
            {bbox[1] + roi[1] for bbox, _quad in zero_mesh}
            | {bbox[3] + roi[1] for bbox, _quad in zero_mesh}
        )
        output_hashes = {
            path.name: _sha256_path(path)
            for path in sorted(staging.iterdir())
            if path.name != "stats.json"
        }
        runtime_assets_unchanged = _runtime_tree_is_unchanged(
            RUNTIME_ASSET_DIR, runtime_before
        )
        if not runtime_assets_unchanged:
            raise ValueError("runtime assets changed while building QA evidence")
        target_steps = [
            math.hypot(second.target_x - first.target_x, second.target_y - first.target_y)
            for first, second in zip(poses[:-1], poses[1:], strict=True)
        ]
        head_steps = [
            math.hypot(second.head_x - first.head_x, second.head_y - first.head_y)
            for first, second in zip(poses[:-1], poses[1:], strict=True)
        ]
        rendered_head_steps = [
            math.dist(first, second)
            for first, second in zip(
                rendered_head_coordinates[:-1],
                rendered_head_coordinates[1:],
                strict=True,
            )
        ]
        residual_227 = (
            poses[227].eye_x / EYE_LIMIT_X,
            poses[227].eye_y / EYE_LIMIT_Y,
        )
        stats: dict[str, object] = {
            "constants": {
                "frame_count": FRAME_COUNT,
                "fps": FPS,
                "dt_seconds": DT_SECONDS,
                "orbit_radius": ORBIT_RADIUS,
                "focus_time_constant_seconds": FOCUS_TIME_CONSTANT_SECONDS,
                "head_time_constant_seconds": HEAD_TIME_CONSTANT_SECONDS,
                "head_render_gain": HEAD_RENDER_GAIN,
                "deformation_gain": compositor.deformation_gain,
                "eye_head_compensation": EYE_HEAD_COMPENSATION,
                "eye_limits": {"x": EYE_LIMIT_X, "y": EYE_LIMIT_Y},
                "rendered_eye_anchor_limits": {
                    "horizontal": RENDERED_EYE_ANCHOR_LIMITS[0],
                    "vertical": RENDERED_EYE_ANCHOR_LIMITS[1],
                },
                "matte_rgb": list(MATTE_RGB),
                "normal_durations_ms": list(NORMAL_DURATIONS_MS),
                "slow_durations_ms": list(SLOW_DURATIONS_MS),
                "palette": "Pillow WEB dither=NONE optimize=False disposal=2",
                "contact_frame_indices": list(CONTACT_FRAME_INDICES),
                "canonical_enclosed_hole_baselines": CLEAR_HOLE_BASELINES,
                "blocking_enclosed_hole_connectivity": 8,
                "significant_hole_min_area_source_pixels": SIGNIFICANT_HOLE_MIN_AREA,
                "eye_crops": {name: list(box) for name, box in EYE_CROPS.items()},
            },
            "inputs": {
                "canonical": canonical_path.name,
                "eye_asset_dir": "eye-neutral-v1",
                "sha256": input_hashes,
            },
            "outputs": output_hashes,
            "roi": list(roi),
            "mesh": {
                "x_vertices": x_vertices,
                "y_vertices": y_vertices,
                **mesh_metrics,
            },
            "poses": [asdict(pose) for pose in poses],
            "pose_extrema": {
                "target_abs_x": max(abs(pose.target_x) for pose in poses),
                "target_abs_y": max(abs(pose.target_y) for pose in poses),
                "focus_magnitude_max": max(math.hypot(pose.focus_x, pose.focus_y) for pose in poses),
                "head_magnitude_max": max(math.hypot(pose.head_x, pose.head_y) for pose in poses),
                "rendered_head_magnitude_max": max(
                    math.hypot(*coordinates)
                    for coordinates in rendered_head_coordinates
                ),
                "eye_abs_x": max(abs(pose.eye_x) for pose in poses),
                "eye_abs_y": max(abs(pose.eye_y) for pose in poses),
                "target_step_max": max(target_steps),
                "head_state_step_max": max(head_steps),
                "rendered_head_step_max": max(rendered_head_steps),
            },
            "step_response": _step_response_oracle(),
            "semantic_displacements": semantic,
            "audit_extrema_frame_indices": audit_extrema,
            "head_only_changed_pixels": visible_motion,
            "eye_crop_find_edges": eye_edge_energy,
            "total_rendered_eye_anchor_travel": eye_travel,
            "containment": {
                "outside_roi_changed_pixels_max": max(outside_changed),
                "outside_dynamic_support_changed_pixels_max": max(outside_dynamic_changed),
                "protected_right_strip_changed_pixels_max": max(right_strip_changed),
                "protected_lower_band_changed_pixels_max": max(lower_band_changed),
                "transparent_rgb_violations_max": max(transparent_rgb),
                "canonical_enclosed_transparent_holes": canonical_holes,
                "rendered_enclosed_transparent_holes_max": hole_maxima,
                "alpha_support_delta_min": min(support_deltas),
                "alpha_support_delta_max": max(support_deltas),
                "alpha_positive_ratio_min": min(positive_ratios),
                "alpha_positive_ratio_max": max(positive_ratios),
                "semitransparent_ratio_min": min(semitransparent_ratios),
                "semitransparent_ratio_max": max(semitransparent_ratios),
            },
            "final_center": {
                "frame_indices": list(range(228, 240)),
                "changed_pixels": 0,
                "maximum_channel_delta": 0,
                "settle_focus_magnitude_frame_227": math.hypot(poses[227].focus_x, poses[227].focus_y),
                "settle_head_magnitude_frame_227": math.hypot(poses[227].head_x, poses[227].head_y),
                "settle_residual_magnitude_frame_227": math.hypot(*residual_227),
            },
            "synthetic_premultiplied_edge_oracle": edge_oracle,
            "gifs": {
                "normal": normal_gif,
                "slow_4x": slow_gif,
                "landmark_overlay": overlay_gif,
            },
            "scope": {
                "runtime_assets_unchanged": runtime_assets_unchanged,
                "directional_runtime_assets_created": False,
                "qa_only": True,
                "human_fringe_gate_backgrounds": ["light", "dark", "gray", "checker"],
            },
        }
        if stats["pose_extrema"]["target_step_max"] > 0.075:  # type: ignore[index]
            raise ValueError("preview target path contains a step above 0.075")
        if stats["pose_extrema"]["head_state_step_max"] > 0.055:  # type: ignore[index]
            raise ValueError("preview head-state path contains a step above 0.055")
        if stats["pose_extrema"]["rendered_head_step_max"] > 0.065:  # type: ignore[index]
            raise ValueError("preview rendered-head path contains a step above 0.065")
        _write_json(stats, staging / "stats.json")
        _validate_staging(staging)
        _replace_output(staging, output_dir)
        return stats
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic continuous head-neck visual QA evidence"
    )
    parser.add_argument("--asset-dir", dest="eye_asset_dir", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    build_preview(args.eye_asset_dir, args.canonical, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

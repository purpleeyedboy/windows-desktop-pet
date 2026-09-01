from __future__ import annotations

import ast
import math
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageMath

import desktop_pet.head_neck_deformation as deformation
from desktop_pet.head_neck_deformation import ContinuousHeadNeckCompositor, HeadPose


CANVAS_SIZE = (512, 768)
HEAD_ROI = (0, 160, 320, 432)
X_VERTICES = (
    0, 24, 36, 48, 60, 72, 82, 93, 108, 118, 128, 139, 151,
    163, 176, 184, 194, 205, 218, 230, 242, 249, 256, 264, 320,
)
Y_VERTICES = (
    160, 186, 202, 223, 250, 275, 300, 320, 335, 351,
    370, 397, 425, 454, 485, 520, 555, 565, 592,
)
DYNAMIC_POLYGON = (
    (24, 202), (246, 202), (263, 370), (242, 455),
    (221, 564), (105, 564), (80, 470), (32, 430),
)
SEMANTIC_POINTS = {
    "ear_tips": ((36, 223), (223, 213)),
    "ear_roots": ((87, 310), (194, 312)),
    "eye_anchors": ((82, 351), (163, 347)),
    "nose": ((118, 397),),
    "jaw": ((122, 451),),
    "neck_roots": ((96, 454), (205, 454)),
    "mid_neck": ((108, 515), (207, 515)),
    "chest_anchors": ((139, 555), (207, 555)),
}


class RecordingCompositor:
    source_size = CANVAS_SIZE
    eye_midpoint = (122.5, 349.0)

    def __init__(self, image: Image.Image | None = None) -> None:
        self.image = image or _synthetic_cat()
        self.calls: list[tuple[float, float]] = []

    def compose(self, eye_x: float, eye_y: float) -> Image.Image:
        self.calls.append((eye_x, eye_y))
        return self.image.copy()


def _synthetic_cat() -> Image.Image:
    image = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((28, 190, 258, 535), fill=(188, 126, 91, 255))
    draw.ellipse((36, 200, 249, 526), outline=(244, 205, 175, 136), width=3)
    draw.rectangle((105, 500, 220, 565), fill=(132, 84, 64, 255))
    draw.rectangle((264, 250, 319, 580), fill=(31, 71, 101, 255))
    draw.rectangle((350, 650, 410, 720), fill=(31, 71, 101, 255))
    return image


def _mesh_vertices(
    mesh: tuple[tuple[tuple[int, int, int, int], tuple[float, ...]], ...]
) -> dict[tuple[int, int], tuple[float, float]]:
    vertices: dict[tuple[int, int], tuple[float, float]] = {}
    for bbox, quad in mesh:
        x0, y0, x1, y1 = bbox
        for output, source in (
            ((x0, y0), (quad[0], quad[1])),
            ((x0, y1), (quad[2], quad[3])),
            ((x1, y1), (quad[4], quad[5])),
            ((x1, y0), (quad[6], quad[7])),
        ):
            previous = vertices.setdefault(output, source)
            assert previous == pytest.approx(source, abs=1e-12)
    return vertices


def _signed_area(points: tuple[tuple[float, float], ...]) -> float:
    return 0.5 * sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1])
    )


def _strictly_inside_polygon(x: float, y: float) -> bool:
    inside = False
    previous_x, previous_y = DYNAMIC_POLYGON[-1]
    for current_x, current_y in DYNAMIC_POLYGON:
        cross = (x - previous_x) * (current_y - previous_y) - (
            y - previous_y
        ) * (current_x - previous_x)
        if abs(cross) < 1e-12 and (
            min(previous_x, current_x) <= x <= max(previous_x, current_x)
            and min(previous_y, current_y) <= y <= max(previous_y, current_y)
        ):
            return False
        if (current_y > y) != (previous_y > y):
            intersection = (
                (previous_x - current_x)
                * (y - current_y)
                / (previous_y - current_y)
                + current_x
            )
            if x < intersection:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _is_dynamic_pixel(x: int, y: int) -> bool:
    return x < 264 and y < 555 and _strictly_inside_polygon(x + 0.5, y + 0.5)


def _oracle_unpremultiply(image: Image.Image) -> Image.Image:
    red, green, blue, alpha = image.split()
    channels = [
        ImageMath.unsafe_eval(
            'convert(c * 255 / max(a, 1), "L")', c=channel, a=alpha
        )
        for channel in (red, green, blue)
    ]
    transparent = alpha.point(lambda value: 255 if value == 0 else 0)
    for channel in channels:
        channel.paste(0, mask=transparent)
    return Image.merge("RGBA", (*channels, alpha))


def _independent_oracle(
    source: Image.Image,
    mesh: tuple[tuple[tuple[int, int, int, int], tuple[float, ...]], ...],
) -> Image.Image:
    roi = source.crop((0, 160, 320, 592))
    red, green, blue, alpha = roi.split()
    premultiplied = Image.merge(
        "RGBA",
        (
            ImageChops.multiply(red, alpha),
            ImageChops.multiply(green, alpha),
            ImageChops.multiply(blue, alpha),
            alpha,
        ),
    )
    warped = _oracle_unpremultiply(
        premultiplied.transform(
            roi.size,
            Image.Transform.MESH,
            mesh,
            Image.Resampling.BICUBIC,
        )
    )
    warped.putalpha(
        warped.getchannel("A").point(
            lambda value: 255 if value >= 252 else value
        )
    )
    warped_pixels = warped.load()
    source_pixels = source.load()
    for local_y in range(432):
        global_y = local_y + 160
        for x in range(320):
            if not _is_dynamic_pixel(x, global_y):
                warped_pixels[x, local_y] = source_pixels[x, global_y]
    result = source.copy()
    result.paste(warped, (0, 160))
    return result


def _changed_points(first: Image.Image, second: Image.Image) -> set[tuple[int, int]]:
    first_pixels = first.load()
    second_pixels = second.load()
    return {
        (x, y)
        for y in range(first.height)
        for x in range(first.width)
        if first_pixels[x, y] != second_pixels[x, y]
    }


def _alpha_centroid(image: Image.Image) -> tuple[float, float]:
    alpha = image.getchannel("A")
    pixels = alpha.load()
    total = sum(alpha.getdata())
    assert total > 0
    return (
        sum(x * pixels[x, y] for y in range(image.height) for x in range(image.width)) / total,
        sum(y * pixels[x, y] for y in range(image.height) for x in range(image.width)) / total,
    )


def test_public_geometry_is_exact_half_open_and_pose_is_immutable() -> None:
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor())
    assert compositor.source_size == CANVAS_SIZE
    assert compositor.eye_midpoint == (122.5, 349.0)
    assert compositor.head_roi == HEAD_ROI
    mesh = compositor.mesh_for(HeadPose(0.25, -0.5))
    assert len(mesh) == 24 * 18
    assert tuple(sorted({box[0] for box, _ in mesh} | {box[2] for box, _ in mesh})) == X_VERTICES
    assert tuple(sorted({box[1] + 160 for box, _ in mesh} | {box[3] + 160 for box, _ in mesh})) == Y_VERTICES
    assert max(box[2] for box, _ in mesh) == 320
    assert max(box[3] for box, _ in mesh) == 432
    assert min(box[1] for box, _ in mesh) == 0

    pose = HeadPose(0.0, 0.0)
    with pytest.raises(FrozenInstanceError):
        pose.x = 1.0  # type: ignore[misc]


def test_boundary_ramp_is_the_reviewed_twenty_source_pixels() -> None:
    assert deformation._BOUNDARY_RAMP == 20.0


def test_user_requested_deformation_gain_is_exactly_double() -> None:
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor())
    assert deformation._DEFORMATION_GAIN == 2.0
    assert compositor.deformation_gain == 2.0


@pytest.mark.parametrize(
    "values",
    [
        (True, 0.0), (0.0, False), ("0", 0.0), (0.0, object()),
        (math.nan, 0.0), (0.0, math.inf), (1.0, 0.01), (-0.8, -0.7),
    ],
)
def test_head_pose_rejects_non_real_non_finite_and_outside_unit_disk(
    values: tuple[object, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        HeadPose(*values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "eye_x,eye_y",
    [
        (True, 0.0), (0.0, False), (math.nan, 0.0), (0.0, -math.inf),
        (3.0001, 0.0), (0.0, -2.0001),
    ],
)
def test_compose_rejects_invalid_eye_offsets(eye_x: object, eye_y: object) -> None:
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor())
    with pytest.raises((TypeError, ValueError)):
        compositor.compose(eye_x, eye_y, HeadPose(0.0, 0.0))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "point",
    [
        (True, 300.0), (100.0, False), (math.nan, 300.0),
        (100.0, math.inf), (-0.1, 300.0), (100.0, 592.1),
    ],
)
def test_sampling_offset_rejects_invalid_points(point: tuple[object, object]) -> None:
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor())
    with pytest.raises((TypeError, ValueError)):
        compositor.sampling_offset_at(point, HeadPose(0.2, 0.1))  # type: ignore[arg-type]


def test_zero_head_pose_bypasses_resampling_and_preserves_eye_only_bytes() -> None:
    base = RecordingCompositor()
    compositor = ContinuousHeadNeckCompositor(base)
    expected = base.compose(2.25, -1.25)
    actual = compositor.compose(2.25, -1.25, HeadPose(-0.0, 0.0))
    assert actual.tobytes() == expected.tobytes()
    assert base.calls[-1] == (2.25, -1.25)


def test_sampling_offsets_meet_signed_fixed_semantic_travel_contract() -> None:
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor())
    horizontal = HeadPose(1.0, 0.0)
    vertical = HeadPose(0.0, 1.0)
    nose_dx = compositor.sampling_offset_at(SEMANTIC_POINTS["nose"][0], horizontal)[0]
    eyes = [compositor.sampling_offset_at(point, horizontal)[0] for point in SEMANTIC_POINTS["eye_anchors"]]
    necks = [compositor.sampling_offset_at(point, horizontal)[0] for point in SEMANTIC_POINTS["neck_roots"]]
    ear_tips = [compositor.sampling_offset_at(point, horizontal)[0] for point in SEMANTIC_POINTS["ear_tips"]]
    ear_roots = [compositor.sampling_offset_at(point, horizontal)[0] for point in SEMANTIC_POINTS["ear_roots"]]
    nose_dy = compositor.sampling_offset_at(SEMANTIC_POINTS["nose"][0], vertical)[1]

    assert nose_dx < 0 and 6.0 <= abs(nose_dx) <= 8.0
    assert all(value < 0 and 4.0 <= abs(value) <= 6.0 for value in eyes)
    assert all(value < 0 and 1.6 <= abs(value) <= 4.4 for value in necks)
    assert all(value < 0 and 3.0 <= abs(value) <= 6.0 for value in (*ear_tips, *ear_roots))
    assert all(abs(tip - root) <= 2.0 for tip, root in zip(ear_tips, ear_roots))
    assert abs(nose_dx) - sum(abs(value) for value in necks) / 2.0 >= 2.0
    assert nose_dy < 0 and 4.0 <= abs(nose_dy) <= 6.0
    for point in SEMANTIC_POINTS["chest_anchors"]:
        assert compositor.sampling_offset_at(point, horizontal) == (0.0, 0.0)


@pytest.mark.parametrize(
    "pose",
    [
        HeadPose(1.0, 0.0), HeadPose(-1.0, 0.0),
        HeadPose(0.0, 1.0), HeadPose(0.0, -1.0),
        HeadPose(0.6, 0.8), HeadPose(-math.sqrt(0.5), math.sqrt(0.5)),
    ],
)
def test_every_mesh_is_finite_in_bounds_convex_and_within_area_limits(
    pose: HeadPose,
) -> None:
    mesh = ContinuousHeadNeckCompositor(RecordingCompositor()).mesh_for(pose)
    for bbox, quad in mesh:
        assert all(math.isfinite(value) for value in quad)
        points = tuple(zip(quad[::2], quad[1::2]))
        assert all(0.0 <= x <= 320.0 and 0.0 <= y <= 432.0 for x, y in points)
        crosses = []
        for index in range(4):
            a, b, c = points[index], points[(index + 1) % 4], points[(index + 2) % 4]
            crosses.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
        assert all(value < 0.0 for value in crosses)
        output_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        assert 0.60 <= abs(_signed_area(points)) / output_area <= 1.40


def test_perimeter_polygon_boundary_and_protected_bands_are_pinned() -> None:
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor())
    pose = HeadPose(0.6, -0.8)
    vertices = _mesh_vertices(compositor.mesh_for(pose))
    for x in X_VERTICES:
        for y in Y_VERTICES:
            if x in (0, 320) or y in (160, 592) or x >= 264 or y >= 555:
                assert vertices[(x, y - 160)] == (x, y - 160)
    for point in DYNAMIC_POLYGON:
        assert compositor.sampling_offset_at(point, pose) == (0.0, 0.0)
    assert compositor.sampling_offset_at((280.0, 350.0), pose) == (0.0, 0.0)
    assert compositor.sampling_offset_at((150.0, 570.0), pose) == (0.0, 0.0)


def test_fractional_field_is_continuous_across_axes_and_not_a_pose_lookup() -> None:
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor())
    point = (118.0, 397.0)
    negative = compositor.sampling_offset_at(point, HeadPose(-1e-7, 0.31))
    positive = compositor.sampling_offset_at(point, HeadPose(1e-7, 0.31))
    first = compositor.sampling_offset_at(point, HeadPose(0.371, -0.219))
    nearby = compositor.sampling_offset_at(point, HeadPose(0.371001, -0.219001))
    assert math.dist(negative, positive) < 1e-5
    assert 0.0 < math.dist(first, nearby) < 1e-4


@pytest.mark.parametrize("pose", [HeadPose(1.0, 0.0), HeadPose(0.0, 1.0)])
def test_head_warp_matches_independent_oracle_and_has_only_allowed_changes(
    pose: HeadPose,
) -> None:
    source = _synthetic_cat()
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor(source))
    result = compositor.compose(0.0, 0.0, pose)
    oracle = _independent_oracle(source, compositor.mesh_for(pose))
    changed = _changed_points(source, result)
    assert result.tobytes() == oracle.tobytes()
    assert len(changed) >= 500
    assert all(0 <= x < 320 and 160 <= y < 592 for x, y in changed)
    assert all(_is_dynamic_pixel(x, y) for x, y in changed)
    assert all(x < 264 and y < 555 for x, y in changed)


@pytest.mark.parametrize(
    "pose,axis",
    [(HeadPose(1.0, 0.0), 0), (HeadPose(0.0, 1.0), 1)],
)
def test_forward_rendered_marker_moves_with_positive_pose_sign(
    pose: HeadPose, axis: int
) -> None:
    source = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(source).ellipse((112, 391, 124, 403), fill=(240, 130, 70, 255))
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor(source))
    before = _alpha_centroid(source)
    after = _alpha_centroid(compositor.compose(0.0, 0.0, pose))
    assert after[axis] > before[axis] + 1.5


def test_alpha_and_transparent_rgb_invariants_are_preserved() -> None:
    source = Image.open(
        Path(__file__).parents[1]
        / "assets"
        / "rig"
        / "v1"
        / "source"
        / "canonical-idle.png"
    ).convert("RGBA")
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor(source))
    result = compositor.compose(0.75, -0.5, HeadPose(0.43, -0.37))
    source_semi = sum(0 < value < 255 for value in source.getchannel("A").getdata())
    result_semi = sum(0 < value < 255 for value in result.getchannel("A").getdata())
    assert 0.80 <= result_semi / source_semi <= 1.25
    assert all(pixel[:3] == (0, 0, 0) for pixel in result.getdata() if pixel[3] == 0)


def test_near_opaque_alpha_plateau_is_normalized_only_inside_dynamic_warp() -> None:
    source = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(source)
    draw.rectangle((90, 330, 180, 440), fill=(211, 144, 77, 253))
    draw.rectangle((280, 330, 300, 400), fill=(61, 122, 183, 253))
    draw.rectangle((130, 560, 170, 580), fill=(91, 152, 213, 253))
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor(source))

    result = compositor.compose(0.0, 0.0, HeadPose(0.6, 0.2))
    normalized_oracle = _independent_oracle(
        source, compositor.mesh_for(HeadPose(0.6, 0.2))
    )

    assert result.getpixel((135, 385))[:3] == normalized_oracle.getpixel(
        (135, 385)
    )[:3]
    assert result.getpixel((135, 385))[3] == 255
    assert result.getpixel((290, 360)) == source.getpixel((290, 360))
    assert result.getpixel((150, 570)) == source.getpixel((150, 570))
    for y in range(160, 555):
        for x in range(264):
            pixel = result.getpixel((x, y))
            if _is_dynamic_pixel(x, y) and pixel[3] >= 252:
                assert pixel[3] == 255


def test_premultiplied_resampling_keeps_uniform_color_bright_at_alpha_edge() -> None:
    source = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(source).ellipse((62, 300, 198, 470), fill=(255, 183, 67, 255))
    compositor = ContinuousHeadNeckCompositor(RecordingCompositor(source))
    result = compositor.compose(0.0, 0.0, HeadPose(0.37, 0.21))
    edge_pixels = [pixel for pixel in result.crop((0, 160, 320, 592)).getdata() if 16 <= pixel[3] <= 239]
    assert edge_pixels
    assert min(pixel[0] for pixel in edge_pixels) >= 248
    assert min(pixel[1] for pixel in edge_pixels) >= 176
    assert min(pixel[2] for pixel in edge_pixels) >= 62


def test_invalid_injected_frame_fails_closed() -> None:
    wrong_mode = RecordingCompositor(Image.new("RGB", CANVAS_SIZE))
    wrong_size = RecordingCompositor(Image.new("RGBA", (511, 768)))
    with pytest.raises(ValueError, match="RGBA"):
        ContinuousHeadNeckCompositor(wrong_mode).compose(0.0, 0.0, HeadPose(0.1, 0.0))
    with pytest.raises(ValueError, match="512x768"):
        ContinuousHeadNeckCompositor(wrong_size).compose(0.0, 0.0, HeadPose(0.1, 0.0))


@pytest.mark.parametrize(
    "pose",
    (
        lambda: HeadPose(0.0, 0.0, 50.01, 0.0),
        lambda: HeadPose(0.0, 0.0, 0.0, -0.01),
        lambda: HeadPose(0.0, 0.0, 0.0, 1.01),
    ),
)
def test_head_pose_rejects_invalid_idle_tilt_components(pose) -> None:
    with pytest.raises(ValueError):
        pose()


def test_rotation_does_not_reintroduce_pixel_stretch_offsets() -> None:
    point = (118.0, 397.0)
    neutral = deformation._sampling_offset(
        *point, HeadPose(0.0, 0.0, 0.0, 0.0)
    )
    rotated = deformation._sampling_offset(
        *point, HeadPose(0.0, 0.0, 50.0, 1.0)
    )
    assert rotated == neutral == (0.0, 0.0)


def test_idle_rotation_layer_contains_head_but_excludes_neck_and_chest() -> None:
    mask = deformation._HEAD_LAYER_MASK
    assert mask.getpixel((120, 350)) >= 250
    assert mask.getpixel((204, 414)) >= 250
    assert mask.getpixel((150, 455)) == 0
    assert mask.getpixel((180, 460)) == 0
    assert mask.getpixel((150, 500)) == 0
    assert mask.getpixel((175, 560)) == 0


def test_layered_neutral_frame_is_exact_source_with_symmetric_padding() -> None:
    source = _synthetic_cat()
    backplate = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    compositor = ContinuousHeadNeckCompositor(
        RecordingCompositor(source), body_backplate=backplate
    )
    result = compositor.compose(0.0, 0.0, HeadPose(0.0, 0.0))
    assert compositor.source_size == (640, 768)
    assert result.size == (640, 768)
    assert ImageChops.difference(result.crop((64, 0, 576, 768)), source).getbbox() is None
    assert result.crop((0, 0, 64, 768)).getbbox() is None
    assert result.crop((576, 0, 640, 768)).getbbox() is None


def test_rotated_eye_hit_testing_uses_inverse_head_rotation() -> None:
    base = RecordingCompositor()
    base.eye_interaction_boxes = ((62, 335, 96, 367),)
    compositor = ContinuousHeadNeckCompositor(
        base,
        body_backplate=Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0)),
    )
    angle = 40.0
    compositor.compose(0.0, 0.0, HeadPose(0.0, 0.0, angle, 1.0))
    source_x, source_y = (79.0, 351.0)
    pivot_x, pivot_y = (204.0, 414.0)
    radians = math.radians(angle)
    dx = source_x - pivot_x
    dy = source_y - pivot_y
    rendered = (
        64.0 + pivot_x + math.cos(radians) * dx + math.sin(radians) * dy,
        pivot_y - math.sin(radians) * dx + math.cos(radians) * dy,
    )
    assert compositor.hit_test_eye(rendered)
    assert not compositor.hit_test_eye((639.0, 10.0))


def test_arc_path_does_not_translate_the_fixed_head_neck_joint() -> None:
    source = _synthetic_cat()
    backplate = _synthetic_cat()
    compositor = ContinuousHeadNeckCompositor(
        RecordingCompositor(source), body_backplate=backplate
    )

    without_arc = compositor.compose(
        0.0, 0.0, HeadPose(0.0, 0.0, 20.0, 0.0)
    )
    with_arc = compositor.compose(
        0.0, 0.0, HeadPose(0.0, 0.0, 20.0, 1.0)
    )

    assert ImageChops.difference(without_arc, with_arc).getbbox() is None


@pytest.mark.parametrize(
    "pose",
    (
        HeadPose(0.0, 0.0, -50.0, 0.0),
        HeadPose(0.0, 0.0, 50.0, 0.0),
        HeadPose(0.0, 0.0, 0.0, 1.0),
        HeadPose(0.6, 0.4, -50.0, 1.0),
        HeadPose(-0.6, 0.4, 50.0, 1.0),
    ),
)
def test_idle_tilt_and_mouse_follow_extremes_keep_a_valid_mesh(pose) -> None:
    compositor = ContinuousHeadNeckCompositor(
        RecordingCompositor(),
        body_backplate=Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0)),
    )
    mesh = compositor.mesh_for(pose)
    assert len(mesh) == (len(X_VERTICES) - 1) * (len(Y_VERTICES) - 1)
    result = compositor.compose(0.0, 0.0, pose)
    assert result.mode == "RGBA"
    assert result.size == (640, 768)


def test_production_module_has_only_pillow_and_standard_library_dependencies() -> None:
    module_path = Path(__file__).parents[1] / "src" / "desktop_pet" / "head_neck_deformation.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports.isdisjoint({"numpy", "cv2", "opencv", "live2d", "inochi2d"})
    source = module_path.read_text(encoding="utf-8").lower()
    assert "direction sprite" not in source
    assert "nearest pose" not in source

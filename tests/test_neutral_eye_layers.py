from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "assets/rig/v1/source/canonical-idle.png"
NEUTRAL_CANDIDATE = (
    ROOT / "assets/rig/v1/source/ai/neutral-eyeball-generated-v1.png"
)
REJECTED_MASK_DIR = ROOT / "assets/rig/v1/source/masks"
CANDIDATE_QA_DIR = ROOT / "qa/neutral-eye-v1/candidate"
APPROVED_ASSET_DIR = ROOT / "assets/rig/v1/source/eye-neutral-v1"
AUTHORED_PNGS = (
    "underlay.png",
    "eye-left.png",
    "eye-right.png",
    "eye-left-mask.png",
    "eye-right-mask.png",
)
CANONICAL_SHA256 = "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"
MOTION_LIMITS = {"x": 3.0, "y": 2.0}
EYES = ("left", "right")
FIXED_FEATURE_REGIONS = {
    "left": {
        "upper_lid_rim_face": (65, 328, 100, 335),
        "lower_tear_line": (65, 369, 100, 376),
    },
    "right": {
        "upper_lid_rim_face": (147, 323, 181, 333),
        "lower_tear_line": (147, 363, 181, 371),
    },
}
MOVING_FEATURE_SCANLINES = {
    "left": (
        (337, 76, 84),
        (340, 70, 89),
        (345, 66, 92),
        (350, 65, 93),
        (355, 66, 92),
        (360, 70, 89),
        (363, 75, 86),
    ),
    "right": (
        (334, 170, 171),
        (336, 160, 172),
        (338, 157, 174),
        (342, 153, 177),
        (347, 152, 178),
        (352, 153, 177),
        (357, 157, 173),
        (359, 161, 170),
    ),
}


def _builder_module():
    from tools import build_neutral_eye_layers

    return build_neutral_eye_layers


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _different_pixel_count(first: Image.Image, second: Image.Image) -> int:
    return sum(
        pixel != (0, 0, 0, 0)
        for pixel in tuple(ImageChops.difference(first, second).getdata())
    )


def _maximum_channel_delta(first: Image.Image, second: Image.Image) -> int:
    extrema = ImageChops.difference(first, second).getextrema()
    return max(channel_max for _, channel_max in extrema)


def _binary_support(mask: Image.Image) -> Image.Image:
    return mask.point(lambda value: 255 if value else 0)


def _decoded_png_signature(path: Path) -> tuple[str, tuple[int, int], bytes]:
    with Image.open(path) as image:
        return image.mode, image.size, image.tobytes()


def _assert_fresh_outputs_match_approved_pixels(asset_dir: Path) -> None:
    for filename in AUTHORED_PNGS:
        assert _decoded_png_signature(asset_dir / filename) == _decoded_png_signature(
            APPROVED_ASSET_DIR / filename
        )


def _normalize_test_only_snapshot_to_approved_bytes(asset_dir: Path) -> dict:
    """Prepare strict-loader/evidence integration inputs after the raw-pixel gate."""
    _assert_fresh_outputs_match_approved_pixels(asset_dir)
    for filename in AUTHORED_PNGS:
        (asset_dir / filename).write_bytes(
            (APPROVED_ASSET_DIR / filename).read_bytes()
        )
    (asset_dir / "authoring.json").write_bytes(
        (APPROVED_ASSET_DIR / "authoring.json").read_bytes()
    )
    return json.loads((asset_dir / "authoring.json").read_text(encoding="utf-8"))


@pytest.fixture()
def built(tmp_path: Path) -> tuple[Path, dict]:
    output_dir = tmp_path / "eye-neutral-v1"
    metadata = _builder_module().build_assets(CANONICAL, NEUTRAL_CANDIDATE, output_dir)
    return output_dir, metadata


@pytest.fixture()
def normalized_built(built: tuple[Path, dict]) -> tuple[Path, dict]:
    asset_dir, _ = built
    return asset_dir, _normalize_test_only_snapshot_to_approved_bytes(asset_dir)


def test_build_rejects_noncanonical_source(tmp_path: Path) -> None:
    modified = Image.open(CANONICAL).convert("RGBA")
    modified.putpixel((0, 0), (1, 2, 3, 4))
    modified_path = tmp_path / "modified.png"
    modified.save(modified_path)

    with pytest.raises(ValueError, match="canonical SHA-256"):
        _builder_module().build_assets(modified_path, NEUTRAL_CANDIDATE, tmp_path / "out")


def test_fresh_outputs_match_approved_mode_size_and_raw_pixels(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built

    _assert_fresh_outputs_match_approved_pixels(asset_dir)


def test_same_pixel_different_png_bytes_require_test_only_normalization(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built
    target = asset_dir / "underlay.png"
    approved = APPROVED_ASSET_DIR / target.name
    original_signature = _decoded_png_signature(target)
    with Image.open(target) as image:
        image.copy().save(target, format="PNG", optimize=False, compress_level=1)

    assert _decoded_png_signature(target) == original_signature
    assert target.read_bytes() != approved.read_bytes()

    from desktop_pet.neutral_eye_compositor import ValidatedNeutralEyeSnapshot

    with pytest.raises(ValueError, match="approved.*SHA|SHA.*approved"):
        ValidatedNeutralEyeSnapshot.load(asset_dir)

    normalized_metadata = _normalize_test_only_snapshot_to_approved_bytes(asset_dir)
    assert target.read_bytes() == approved.read_bytes()
    assert normalized_metadata == json.loads(
        (asset_dir / "authoring.json").read_text(encoding="utf-8")
    )
    assert ValidatedNeutralEyeSnapshot.load(asset_dir).images()[target.name].tobytes() == (
        original_signature[2]
    )


def test_authored_layers_have_expected_modes_sizes_and_metadata(built: tuple[Path, dict]) -> None:
    asset_dir, returned_metadata = built
    recorded_metadata = json.loads((asset_dir / "authoring.json").read_text(encoding="utf-8"))

    assert returned_metadata == recorded_metadata
    assert recorded_metadata["canonical"]["sha256"] == CANONICAL_SHA256
    assert recorded_metadata["canonical"]["mode"] == "RGBA"
    assert recorded_metadata["canonical"]["size"] == [512, 768]
    assert recorded_metadata["neutral_candidate"]["mode"] == "RGB"
    assert recorded_metadata["neutral_candidate"]["size"] == [1024, 1536]
    assert recorded_metadata["normalized_target"]["size"] == [512, 768]
    assert recorded_metadata["normalized_target"]["shared_source_eye"] == "right"
    assert recorded_metadata["motion_limits"] == MOTION_LIMITS
    assert recorded_metadata["warp"]["boundary_displacement"] == 0.0
    assert recorded_metadata["warp"]["falloff"] == "smoothstep normalized distance-to-boundary"
    assert "aperture-relative" in recorded_metadata["motion_resampling"]

    expected_files = {
        "underlay.png": "RGBA",
        "eye-left.png": "RGBA",
        "eye-right.png": "RGBA",
        "eye-left-mask.png": "L",
        "eye-right-mask.png": "L",
    }
    for filename, mode in expected_files.items():
        path = asset_dir / filename
        image = Image.open(path)
        assert image.mode == mode
        assert image.size == (512, 768)
        assert recorded_metadata["outputs"][filename]["sha256"] == _sha256(path)


def test_reviewed_masks_are_tight_antialiased_and_inside_rejected_masks(
    built: tuple[Path, dict],
) -> None:
    asset_dir, metadata = built
    rejected_limits = {"left": (45, 56), "right": (46, 57)}

    for eye in EYES:
        mask = Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L")
        rejected = Image.open(REJECTED_MASK_DIR / f"eye-{eye}-mask.png").convert("L")
        bbox = mask.getbbox()
        assert bbox is not None
        assert bbox == tuple(metadata["eyes"][eye]["reviewed_bounds"])
        assert bbox[2] - bbox[0] < rejected_limits[eye][0]
        assert bbox[3] - bbox[1] < rejected_limits[eye][1]
        assert any(0 < value < 255 for value in tuple(mask.getdata()))

        leaked_support = ImageChops.subtract(_binary_support(mask), _binary_support(rejected))
        assert leaked_support.getbbox() is None


def test_screen_left_neutral_globe_is_shifted_two_pixels_left_without_resizing(
    built: tuple[Path, dict],
) -> None:
    asset_dir, metadata = built
    mask = Image.open(asset_dir / "eye-left-mask.png").convert("L")
    expected_polygon = (
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
    )

    assert tuple(map(tuple, metadata["eyes"]["left"]["reviewed_polygon"])) == expected_polygon
    assert mask.getbbox() == (62, 335, 96, 367)
    mask_values = tuple(mask.getdata())
    assert sum(value > 0 for value in mask_values) == 852
    assert sum(value == 255 for value in mask_values) == 735
    assert sum(mask_values) == 201_484


def test_reviewed_masks_exclude_fixed_upper_and_lower_feature_regions(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built

    for eye in EYES:
        mask = Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L")
        for region in FIXED_FEATURE_REGIONS[eye].values():
            assert mask.crop(region).getbbox() is None


def test_all_five_poses_keep_fixed_upper_and_lower_regions_canonical_exact(
    normalized_built: tuple[Path, dict],
) -> None:
    asset_dir, _ = normalized_built
    canonical = Image.open(CANONICAL).convert("RGBA")
    offsets = (
        (0.0, 0.0),
        (-MOTION_LIMITS["x"], 0.0),
        (MOTION_LIMITS["x"], 0.0),
        (0.0, -MOTION_LIMITS["y"]),
        (0.0, MOTION_LIMITS["y"]),
    )
    poses = {
        offset: _builder_module().compose_pose(asset_dir, *offset) for offset in offsets
    }

    for eye in EYES:
        for region in FIXED_FEATURE_REGIONS[eye].values():
            expected = canonical.crop(region).convert("RGB")
            for offset in offsets:
                pose = poses[offset]
                assert ImageChops.difference(
                    pose.crop(region).convert("RGB"), expected
                ).getbbox() is None


def test_neutral_plateau_covers_full_reviewed_interior_without_iris_or_highlight(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built
    underlay = Image.open(asset_dir / "underlay.png").convert("RGB")

    for eye in EYES:
        mask = Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L")
        reviewed_interior = mask.point(lambda value: 255 if value == 255 else 0)

        for y, start_x, end_x in MOVING_FEATURE_SCANLINES[eye]:
            assert all(
                mask.getpixel((x, y)) == 255 for x in range(start_x, end_x + 1)
            )

        bbox = reviewed_interior.getbbox()
        assert bbox is not None
        for y in range(bbox[1], bbox[3]):
            for x in range(bbox[0], bbox[2]):
                if reviewed_interior.getpixel((x, y)):
                    pixel = underlay.getpixel((x, y))
                    assert max(pixel) - min(pixel) <= 50

    right_reviewed = Image.open(
        asset_dir / "eye-right-mask.png"
    ).convert("L").point(lambda value: 255 if value == 255 else 0)
    right_highlight_box = (165, 328, 180, 345)
    for y in range(right_highlight_box[1], right_highlight_box[3]):
        for x in range(right_highlight_box[0], right_highlight_box[2]):
            if right_reviewed.getpixel((x, y)):
                pixel = underlay.getpixel((x, y))
                assert sum(pixel) / 3.0 <= 225.0


def test_neutral_underlay_retains_diffuse_low_frequency_globe_curvature(
    built: tuple[Path, dict],
) -> None:
    asset_dir, metadata = built
    underlay = Image.open(asset_dir / "underlay.png").convert("RGB")

    for eye in EYES:
        reviewed_interior = Image.open(
            asset_dir / f"eye-{eye}-mask.png"
        ).convert("L").point(lambda value: 255 if value == 255 else 0)
        anchor_x, anchor_y = metadata["eyes"][eye]["movement_anchor"]
        radial_means = []
        for inner_radius, outer_radius in ((0.0, 3.0), (8.0, 12.0), (13.0, 17.0)):
            luminances = []
            for y in range(reviewed_interior.height):
                for x in range(reviewed_interior.width):
                    distance = math.hypot(x - anchor_x, y - anchor_y)
                    if (
                        inner_radius <= distance <= outer_radius
                        and reviewed_interior.getpixel((x, y))
                    ):
                        luminances.append(sum(underlay.getpixel((x, y))) / 3.0)
            assert luminances
            radial_means.append(sum(luminances) / len(luminances))

        assert radial_means[0] - radial_means[1] >= 6.5
        assert radial_means[1] - radial_means[2] >= 10.0


def test_reviewed_masks_exclude_fixed_dark_rims_but_keep_eye_features(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built
    safe_bounds = {
        "left": (62, 328, 103, 378),
        "right": (143, 323, 182, 372),
    }
    required_feature_points = {
        "left": ((80, 350),),
        "right": ((162, 346), (170, 334)),
    }

    for eye in EYES:
        mask = Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L")
        bbox = mask.getbbox()
        assert bbox is not None
        safe = safe_bounds[eye]
        assert bbox[0] >= safe[0]
        assert bbox[1] >= safe[1]
        assert bbox[2] <= safe[2]
        assert bbox[3] <= safe[3]
        assert all(mask.getpixel(point) == 255 for point in required_feature_points[eye])

def test_underlay_changes_only_inside_masks_and_preserves_canonical_alpha(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built
    canonical = Image.open(CANONICAL).convert("RGBA")
    underlay = Image.open(asset_dir / "underlay.png").convert("RGBA")
    union = ImageChops.lighter(
        Image.open(asset_dir / "eye-left-mask.png").convert("L"),
        Image.open(asset_dir / "eye-right-mask.png").convert("L"),
    )
    outside = ImageChops.invert(_binary_support(union))

    assert ImageChops.difference(canonical.getchannel("A"), underlay.getchannel("A")).getbbox() is None
    rgb_difference = ImageChops.difference(
        canonical.convert("RGB"), underlay.convert("RGB")
    )
    assert ImageChops.composite(
        rgb_difference, Image.new("RGB", canonical.size), outside
    ).getbbox() is None
    assert rgb_difference.getbbox() is not None


def test_neutral_underlay_has_no_near_black_feature_remnant_in_opaque_core(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built
    underlay = Image.open(asset_dir / "underlay.png").convert("RGB")

    for eye in EYES:
        mask = Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L")
        for y in range(mask.height):
            for x in range(mask.width):
                if mask.getpixel((x, y)) == 255:
                    assert max(underlay.getpixel((x, y))) > 64


def test_neutral_fill_removes_every_near_black_pixel_in_reviewed_pupil_boxes(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built
    underlay = Image.open(asset_dir / "underlay.png").convert("RGB")
    reviewed_pupil_boxes = {
        "left": (77, 337, 86, 364),
        "right": (159, 335, 167, 359),
    }

    for box in reviewed_pupil_boxes.values():
        for y in range(box[1], box[3]):
            for x in range(box[0], box[2]):
                assert max(underlay.getpixel((x, y))) > 64


def test_neutral_underlay_has_no_pupil_like_vertical_dark_depression(
    built: tuple[Path, dict],
) -> None:
    asset_dir, metadata = built
    underlay = Image.open(asset_dir / "underlay.png").convert("RGB")

    def luminance(point: tuple[int, int]) -> float:
        return sum(underlay.getpixel(point)) / 3.0

    for eye in EYES:
        anchor_x, anchor_y = (
            round(value) for value in metadata["eyes"][eye]["movement_anchor"]
        )
        center_column = sum(
            luminance((anchor_x, y)) for y in range(anchor_y - 6, anchor_y + 7)
        ) / 13
        side_columns = sum(
            luminance((x, y))
            for x in (anchor_x - 6, anchor_x + 6)
            for y in range(anchor_y - 6, anchor_y + 7)
        ) / 26
        assert side_columns - center_column <= 12.0


def test_eye_surfaces_are_masked_canonical_pixels_with_zero_transparent_rgb(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built
    canonical = Image.open(CANONICAL).convert("RGBA")

    for eye in EYES:
        surface = Image.open(asset_dir / f"eye-{eye}.png").convert("RGBA")
        mask = Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L")
        surface_alpha = surface.getchannel("A")
        assert ImageChops.difference(surface_alpha, mask).getbbox() is None

        canonical_pixels = canonical.load()
        surface_pixels = surface.load()
        for y in range(surface.height):
            for x in range(surface.width):
                rgba = surface_pixels[x, y]
                if rgba[3] == 0:
                    assert rgba[:3] == (0, 0, 0)
                else:
                    assert rgba[:3] == canonical_pixels[x, y][:3]


def test_zero_pose_uses_compositor_and_is_pixel_exact_canonical(
    normalized_built: tuple[Path, dict],
) -> None:
    asset_dir, _ = normalized_built
    canonical = Image.open(CANONICAL).convert("RGBA")

    center = _builder_module().compose_pose(asset_dir, eye_x=0.0, eye_y=0.0)

    assert center.mode == "RGBA"
    assert center.size == canonical.size
    assert _different_pixel_count(center, canonical) == 0
    assert _maximum_channel_delta(center, canonical) == 0


@pytest.mark.parametrize(
    ("eye_x", "eye_y"),
    [(-3.0, 0.0), (3.0, 0.0), (0.0, -2.0), (0.0, 2.0)],
)
def test_eye_motion_is_shared_bounded_and_clipped_to_stationary_apertures(
    normalized_built: tuple[Path, dict], eye_x: float, eye_y: float
) -> None:
    asset_dir, metadata = normalized_built
    canonical = Image.open(CANONICAL).convert("RGBA")
    pose = _builder_module().compose_pose(asset_dir, eye_x=eye_x, eye_y=eye_y)
    union = ImageChops.lighter(
        Image.open(asset_dir / "eye-left-mask.png").convert("L"),
        Image.open(asset_dir / "eye-right-mask.png").convert("L"),
    )
    outside = ImageChops.invert(_binary_support(union))

    assert metadata["eyes"]["left"]["movement_anchor"] != metadata["eyes"]["right"]["movement_anchor"]
    assert abs(eye_x) <= metadata["motion_limits"]["x"]
    assert abs(eye_y) <= metadata["motion_limits"]["y"]
    outside_difference = ImageChops.composite(
        ImageChops.difference(canonical, pose), Image.new("RGBA", canonical.size), outside
    )
    assert outside_difference.getbbox(alpha_only=False) is None


def test_rgba_default_bbox_would_miss_an_rgb_only_outside_support_change(
    built: tuple[Path, dict],
) -> None:
    asset_dir, _ = built
    canonical = Image.open(CANONICAL).convert("RGBA")
    union = ImageChops.lighter(
        Image.open(asset_dir / "eye-left-mask.png").convert("L"),
        Image.open(asset_dir / "eye-right-mask.png").convert("L"),
    )
    outside = ImageChops.invert(_binary_support(union))
    altered = canonical.copy()
    point = next(
        (x, y)
        for y in range(canonical.height)
        for x in range(canonical.width)
        if outside.getpixel((x, y))
    )
    red, green, blue, alpha = altered.getpixel(point)
    altered.putpixel(point, ((red + 1) % 256, green, blue, alpha))
    outside_difference = ImageChops.composite(
        ImageChops.difference(canonical, altered),
        Image.new("RGBA", canonical.size),
        outside,
    )

    assert outside_difference.getbbox() is None
    assert outside_difference.getbbox(alpha_only=False) is not None


@pytest.mark.parametrize(
    ("eye_x", "eye_y"),
    [(-3.0, 0.0), (3.0, 0.0), (0.0, -2.0), (0.0, 2.0)],
)
def test_warp_pins_aperture_boundary_and_moves_anchor_region(
    normalized_built: tuple[Path, dict], eye_x: float, eye_y: float
) -> None:
    asset_dir, metadata = normalized_built
    canonical = Image.open(CANONICAL).convert("RGBA")
    pose = _builder_module().compose_pose(asset_dir, eye_x=eye_x, eye_y=eye_y)

    for eye in EYES:
        mask = _binary_support(
            Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L")
        )
        boundary = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
        boundary_points = [
            (x, y)
            for y in range(boundary.height)
            for x in range(boundary.width)
            if boundary.getpixel((x, y))
        ]
        assert boundary_points
        assert all(pose.getpixel(point) == canonical.getpixel(point) for point in boundary_points)

        anchor_x, anchor_y = metadata["eyes"][eye]["movement_anchor"]
        anchor_box = (
            round(anchor_x) - 2,
            round(anchor_y) - 2,
            round(anchor_x) + 3,
            round(anchor_y) + 3,
        )
        assert ImageChops.difference(
            pose.crop(anchor_box).convert("RGB"),
            canonical.crop(anchor_box).convert("RGB"),
        ).getbbox() is not None


def test_warp_exposes_no_trailing_underlay_core(
    normalized_built: tuple[Path, dict],
) -> None:
    asset_dir, _ = normalized_built
    from desktop_pet.neutral_eye_compositor import (
        NeutralEyeCompositor,
        ValidatedNeutralEyeSnapshot,
    )

    snapshot = ValidatedNeutralEyeSnapshot.load(asset_dir)
    images = snapshot.images()
    underlay = images["underlay.png"]
    underlay_pixels = underlay.load()
    core_union = Image.new("L", underlay.size)
    for eye in EYES:
        mask = Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L")
        core_union = ImageChops.lighter(
            core_union, mask.point(lambda value: 255 if value == 255 else 0)
        )
    core_pixels = core_union.load()
    for y in range(underlay.height):
        for x in range(underlay.width):
            if core_pixels[x, y]:
                underlay_pixels[x, y] = (255, 0, 255, underlay_pixels[x, y][3])
    compositor = NeutralEyeCompositor._from_images(snapshot.authoring(), images)

    for offset in ((-3.0, 0.0), (3.0, 0.0), (0.0, -2.0), (0.0, 2.0)):
        pose = compositor.compose(*offset)
        pose_pixels = pose.load()
        for y in range(pose.height):
            for x in range(pose.width):
                if core_pixels[x, y]:
                    red, green, blue, _ = pose_pixels[x, y]
                    assert not (red >= 220 and green <= 35 and blue >= 220)


def test_out_of_range_motion_is_rejected(
    normalized_built: tuple[Path, dict],
) -> None:
    asset_dir, _ = normalized_built

    with pytest.raises(ValueError, match="motion limits"):
        _builder_module().compose_pose(asset_dir, eye_x=3.01, eye_y=0.0)
    with pytest.raises(ValueError, match="motion limits"):
        _builder_module().compose_pose(asset_dir, eye_x=0.0, eye_y=-2.01)


def test_extreme_poses_add_no_near_black_pixels_in_outer_boundary_ring(
    normalized_built: tuple[Path, dict],
) -> None:
    asset_dir, _ = normalized_built
    canonical = Image.open(CANONICAL).convert("RGBA")
    canonical_pixels = canonical.load()

    for eye in EYES:
        mask = _binary_support(Image.open(asset_dir / f"eye-{eye}-mask.png").convert("L"))
        outer_ring = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(7)), mask)
        ring_pixels = outer_ring.load()
        for eye_x, eye_y in ((-3.0, 0.0), (3.0, 0.0), (0.0, -2.0), (0.0, 2.0)):
            pose_pixels = _builder_module().compose_pose(asset_dir, eye_x, eye_y).load()
            for y in range(canonical.height):
                for x in range(canonical.width):
                    if ring_pixels[x, y]:
                        canonical_near_black = max(canonical_pixels[x, y][:3]) <= 24
                        pose_near_black = max(pose_pixels[x, y][:3]) <= 24
                        assert not (pose_near_black and not canonical_near_black)


def test_contact_sheet_writes_required_static_evidence_and_stats(
    normalized_built: tuple[Path, dict], tmp_path: Path
) -> None:
    asset_dir, _ = normalized_built
    qa_dir = tmp_path / "qa"

    stats = _builder_module().build_contact_sheet(asset_dir, qa_dir)

    required = {
        "center.png",
        "left.png",
        "right.png",
        "up.png",
        "down.png",
        "layer-contact-sheet.png",
        "stats.json",
    }
    assert required <= {path.name for path in qa_dir.iterdir()}
    assert stats == json.loads((qa_dir / "stats.json").read_text(encoding="utf-8"))
    assert stats["center"]["changed_pixels"] == 0
    assert stats["center"]["maximum_channel_delta"] == 0
    assert stats["poses"]["left"]["offset"] == [-3.0, 0.0]
    assert stats["poses"]["right"]["offset"] == [3.0, 0.0]
    assert stats["poses"]["up"]["offset"] == [0.0, -2.0]
    assert stats["poses"]["down"]["offset"] == [0.0, 2.0]
    assert stats["warp"]["falloff"] == "smoothstep normalized distance-to-boundary"
    assert stats["r5_status"] == (
        "N1 static eye layers accepted; organic-head R5 center visual gate remains unapproved and blocked."
    )
    for pose_name in ("left", "right", "up", "down"):
        assert stats["poses"][pose_name]["anchor_displacement"] == stats["poses"][pose_name]["offset"]
    assert Image.open(qa_dir / "layer-contact-sheet.png").size[0] >= 1280


def test_contact_sheet_motion_limit_caption_uses_single_source_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _builder_module()
    monkeypatch.setattr(module, "MOTION_LIMITS", {"x": 9.5, "y": 8.2})

    assert module.motion_limit_caption() == (
        "Fixed eyelids/rims. Shared target limits: horizontal ±9.5 px, vertical ±8.2 px."
    )


def test_committed_candidate_evidence_uses_exact_motion_limit_extremes() -> None:
    stats = json.loads((CANDIDATE_QA_DIR / "stats.json").read_text(encoding="utf-8"))

    assert stats["motion_limits"] == MOTION_LIMITS
    expected_offsets = {
        "left": [-3.0, 0.0],
        "right": [3.0, 0.0],
        "up": [0.0, -2.0],
        "down": [0.0, 2.0],
    }
    for name, expected_offset in expected_offsets.items():
        assert stats["poses"][name]["offset"] == expected_offset
        assert stats["poses"][name]["anchor_displacement"] == expected_offset


def test_contact_sheet_stats_detect_a_corrupted_center(
    normalized_built: tuple[Path, dict], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset_dir, _ = normalized_built
    module = _builder_module()
    real_compose_pose = module.compose_pose

    def corrupted_center(asset_path: Path, eye_x: float, eye_y: float) -> Image.Image:
        pose = real_compose_pose(asset_path, eye_x, eye_y)
        if eye_x == 0.0 and eye_y == 0.0:
            pose.putpixel((0, 0), (1, 2, 3, 4))
        return pose

    monkeypatch.setattr(module, "compose_pose", corrupted_center)
    stats = module.build_contact_sheet(asset_dir, tmp_path / "corrupted-qa")

    assert stats["center"]["changed_pixels"] > 0
    assert stats["center"]["maximum_channel_delta"] > 0


def test_two_builds_are_same_host_same_codec_byte_deterministic(
    tmp_path: Path,
) -> None:
    module = _builder_module()
    asset_dirs = [tmp_path / "first-assets", tmp_path / "second-assets"]
    qa_dirs = [tmp_path / "first-qa", tmp_path / "second-qa"]

    fresh_asset_hashes = []
    for asset_dir, qa_dir in zip(asset_dirs, qa_dirs, strict=True):
        module.build_assets(CANONICAL, NEUTRAL_CANDIDATE, asset_dir)
        _assert_fresh_outputs_match_approved_pixels(asset_dir)
        fresh_asset_hashes.append(
            {
                name: _sha256(asset_dir / name)
                for name in (
                    "underlay.png",
                    "eye-left.png",
                    "eye-right.png",
                    "eye-left-mask.png",
                    "eye-right-mask.png",
                    "authoring.json",
                )
            }
        )
        _normalize_test_only_snapshot_to_approved_bytes(asset_dir)
        module.build_contact_sheet(asset_dir, qa_dir)

    asset_names = (
        "underlay.png",
        "eye-left.png",
        "eye-right.png",
        "eye-left-mask.png",
        "eye-right-mask.png",
        "authoring.json",
    )
    evidence_names = (
        "center.png",
        "left.png",
        "right.png",
        "up.png",
        "down.png",
        "layer-contact-sheet.png",
        "stats.json",
    )
    assert fresh_asset_hashes[0] == fresh_asset_hashes[1]
    assert {name: _sha256(qa_dirs[0] / name) for name in evidence_names} == {
        name: _sha256(qa_dirs[1] / name) for name in evidence_names
    }

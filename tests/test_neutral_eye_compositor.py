from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import pytest
from PIL import Image, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets/rig/v1/source/eye-neutral-v1"
CANONICAL = ROOT / "assets/rig/v1/source/canonical-idle.png"
CANVAS_SIZE = (512, 768)
MOTION_LIMITS = {"x": 3.0, "y": 2.0}
EYES = ("left", "right")
OUTPUTS = {
    "underlay.png": "RGBA",
    "eye-left.png": "RGBA",
    "eye-right.png": "RGBA",
    "eye-left-mask.png": "L",
    "eye-right-mask.png": "L",
}
OUTPUT_SHA256 = {
    "underlay.png": "d83230b60fe753b7344ae0b349d0c1409b47dc2002df66c5689765fcb0ca2495",
    "eye-left.png": "6140a3a4085d8514795ea2c17ee2173964553c604f0d096a120a508fa9f7308c",
    "eye-right.png": "9528b5f3c985b8366003fd77d413ff564b50ae547c705e5e6aee85fc86542906",
    "eye-left-mask.png": "27bee30342e67cab45d77a14ad7eebb0125f72d4b19039b5c3c1bf506623a81c",
    "eye-right-mask.png": "fba54f4eb10884d5a284ea6c16cd762d0786f61e09ddc5297e99d793c3a092e4",
}
RAW_RGBA_GOLDENS = {
    (0.0, 0.0): "67a599d92c8065df95b8cec85a1e5d0841e1023ee04b1a21f5719613077a328e",
    (-3.0, 0.0): "2057931808a7ab55b05851e4957c603dfc75057953c4c9b8799a033539bbf321",
    (3.0, 0.0): "ca341760500c3b5afedafaa065f98880bbdb4672f1e37f2ea3a90a3e488e4909",
    (0.0, -2.0): "49da1352ab2ec3fd9840ab9e46a1a5af2fb5158cfbd8ff30838ed69e37e6012f",
    (0.0, 2.0): "5cd56af316aea3b3c69e6ce35ac578af52019a131a57d447ef8ec0823587211c",
    (-3.0, -2.0): "907464507980b2527cc5917a2c8f3ca5437da10b679f072762ec038b2cd5ec0d",
    (3.0, -2.0): "d045ad0ad7161f5b62f966128d782d33aaf2526616d17d40daf52d3ca7e97de2",
    (-3.0, 2.0): "4c872b57ebb313a98cda35f98b467b491863d39b8965cf1cb7bb58fb2d7754e7",
    (3.0, 2.0): "f4ec4e1a7b35bd1d6bf720cbf07a846c168fab40b76e75b018835dd1f25e12f0",
    (1.25, -0.75): "dd9e07abb1875a6f5a3457a742103c684d87d3c359dc2a25767882426ce74fdb",
    (-2.4, 1.1): "ac4f0ec90c05ca33085803e5391ddd100ac2f587fdefb0af897e220cf2e3b493",
    (1.0 / 3.0, -1.2345): "f26113bf8f11e0def527e1d4e96263534770237047548d6421512283482883dc",
}

def _compositor_class():
    from desktop_pet.neutral_eye_compositor import NeutralEyeCompositor

    return NeutralEyeCompositor


def _raw_hash(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binary_support(mask: Image.Image) -> Image.Image:
    return mask.point(lambda value: 255 if value else 0)


def _copy_assets(tmp_path: Path) -> Path:
    copied = tmp_path / "eye-neutral-v1"
    shutil.copytree(ASSET_DIR, copied)
    return copied


def _read_authoring(asset_dir: Path) -> dict:
    return json.loads((asset_dir / "authoring.json").read_text(encoding="utf-8"))


def _write_authoring(asset_dir: Path, authoring: dict) -> None:
    (asset_dir / "authoring.json").write_text(
        json.dumps(authoring, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_load_exposes_geometry_and_all_pre_extraction_raw_rgba_goldens() -> None:
    compositor = _compositor_class().load(ASSET_DIR)

    assert compositor.source_size == CANVAS_SIZE
    assert compositor.eye_midpoint == (122.5, 349.0)
    for offset, expected_hash in RAW_RGBA_GOLDENS.items():
        pose = compositor.compose(*offset)
        assert pose.mode == "RGBA"
        assert pose.size == CANVAS_SIZE
        assert _raw_hash(pose) == expected_hash


def test_all_golden_poses_preserve_alpha_containment_boundaries_and_outer_ring() -> None:
    compositor = _compositor_class().load(ASSET_DIR)
    canonical = Image.open(CANONICAL).convert("RGBA")
    masks = {
        eye: Image.open(ASSET_DIR / f"eye-{eye}-mask.png").convert("L")
        for eye in EYES
    }
    support = ImageChops.lighter(*(_binary_support(mask) for mask in masks.values()))
    outside = ImageChops.invert(support)
    ring = ImageChops.subtract(support.filter(ImageFilter.MaxFilter(7)), support)
    canonical_pixels = canonical.load()
    ring_points = [
        (x, y)
        for y in range(CANVAS_SIZE[1])
        for x in range(CANVAS_SIZE[0])
        if ring.getpixel((x, y)) and max(canonical_pixels[x, y][:3]) > 24
    ]
    boundaries = {
        eye: ImageChops.subtract(
            _binary_support(mask),
            _binary_support(mask).filter(ImageFilter.MinFilter(3)),
        )
        for eye, mask in masks.items()
    }
    boundary_points = {
        eye: [
            (x, y)
            for y in range(CANVAS_SIZE[1])
            for x in range(CANVAS_SIZE[0])
            if boundaries[eye].getpixel((x, y))
        ]
        for eye in EYES
    }

    for offset in RAW_RGBA_GOLDENS:
        pose = compositor.compose(*offset)
        assert pose.getchannel("A").tobytes() == canonical.getchannel("A").tobytes()
        outside_delta = Image.composite(
            ImageChops.difference(pose, canonical),
            Image.new("RGBA", CANVAS_SIZE),
            outside,
        )
        assert outside_delta.getbbox(alpha_only=False) is None
        assert all(
            pose.getpixel(point) == canonical.getpixel(point)
            for points in boundary_points.values()
            for point in points
        )
        pose_pixels = pose.load()
        assert not any(max(pose_pixels[x, y][:3]) <= 24 for x, y in ring_points)


@pytest.mark.parametrize(
    ("eye_x", "eye_y"),
    [
        (math.nan, 0.0),
        (math.inf, 0.0),
        (-math.inf, 0.0),
        (0.0, math.nan),
        (0.0, math.inf),
        (3.000001, 0.0),
        (-3.000001, 0.0),
        (0.0, 2.000001),
        (0.0, -2.000001),
    ],
)
def test_compose_rejects_nonfinite_and_out_of_range_offsets_before_work(
    eye_x: float, eye_y: float
) -> None:
    compositor = _compositor_class().load(ASSET_DIR)

    with pytest.raises(ValueError, match="finite.*motion limits|motion limits.*finite"):
        compositor.compose(eye_x, eye_y)


def test_compose_performs_no_image_or_json_io_after_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compositor = _compositor_class().load(ASSET_DIR)

    def forbidden_io(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("compose must use construction-time caches only")

    monkeypatch.setattr(Image, "open", forbidden_io)
    monkeypatch.setattr(Path, "read_bytes", forbidden_io)
    monkeypatch.setattr(Path, "read_text", forbidden_io)
    assert _raw_hash(compositor.compose(1.25, -0.75)) == RAW_RGBA_GOLDENS[(1.25, -0.75)]


def test_supported_pillow_api_does_not_require_post_pillow_11_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden_api = "get_" + "flattened_data"
    relevant_paths = [
        ROOT / "src/desktop_pet/neutral_eye_compositor.py",
        ROOT / "tools/build_neutral_eye_layers.py",
        ROOT / "tools/build_neutral_eye_preview.py",
        ROOT / "tools/build_approved_runtime_assets.py",
        ROOT / "tests/test_neutral_eye_compositor.py",
        ROOT / "tests/test_neutral_eye_layers.py",
        ROOT / "tests/test_neutral_eye_preview.py",
    ]
    assert all(
        forbidden_api not in path.read_text(encoding="utf-8")
        for path in relevant_paths
    )

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Pillow >=11,<12 does not provide this API")

    monkeypatch.setattr(Image.Image, forbidden_api, forbidden, raising=False)
    assert _raw_hash(_compositor_class().load(ASSET_DIR).compose(0.0, 0.0)) == (
        RAW_RGBA_GOLDENS[(0.0, 0.0)]
    )


def test_caller_mutation_does_not_corrupt_cached_center_or_future_poses() -> None:
    compositor = _compositor_class().load(ASSET_DIR)
    center = compositor.compose(0.0, 0.0)
    fractional = compositor.compose(1.25, -0.75)

    center.putpixel((82, 351), (255, 0, 255, 0))
    fractional.putpixel((163, 347), (255, 0, 255, 0))

    assert _raw_hash(compositor.compose(0.0, 0.0)) == RAW_RGBA_GOLDENS[(0.0, 0.0)]
    assert _raw_hash(compositor.compose(1.25, -0.75)) == RAW_RGBA_GOLDENS[(1.25, -0.75)]


def test_load_rejects_png_and_authoring_hash_changed_together(tmp_path: Path) -> None:
    asset_dir = _copy_assets(tmp_path)
    underlay_path = asset_dir / "underlay.png"
    underlay = Image.open(underlay_path).convert("RGBA")
    underlay.putpixel((0, 0), (1, 2, 3, 4))
    underlay.save(underlay_path)
    authoring = _read_authoring(asset_dir)
    authoring["outputs"]["underlay.png"]["sha256"] = _file_hash(underlay_path)
    _write_authoring(asset_dir, authoring)

    with pytest.raises(ValueError, match="approved.*SHA|SHA.*approved"):
        _compositor_class().load(asset_dir)


def test_load_hashes_and_decodes_each_file_from_the_same_single_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset_dir = _copy_assets(tmp_path)
    target = asset_dir / "underlay.png"
    input_paths = {
        asset_dir / "authoring.json",
        *(asset_dir / filename for filename in OUTPUTS),
    }
    counts = {path: 0 for path in input_paths}
    real_read_bytes = Path.read_bytes
    real_write_bytes = Path.write_bytes

    def read_then_swap(path: Path) -> bytes:
        data = real_read_bytes(path)
        if path in counts:
            counts[path] += 1
        if path == target and counts[path] == 1:
            real_write_bytes(path, b"swapped after validated read")
        return data

    monkeypatch.setattr(Path, "read_bytes", read_then_swap)
    compositor = _compositor_class().load(asset_dir)

    assert counts == {path: 1 for path in input_paths}
    assert _raw_hash(compositor.compose(0.0, 0.0)) == RAW_RGBA_GOLDENS[(0.0, 0.0)]


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("canonical_metadata", "canonical metadata"),
        ("missing_output", "outputs"),
        ("output_hash", "approved.*SHA|SHA.*approved"),
        ("output_mode", "output metadata"),
        ("output_size", "output metadata"),
        ("motion_limits", "motion limits"),
        ("warp_metadata", "warp metadata"),
        ("nonfinite_anchor", "finite"),
        ("overflowing_anchor", "anchor"),
        ("outside_canvas_anchor", "outside the canvas"),
        ("anchor_outside_support", "outside support"),
        ("fractional_boundary_anchor", "strictly inside support"),
        ("empty_support", "support is empty"),
        ("no_positive_boundary_distance", "positive boundary distance"),
    ],
)
def test_load_rejects_invalid_authoring_outputs_geometry_and_supports(
    tmp_path: Path, case: str, message: str
) -> None:
    asset_dir = _copy_assets(tmp_path)
    authoring = _read_authoring(asset_dir)
    semantic_images: dict[str, Image.Image] | None = None
    if case == "canonical_metadata":
        authoring["canonical"]["mode"] = "RGB"
    elif case == "missing_output":
        del authoring["outputs"]["eye-right.png"]
    elif case == "output_hash":
        authoring["outputs"]["underlay.png"]["sha256"] = "0" * 64
    elif case == "output_mode":
        authoring["outputs"]["underlay.png"]["mode"] = "RGB"
    elif case == "output_size":
        authoring["outputs"]["underlay.png"]["size"] = [511, 768]
    elif case == "motion_limits":
        authoring["motion_limits"]["x"] = 4.0
    elif case == "warp_metadata":
        authoring["warp"]["falloff"] = "linear"
    elif case == "nonfinite_anchor":
        authoring["eyes"]["left"]["movement_anchor"][0] = math.nan
    elif case == "overflowing_anchor":
        authoring["eyes"]["left"]["movement_anchor"][0] = 10**400
    elif case == "outside_canvas_anchor":
        authoring["eyes"]["left"]["movement_anchor"] = [-1.0, 351.0]
    elif case == "anchor_outside_support":
        authoring["eyes"]["left"]["movement_anchor"] = [0.0, 0.0]
    elif case == "fractional_boundary_anchor":
        authoring["eyes"]["left"]["movement_anchor"] = [62.5, 351.5]
    elif case in {"empty_support", "no_positive_boundary_distance"}:
        from desktop_pet.neutral_eye_compositor import ValidatedNeutralEyeSnapshot

        semantic_images = ValidatedNeutralEyeSnapshot.load(asset_dir).images()
        mask = Image.new("L", CANVAS_SIZE)
        if case == "no_positive_boundary_distance":
            mask.putpixel((82, 351), 255)
        semantic_images["eye-left-mask.png"] = mask

    with pytest.raises(ValueError, match=message):
        if semantic_images is None:
            _write_authoring(asset_dir, authoring)
            _compositor_class().load(asset_dir)
        else:
            _compositor_class()._from_images(authoring, semantic_images)


def test_compose_converts_float_overflow_to_value_error() -> None:
    compositor = _compositor_class().load(ASSET_DIR)

    with pytest.raises(ValueError, match="finite.*motion limits"):
        compositor.compose(10**400, 0.0)


def test_warm_thirty_noncenter_compositions_fit_cloud_budget() -> None:
    compositor = _compositor_class().load(ASSET_DIR)
    poses = tuple(
        (-2.9 + 5.8 * index / 29, -1.9 + 3.8 * ((index * 7) % 30) / 29)
        for index in range(30)
    )
    compositor.compose(*poses[0])

    started = perf_counter()
    for pose in poses:
        compositor.compose(*pose)
    elapsed = perf_counter() - started

    assert elapsed < 0.60, f"30 warm source compositions took {elapsed:.6f}s"


@pytest.mark.parametrize(
    "tool",
    ["tools/build_neutral_eye_layers.py", "tools/build_neutral_eye_preview.py"],
)
def test_authoring_tool_help_supports_direct_source_tree_execution_without_pythonpath(
    tool: str,
) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, tool, "--help"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


@pytest.mark.parametrize(
    "tool",
    ["tools/build_neutral_eye_layers.py", "tools/build_neutral_eye_preview.py"],
)
def test_direct_script_diagnostic_uses_repository_compositor_before_fake_installed_package(
    tmp_path: Path, tool: str
) -> None:
    fake_package = tmp_path / "installed" / "desktop_pet"
    fake_package.mkdir(parents=True)
    (fake_package / "__init__.py").write_text("", encoding="utf-8")
    (fake_package / "neutral_eye_compositor.py").write_text(
        "class NeutralEyeCompositor:\n    pass\n", encoding="utf-8"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(fake_package.parent)

    result = subprocess.run(
        [sys.executable, tool, "--show-compositor-path"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    expected = (ROOT / "src/desktop_pet/neutral_eye_compositor.py").resolve()
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).resolve() == expected

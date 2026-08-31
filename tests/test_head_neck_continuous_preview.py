from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import shutil
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
EYE_ASSETS = ROOT / "assets/rig/v1/source/eye-neutral-v1"
CANONICAL = ROOT / "assets/rig/v1/source/canonical-idle.png"
RUNTIME_ASSETS = ROOT / "assets/rig/v1/runtime"
COMMITTED_OUTPUT = ROOT / "qa/head-neck-continuous-v1"
X_VERTICES = [0, 24, 36, 48, 60, 72, 82, 93, 108, 118, 128, 139, 151, 163, 176, 184, 194, 205, 218, 230, 242, 249, 256, 264, 320]
Y_VERTICES = [160, 186, 202, 223, 250, 275, 300, 320, 335, 351, 370, 397, 425, 454, 485, 520, 555, 565, 592]


def _module():
    from tools import build_head_neck_continuous_preview

    return build_head_neck_continuous_preview


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _input_hashes(asset_dir: Path = EYE_ASSETS, canonical: Path = CANONICAL) -> dict[Path, str]:
    module = _module()
    paths = {
        canonical,
        asset_dir / "authoring.json",
        *(asset_dir / filename for filename in module.EYE_OUTPUTS),
    }
    return {path: _sha256(path) for path in paths}


@pytest.fixture(scope="module")
def preview(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    output = tmp_path_factory.mktemp("head-neck-preview") / "output"
    return output, _module().build_preview(EYE_ASSETS, CANONICAL, output)


def test_preview_pose_is_immutable_and_unique_timeline_is_exact() -> None:
    module = _module()
    poses = module.coordinated_preview_poses()

    assert len(poses) == 240
    with pytest.raises(FrozenInstanceError):
        poses[0].head_x = 1.0  # type: ignore[misc]
    assert all(module.target_for_frame(index) == (0.0, 0.0) for index in range(12))
    for index in range(12, 30):
        j = index - 12
        u = (j + 1) / 18
        smooth = u * u * (3 - 2 * u)
        assert module.target_for_frame(index) == pytest.approx((0.85 * smooth, 0.0), abs=1e-15)
    for index in range(30, 150):
        theta = 2 * math.pi * (index - 30) / 120
        assert module.target_for_frame(index) == pytest.approx(
            (0.85 * math.cos(theta), 0.85 * math.sin(theta)), abs=1e-15
        )
    last_orbit = module.target_for_frame(149)
    for index in range(150, 168):
        j = index - 150
        u = (j + 1) / 18
        remaining = 1 - u * u * (3 - 2 * u)
        assert module.target_for_frame(index) == pytest.approx(
            (last_orbit[0] * remaining, last_orbit[1] * remaining), abs=1e-15
        )
    assert all(module.target_for_frame(index) == (0.0, 0.0) for index in range(168, 240))
    with pytest.raises(ValueError):
        module.target_for_frame(-1)
    with pytest.raises(ValueError):
        module.target_for_frame(240)


def test_coordinated_states_step_oracle_continuity_settle_and_eye_envelope() -> None:
    module = _module()
    poses = module.coordinated_preview_poses()
    alpha_focus = 1 - math.exp(-(1 / 30) / 0.060)
    alpha_head = 1 - math.exp(-(1 / 30) / 0.220)
    focus = (0.0, 0.0)
    head = (0.0, 0.0)
    for pose in poses[:228]:
        target = (pose.target_x, pose.target_y)
        focus = tuple(
            current + alpha_focus * (requested - current)
            for current, requested in zip(focus, target, strict=True)
        )
        head = tuple(
            current + alpha_head * (requested - current)
            for current, requested in zip(head, target, strict=True)
        )
        assert (pose.focus_x, pose.focus_y) == pytest.approx(focus, abs=1e-15)
        assert (pose.head_x, pose.head_y) == pytest.approx(head, abs=1e-15)
        residual = (focus[0] - 0.35 * head[0], focus[1] - 0.35 * head[1])
        assert (pose.eye_x, pose.eye_y) == pytest.approx(
            (3.0 * residual[0], 2.0 * residual[1]), abs=1e-15
        )
        assert math.hypot(*focus) <= 1.0
        assert math.hypot(*head) <= 1.0
        assert abs(pose.eye_x) <= 3.0 and abs(pose.eye_y) <= 2.0

    target_steps = [
        math.dist((first.target_x, first.target_y), (second.target_x, second.target_y))
        for first, second in zip(poses[:-1], poses[1:], strict=True)
    ]
    head_steps = [
        math.dist((first.head_x, first.head_y), (second.head_x, second.head_y))
        for first, second in zip(poses[:-1], poses[1:], strict=True)
    ]
    assert max(target_steps) <= 0.075
    assert max(head_steps) == pytest.approx(0.0520962, abs=1e-6)
    assert max(head_steps) <= 0.055
    residual_227 = (poses[227].eye_x / 3.0, poses[227].eye_y / 2.0)
    assert max(
        math.hypot(poses[227].focus_x, poses[227].focus_y),
        math.hypot(poses[227].head_x, poses[227].head_y),
        math.hypot(*residual_227),
    ) <= 0.0001
    assert all(
        pose == module.PreviewPose(pose.index, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        for pose in poses[228:]
    )

    oracle = module._step_response_oracle()
    assert oracle["sample_count"] == 30
    assert oracle["focus_strictly_ahead"] is True
    assert oracle["focus_first_90_index"] <= 4
    assert oracle["head_first_90_index"] >= 15
    assert oracle["lead_frames"] >= 10


def test_reviewed_render_gain_increases_head_without_changing_filter_state() -> None:
    module = _module()
    poses = module.coordinated_preview_poses()
    assert 1.20 <= module.HEAD_RENDER_GAIN <= 1.23

    peak = max(poses, key=lambda pose: math.hypot(pose.head_x, pose.head_y))
    rendered_x, rendered_y = module._render_head_coordinates(peak)
    state_magnitude = math.hypot(peak.head_x, peak.head_y)
    rendered_magnitude = math.hypot(rendered_x, rendered_y)
    assert rendered_magnitude == pytest.approx(
        state_magnitude * module.HEAD_RENDER_GAIN,
        abs=1e-15,
    )
    assert 0.96 <= rendered_magnitude <= 1.0

    center = poses[228]
    assert module._render_head_coordinates(center) == (0.0, 0.0)
    assert (peak.eye_x, peak.eye_y) == (
        3.0 * (peak.focus_x - 0.35 * peak.head_x),
        2.0 * (peak.focus_y - 0.35 * peak.head_y),
    )


def test_metric_summaries_preserve_signed_orientation_and_semantic_bounds() -> None:
    module = _module()
    eye_compositor = module.NeutralEyeCompositor.load(EYE_ASSETS)
    compositor = module.ContinuousHeadNeckCompositor(eye_compositor)

    mesh = module._mesh_metrics(
        compositor,
        (
            module.HeadPose(-1.0, 0.0),
            module.HeadPose(1.0, 0.0),
            module.HeadPose(0.0, -1.0),
            module.HeadPose(0.0, 1.0),
        ),
    )
    assert mesh["signed_source_area_max"] < 0.0
    assert mesh["signed_source_area_min"] == pytest.approx(-mesh["source_area_max"])
    assert mesh["signed_source_area_max"] == pytest.approx(-mesh["source_area_min"])
    assert mesh["signed_source_output_area_ratio_min"] == pytest.approx(
        -mesh["source_output_area_ratio_max"]
    )
    assert mesh["signed_source_output_area_ratio_max"] == pytest.approx(
        -mesh["source_output_area_ratio_min"]
    )
    assert mesh["orientation_sign_min"] == -1
    assert mesh["orientation_sign_max"] == -1

    semantic = module._semantic_metrics(compositor)
    samples = semantic["cardinal_displacements"]
    point_names = set(module.SEMANTIC_POINTS)
    assert set(semantic["point_displacement_minima"]) == point_names
    assert set(semantic["point_displacement_maxima"]) == point_names
    expected_minima = {
        point: min(direction[point] for direction in samples.values())
        for point in point_names
    }
    expected_maxima = {
        point: max(direction[point] for direction in samples.values())
        for point in point_names
    }
    assert semantic["point_displacement_minima"] == pytest.approx(expected_minima)
    assert semantic["point_displacement_maxima"] == pytest.approx(expected_maxima)
    assert semantic["cardinal_displacement_min"] == pytest.approx(min(expected_minima.values()))
    assert semantic["cardinal_displacement_max"] == pytest.approx(max(expected_maxima.values()))


def test_build_has_exact_allowlist_mesh_gates_and_scope(preview: tuple[Path, dict[str, object]]) -> None:
    module = _module()
    output, stats = preview
    assert {path.name for path in output.iterdir()} == module.OUTPUT_FILENAMES
    assert stats == json.loads((output / "stats.json").read_text(encoding="utf-8"))
    assert stats["roi"] == [0, 160, 320, 432]
    assert stats["mesh"]["x_vertices"] == X_VERTICES
    assert stats["mesh"]["y_vertices"] == Y_VERTICES
    assert len(X_VERTICES) == 25 and len(Y_VERTICES) == 19
    assert stats["constants"]["contact_frame_indices"] == [0, 30, 45, 60, 75, 90, 105, 120, 135]
    assert stats["constants"]["canonical_enclosed_hole_baselines"] == {
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
    assert stats["constants"]["blocking_enclosed_hole_connectivity"] == 8
    assert stats["constants"]["significant_hole_min_area_source_pixels"] == 16
    assert 1.20 <= stats["constants"]["head_render_gain"] <= 1.23
    assert stats["constants"]["deformation_gain"] == 2.0
    assert stats["pose_extrema"]["target_step_max"] <= 0.075
    assert stats["pose_extrema"]["head_state_step_max"] <= 0.055
    assert 0.96 <= stats["pose_extrema"]["rendered_head_magnitude_max"] <= 1.0
    assert stats["pose_extrema"]["rendered_head_step_max"] <= 0.065
    assert all(value >= 500 for value in stats["head_only_changed_pixels"].values())
    assert stats["semantic_displacements"]["horizontal_nose_min"] >= 3.0
    assert stats["semantic_displacements"]["nose_minus_neck_average"] >= 1.0
    assert stats["mesh"]["signed_source_area_max"] < 0.0
    assert stats["mesh"]["orientation_sign_min"] == -1
    assert stats["mesh"]["orientation_sign_max"] == -1
    assert stats["semantic_displacements"]["cardinal_displacement_min"] >= 0.0
    assert stats["semantic_displacements"]["cardinal_displacement_max"] >= 3.0
    assert all(0.80 <= item["ratio"] <= 1.15 for item in stats["eye_crop_find_edges"].values())
    assert stats["constants"]["rendered_eye_anchor_limits"] == {
        "horizontal": 8.0,
        "vertical": 5.5,
    }
    assert stats["total_rendered_eye_anchor_travel"]["horizontal_abs_max"] <= 8.0
    assert stats["total_rendered_eye_anchor_travel"]["vertical_abs_max"] <= 5.5
    containment = stats["containment"]
    assert containment["outside_roi_changed_pixels_max"] == 0
    assert containment["outside_dynamic_support_changed_pixels_max"] == 0
    assert containment["protected_right_strip_changed_pixels_max"] == 0
    assert containment["protected_lower_band_changed_pixels_max"] == 0
    assert containment["transparent_rgb_violations_max"] == 0
    assert 0.97 <= containment["alpha_positive_ratio_min"] <= containment["alpha_positive_ratio_max"] <= 1.03
    assert 0.80 <= containment["semitransparent_ratio_min"] <= containment["semitransparent_ratio_max"] <= 1.25
    assert containment["canonical_enclosed_transparent_holes"] == stats["constants"]["canonical_enclosed_hole_baselines"]
    rendered_holes = containment["rendered_enclosed_transparent_holes_max"]
    assert set(rendered_holes) == {"four_connectivity", "eight_connectivity"}
    assert rendered_holes["eight_connectivity"]["significant_hole_count"] == 0
    assert stats["final_center"]["frame_indices"] == list(range(228, 240))
    assert stats["final_center"]["changed_pixels"] == 0
    assert stats["synthetic_premultiplied_edge_oracle"]["passed"] is True
    assert stats["scope"] == {
        "runtime_assets_unchanged": True,
        "directional_runtime_assets_created": False,
        "qa_only": True,
        "human_fringe_gate_backgrounds": ["light", "dark", "gray", "checker"],
    }
    assert "stats.json" not in stats["outputs"]
    assert set(stats["outputs"]) == module.OUTPUT_FILENAMES - {"stats.json"}
    assert all(stats["outputs"][name] == _sha256(output / name) for name in stats["outputs"])
    difference = Image.open(output / "center-difference.png").convert("RGBA")
    assert difference.getbbox(alpha_only=False) is None


def test_gif_timing_palette_and_same_source_schedule(preview: tuple[Path, dict[str, object]]) -> None:
    module = _module()
    output, stats = preview
    normal, normal_durations, normal_loop = module._decode_gif(output / "head-neck-follow.gif")
    slow, slow_durations, slow_loop = module._decode_gif(output / "head-neck-follow-4x.gif")
    overlay, overlay_durations, overlay_loop = module._decode_gif(output / "landmark-overlay.gif")
    assert normal_loop == slow_loop == overlay_loop == 0
    assert sum(normal_durations) == sum(overlay_durations) == 8000
    assert sum(slow_durations) == 32000
    normal_ticks = module._timeline_ticks(normal, normal_durations)
    slow_ticks = module._timeline_ticks(slow, slow_durations)
    assert len(normal_ticks) == 800 and len(slow_ticks) == 3200
    assert all(slow_ticks[index * 4 : index * 4 + 4] == [tick] * 4 for index, tick in enumerate(normal_ticks))
    assert module._timeline_ticks(overlay, overlay_durations)
    assert stats["gifs"]["normal"]["duration_ms"] == 8000
    assert stats["gifs"]["slow_4x"]["duration_ms"] == 32000
    assert stats["gifs"]["landmark_overlay"]["duration_ms"] == 8000


def test_enclosed_hole_oracle_records_both_connectivities() -> None:
    module = _module()
    canonical = Image.open(CANONICAL).convert("RGBA")
    assert module._enclosed_transparent_components(
        canonical, (0, 160, 320, 432), connectivity=4
    ) == {
        "component_count": 119,
        "pixel_count": 357,
        "largest_component": 21,
        "significant_hole_count": 2,
    }
    assert module._enclosed_transparent_components(
        canonical, (0, 160, 320, 432), connectivity=8
    ) == {
        "component_count": 15,
        "pixel_count": 37,
        "largest_component": 6,
        "significant_hole_count": 0,
    }
    with pytest.raises(ValueError, match="4 or 8"):
        module._enclosed_transparent_components(
            canonical, (0, 160, 320, 432), connectivity=6
        )

    diagonal = Image.new("RGBA", (5, 5), (255, 255, 255, 255))
    for point in ((0, 0), (1, 1), (3, 1), (3, 2)):
        diagonal.putpixel(point, (0, 0, 0, 0))
    assert module._enclosed_transparent_components(
        diagonal, (0, 0, 5, 5), connectivity=4
    ) == {
        "component_count": 2,
        "pixel_count": 3,
        "largest_component": 2,
        "significant_hole_count": 0,
    }
    assert module._enclosed_transparent_components(
        diagonal, (0, 0, 5, 5), connectivity=8
    ) == {
        "component_count": 1,
        "pixel_count": 2,
        "largest_component": 2,
        "significant_hole_count": 0,
    }

    threshold = Image.new("RGBA", (6, 6), (255, 255, 255, 255))
    for point_y in range(1, 5):
        for point_x in range(1, 5):
            threshold.putpixel((point_x, point_y), (0, 0, 0, 0))
    assert module._enclosed_transparent_components(
        threshold, (0, 0, 6, 6), connectivity=8
    )["significant_hole_count"] == 1


def test_build_is_byte_deterministic_and_preserves_inputs_and_runtime(
    tmp_path: Path, preview: tuple[Path, dict[str, object]]
) -> None:
    module = _module()
    first, _stats = preview
    input_before = _input_hashes()
    runtime_before = {
        path.relative_to(RUNTIME_ASSETS): _sha256(path)
        for path in RUNTIME_ASSETS.rglob("*")
        if path.is_file()
    } if RUNTIME_ASSETS.exists() else {}
    second = tmp_path / "second"
    module.build_preview(EYE_ASSETS, CANONICAL, second)
    assert _input_hashes() == input_before
    runtime_after = {
        path.relative_to(RUNTIME_ASSETS): _sha256(path)
        for path in RUNTIME_ASSETS.rglob("*")
        if path.is_file()
    } if RUNTIME_ASSETS.exists() else {}
    assert runtime_after == runtime_before
    for filename in module.OUTPUT_FILENAMES:
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
    assert not any(
        any(
            direction in path.stem.lower().replace("-", " ").replace("_", " ").split()
            for direction in ("left", "right", "up", "down")
        )
        for path in second.iterdir()
        if path.suffix.lower() == ".png"
    )


def test_snapshot_reads_each_required_input_once_before_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, preview: tuple[Path, dict[str, object]]
) -> None:
    module = _module()
    first, _stats = preview
    assets = tmp_path / "assets"
    shutil.copytree(EYE_ASSETS, assets)
    canonical = tmp_path / "canonical-idle.png"
    shutil.copy2(CANONICAL, canonical)
    paths = {
        canonical,
        assets / "authoring.json",
        *(assets / filename for filename in module.EYE_OUTPUTS),
    }
    counts = {path: 0 for path in paths}
    target = assets / "underlay.png"
    real_read_bytes = Path.read_bytes
    real_write_bytes = Path.write_bytes

    def read_then_mutate(path: Path) -> bytes:
        data = real_read_bytes(path)
        if path in counts:
            counts[path] += 1
        if path == target and counts[path] == 1:
            real_write_bytes(path, b"mutated after snapshot")
        return data

    monkeypatch.setattr(Path, "read_bytes", read_then_mutate)
    output = tmp_path / "snapshot-output"
    module.build_preview(assets, canonical, output)
    assert counts == {path: 1 for path in paths}
    for filename in module.OUTPUT_FILENAMES:
        assert (output / filename).read_bytes() == (first / filename).read_bytes()


def test_static_path_preflight_rejects_overlap_files_and_symlinks(tmp_path: Path) -> None:
    module = _module()
    file_output = tmp_path / "output-file"
    file_output.write_bytes(b"not a directory")
    cases = [EYE_ASSETS, EYE_ASSETS / "nested", CANONICAL.parent, file_output]
    symlink_parent = tmp_path / "symlink-parent"
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    try:
        symlink_parent.symlink_to(real_parent, target_is_directory=True)
    except OSError:
        pass
    else:
        cases.append(symlink_parent / "output")
    for output in cases:
        with pytest.raises(ValueError, match="output directory"):
            module._validate_paths(EYE_ASSETS, CANONICAL, output)

    copied_assets = tmp_path / "copied-assets"
    shutil.copytree(EYE_ASSETS, copied_assets)
    canonical_link = tmp_path / "canonical-link.png"
    try:
        canonical_link.symlink_to(CANONICAL)
    except OSError:
        return
    with pytest.raises(ValueError, match="required input"):
        module._validate_paths(copied_assets, canonical_link, tmp_path / "safe-output")


def test_static_path_preflight_rejects_runtime_tree_and_broken_symlink_components(
    tmp_path: Path,
) -> None:
    module = _module()
    for output in (RUNTIME_ASSETS, RUNTIME_ASSETS / "nested" / "preview"):
        with pytest.raises(ValueError, match="output directory"):
            module._validate_paths(EYE_ASSETS, CANONICAL, output)

    broken = tmp_path / "broken-output"
    try:
        broken.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")
    for output in (broken, broken / "nested-output"):
        with pytest.raises(ValueError, match="symlink traversal"):
            module._validate_paths(EYE_ASSETS, CANONICAL, output)


def test_static_path_preflight_allows_only_canonical_qa_output_inside_project(
    tmp_path: Path,
) -> None:
    module = _module()
    module._validate_paths(EYE_ASSETS, CANONICAL, COMMITTED_OUTPUT)
    module._validate_paths(EYE_ASSETS, CANONICAL, tmp_path / "external-preview")

    for output in (
        ROOT / "src",
        ROOT / ".git",
        ROOT / "assets/keyframes",
        ROOT / "assets/rig/v1/keyframes",
        ROOT / "qa/unapproved-preview",
        COMMITTED_OUTPUT / "nested",
    ):
        with pytest.raises(ValueError, match="output directory"):
            module._validate_paths(EYE_ASSETS, CANONICAL, output)


def test_runtime_integrity_claim_is_derived_from_tree_snapshot(tmp_path: Path) -> None:
    module = _module()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    asset = runtime / "asset.png"
    asset.write_bytes(b"approved")
    before = module._snapshot_tree(runtime)
    assert module._runtime_tree_is_unchanged(runtime, before) is True

    asset.write_bytes(b"mutated")
    assert module._runtime_tree_is_unchanged(runtime, before) is False
    asset.write_bytes(b"approved")
    (runtime / "unexpected.bin").write_bytes(b"new")
    assert module._runtime_tree_is_unchanged(runtime, before) is False

    build_source = inspect.getsource(module.build_preview)
    assert '"runtime_assets_unchanged": True' not in build_source
    assert "_runtime_tree_is_unchanged" in build_source


def test_transaction_rolls_back_and_preserves_backup_if_restore_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    output = tmp_path / "replacement"
    output.mkdir()
    (output / "old.txt").write_bytes(b"original")
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "new.txt").write_bytes(b"new")
    real_replace = os.replace
    calls = 0

    def fail_install(source: str | Path, destination: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected install failure")
        real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_install)
    with pytest.raises(OSError, match="injected"):
        module._replace_output(staging, output)
    assert (output / "old.txt").read_bytes() == b"original"
    assert not list(tmp_path.glob(".replacement.*"))

    staging.mkdir()
    (staging / "new.txt").write_bytes(b"new")
    calls = 0

    def fail_install_and_restore(source: str | Path, destination: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls in (2, 3):
            raise OSError("injected rename failure")
        real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_install_and_restore)
    with pytest.raises(OSError, match="recoverable original remains"):
        module._replace_output(staging, output)
    backups = list(tmp_path.glob(".replacement.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "old.txt").read_bytes() == b"original"
    assert not list(tmp_path.glob(".replacement.staging-*"))

    never_installed = tmp_path / "never-installed"
    fresh_staging = tmp_path / "fresh-staging"
    fresh_staging.mkdir()
    (fresh_staging / "new.txt").write_bytes(b"new")

    def fail_first_install(_source: str | Path, _destination: str | Path) -> None:
        raise OSError("injected first install failure")

    monkeypatch.setattr(module.os, "replace", fail_first_install)
    with pytest.raises(OSError, match="first install"):
        module._replace_output(fresh_staging, never_installed)
    assert not fresh_staging.exists()
    assert not never_installed.exists()


def test_committed_evidence_matches_builder_allowlist() -> None:
    if not COMMITTED_OUTPUT.exists():
        pytest.skip("Task 2 evidence has not been generated yet")
    assert {path.name for path in COMMITTED_OUTPUT.iterdir()} == _module().OUTPUT_FILENAMES

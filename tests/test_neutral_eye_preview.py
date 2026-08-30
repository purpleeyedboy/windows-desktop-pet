from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets/rig/v1/source/eye-neutral-v1"
CANONICAL = ROOT / "assets/rig/v1/source/canonical-idle.png"
COMMITTED_OUTPUT = ROOT / "qa/neutral-eye-v1/preview-v2"
CANONICAL_SHA256 = "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"
MOTION_LIMITS = {"x": 3.0, "y": 2.0}
FRAME_COUNT = 90
DURATIONS = (30, 30, 40) * 30


def _module():
    from tools import build_neutral_eye_preview

    return build_neutral_eye_preview


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _diff_metrics(first: Image.Image, second: Image.Image) -> tuple[int, int]:
    difference = ImageChops.difference(first, second)
    return (
        sum(pixel != (0, 0, 0, 0) for pixel in difference.getdata()),
        max(high for _, high in difference.getextrema()),
    )


def _binary_support(mask: Image.Image) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value > 0 else 0)


def _decode_gif(path: Path) -> tuple[list[Image.Image], list[int], int]:
    with Image.open(path) as decoded:
        frames: list[Image.Image] = []
        durations: list[int] = []
        loop = decoded.info.get("loop")
        try:
            while True:
                frames.append(decoded.convert("RGB").copy())
                durations.append(decoded.info.get("duration", 0))
                decoded.seek(decoded.tell() + 1)
        except EOFError:
            pass
    return frames, durations, loop


def _tick_schedule(frames: list[Image.Image], durations: list[int]) -> list[Image.Image]:
    ticks: list[Image.Image] = []
    for frame, duration in zip(frames, durations, strict=True):
        assert duration % 10 == 0
        ticks.extend([frame] * (duration // 10))
    return ticks


def _fixed_palette_rgb(frame: Image.Image) -> Image.Image:
    matte = Image.new("RGB", frame.size, (31, 33, 36))
    matte.paste(frame.convert("RGBA"), mask=frame.getchannel("A"))
    return matte.convert(
        "P", palette=Image.Palette.WEB, dither=Image.Dither.NONE
    ).convert("RGB")


def _immutable_input_hashes(asset_dir: Path) -> dict[Path, str]:
    return {
        path: _sha256(path)
        for path in [CANONICAL, asset_dir / "authoring.json", *(asset_dir / name for name in (
            "underlay.png",
            "eye-left.png",
            "eye-right.png",
            "eye-left-mask.png",
            "eye-right-mask.png",
        ))]
    }


@pytest.fixture(scope="module")
def preview(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    output = tmp_path_factory.mktemp("neutral-eye-preview") / "out"
    return output, _module().build_preview(ASSET_DIR, CANONICAL, output)


def test_cursor_target_uses_continuous_radial_clamped_elliptical_mapping() -> None:
    module = _module()
    radius = module.VIRTUAL_CURSOR_ACTIVATION_RADIUS
    assert radius > 0.0
    assert math.isfinite(radius)
    assert module.cursor_target(0.0, 0.0, radius) == (0.0, 0.0)
    assert module.cursor_target(radius / 2.0, 0.0, radius) == pytest.approx((1.5, 0.0))
    assert module.cursor_target(0.0, -radius, radius) == pytest.approx((0.0, -2.0))
    assert module.cursor_target(0.0, 2.0 * radius, radius) == pytest.approx((0.0, 2.0))

    dx, dy = 3.0, -4.0
    distance = math.hypot(dx, dy)
    strength = min(distance / radius, 1.0)
    assert module.cursor_target(dx, dy, radius) == pytest.approx(
        (MOTION_LIMITS["x"] * dx / distance * strength, MOTION_LIMITS["y"] * dy / distance * strength)
    )
    first = module.cursor_target(radius * math.cos(0.7), radius * math.sin(0.7), radius)
    second = module.cursor_target(radius * math.cos(0.7001), radius * math.sin(0.7001), radius)
    assert math.hypot(second[0] - first[0], second[1] - first[1]) < 0.001


@pytest.mark.parametrize(
    ("dx", "dy", "expected"),
    [
        (sys.float_info.max, 0.0, (3.0, 0.0)),
        (-sys.float_info.max, 0.0, (-3.0, 0.0)),
        (0.0, sys.float_info.max, (0.0, 2.0)),
        (0.0, -sys.float_info.max, (0.0, -2.0)),
        (sys.float_info.max, sys.float_info.max, (3.0 / math.sqrt(2), 2.0 / math.sqrt(2))),
        (sys.float_info.max, -sys.float_info.max, (3.0 / math.sqrt(2), -2.0 / math.sqrt(2))),
        (-sys.float_info.max, sys.float_info.max, (-3.0 / math.sqrt(2), 2.0 / math.sqrt(2))),
        (-sys.float_info.max, -sys.float_info.max, (-3.0 / math.sqrt(2), -2.0 / math.sqrt(2))),
    ],
)
def test_cursor_target_handles_largest_finite_coordinates_without_overflow(
    dx: float, dy: float, expected: tuple[float, float]
) -> None:
    target = _module().cursor_target(dx, dy, 1.0)

    assert all(math.isfinite(value) for value in target)
    assert abs(target[0]) <= MOTION_LIMITS["x"]
    assert abs(target[1]) <= MOTION_LIMITS["y"]
    for actual, expected_component in zip(target, expected, strict=True):
        if expected_component == 0.0:
            assert actual == 0.0
        else:
            assert actual * expected_component > 0.0
    assert target == pytest.approx(expected)


@pytest.mark.parametrize(
    ("dx", "dy", "radius"),
    [
        (math.nan, 0.0, 1.0),
        (0.0, math.inf, 1.0),
        (0.0, 0.0, math.nan),
        (0.0, 0.0, math.inf),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
    ],
)
def test_cursor_target_rejects_nonfinite_inputs_and_nonpositive_radius(
    dx: float, dy: float, radius: float
) -> None:
    with pytest.raises(ValueError):
        _module().cursor_target(dx, dy, radius)


def test_target_path_and_exponential_snap_contract() -> None:
    module = _module()
    assert len(module.preview_offsets()) == FRAME_COUNT
    assert module.target_for_frame(0) == (0.0, 0.0)
    assert module.target_for_frame(6) == pytest.approx((-3.0, 0.0), abs=1e-15)
    assert module.target_for_frame(20) == pytest.approx((0.0, -2.0), abs=1e-15)
    assert module.target_for_frame(34) == pytest.approx((3.0, 0.0), abs=1e-15)
    assert module.target_for_frame(48) == pytest.approx((0.0, 2.0), abs=1e-15)
    assert module.target_for_frame(62) == pytest.approx((-3.0, 0.0), abs=1e-15)
    assert module.target_for_frame(63) == (0.0, 0.0)
    assert module.target_for_frame(89) == (0.0, 0.0)
    targets = [module.target_for_frame(index) for index in range(6, 63)]
    assert len({(round(x, 12), round(y, 12)) for x, y in targets}) > 16
    for index, target in enumerate(targets):
        angle = math.pi + 2.0 * math.pi * index / 56
        cursor = (
            module.VIRTUAL_CURSOR_ACTIVATION_RADIUS * math.cos(angle),
            module.VIRTUAL_CURSOR_ACTIVATION_RADIUS * math.sin(angle),
        )
        assert target == pytest.approx(
            module.cursor_target(*cursor, module.VIRTUAL_CURSOR_ACTIVATION_RADIUS), abs=1e-15
        )
    with pytest.raises(ValueError):
        module.target_for_frame(-1)
    with pytest.raises(ValueError):
        module.target_for_frame(FRAME_COUNT)

    alpha = 1 - math.exp(-(1 / 30) / 0.060)
    state = (0.0, 0.0)
    for index, offset in enumerate(module.preview_offsets()):
        if index == 84:
            state = (0.0, 0.0)
        elif index < 84:
            target = module.target_for_frame(index)
            state = tuple(
                current + alpha * (requested - current)
                for current, requested in zip(state, target, strict=True)
            )
        assert offset == pytest.approx(state, abs=1e-15)
        assert abs(offset[0]) <= MOTION_LIMITS["x"]
        assert abs(offset[1]) <= MOTION_LIMITS["y"]
    assert module.preview_offsets()[83] == pytest.approx((0.0, 0.0), abs=5e-5)
    assert module.preview_offsets()[84:] == ((0.0, 0.0),) * 6


def test_preview_rejects_tampered_immutable_input_before_writing(tmp_path: Path) -> None:
    module = _module()
    tampered_assets = tmp_path / "assets"
    shutil.copytree(ASSET_DIR, tampered_assets)
    mask = Image.open(tampered_assets / "eye-left-mask.png").convert("L")
    mask.putpixel((82, 351), 0)
    mask.save(tampered_assets / "eye-left-mask.png")
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="hash"):
        module.build_preview(tampered_assets, CANONICAL, output)
    assert not output.exists()


def test_preview_rejects_overlapping_or_non_directory_output_before_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    copied_assets = tmp_path / "copied-assets"
    shutil.copytree(ASSET_DIR, copied_assets)
    existing_file = tmp_path / "existing-file"
    existing_file.write_bytes(b"not a directory")
    symlink_output = tmp_path / "directory-link"
    asset_alias = tmp_path / "asset-alias"
    symlink_target = tmp_path / "directory-target"
    symlink_target.mkdir()
    cases: list[tuple[Path, Path]] = [
        (copied_assets, copied_assets),
        (copied_assets, copied_assets / "nested-preview"),
        (ASSET_DIR, CANONICAL.parent),
        (ASSET_DIR, existing_file),
    ]
    try:
        symlink_output.symlink_to(symlink_target, target_is_directory=True)
        asset_alias.symlink_to(copied_assets, target_is_directory=True)
    except OSError:
        pass
    else:
        cases.append((ASSET_DIR, symlink_output))
        cases.append((copied_assets, asset_alias))

    def transaction_must_not_start(*_args: object) -> None:
        raise AssertionError("output transaction must not start for rejected paths")

    canonical = Image.open(CANONICAL).convert("RGBA")
    monkeypatch.setattr(module, "compose_pose", lambda *_args: canonical.copy())
    monkeypatch.setattr(module, "_replace_output", transaction_must_not_start)
    for assets, output in cases:
        before = _immutable_input_hashes(assets)
        with pytest.raises(ValueError, match="output directory"):
            module.build_preview(assets, CANONICAL, output)
        assert _immutable_input_hashes(assets) == before


def test_preview_has_shared_offsets_containment_and_final_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    calls: list[tuple[float, float]] = []
    canonical = Image.open(CANONICAL).convert("RGBA")

    def recording_compose(asset_dir: Path, eye_x: float, eye_y: float) -> Image.Image:
        calls.append((eye_x, eye_y))
        return canonical.copy()

    monkeypatch.setattr(module, "compose_pose", recording_compose)
    stats = module.build_preview(ASSET_DIR, CANONICAL, tmp_path / "out")
    assert calls == list(module.preview_offsets())
    assert stats["frames"] == [
        {
            "frame_index": index,
            "requested_target": list(module.target_for_frame(index)),
            "smoothed_offset": list(offset),
        }
        for index, offset in enumerate(module.preview_offsets())
    ]


def test_preview_has_containment_and_final_canonical(preview: tuple[Path, dict]) -> None:
    _output, stats = preview
    assert stats["containment"]["outside_support_changed_pixels_max"] == 0
    assert stats["containment"]["alpha_changed_pixels_max"] == 0
    assert stats["containment"]["ring_new_near_black_pixels_max"] == 0
    assert stats["final_center"] == {
        "changed_pixels": 0,
        "maximum_channel_delta": 0,
        "frame_indices": [84, 85, 86, 87, 88, 89],
    }


def test_containment_rejects_rgb_only_change_outside_support() -> None:
    module = _module()
    canonical, _authoring, images, _hashes = module._validate_inputs(ASSET_DIR, CANONICAL)
    support, ring = module._binary_support(images)
    changed = canonical.copy()
    outside_point = next(
        (x, y)
        for y in range(canonical.height)
        for x in range(canonical.width)
        if support.getpixel((x, y)) == 0
    )
    red, green, blue, alpha = changed.getpixel(outside_point)
    changed.putpixel(outside_point, ((red + 1) % 256, green, blue, alpha))

    with pytest.raises(ValueError, match="containment validation failed"):
        module._validate_rendered_frames([changed] * FRAME_COUNT, canonical, support, ring)


def test_final_center_rejects_rgb_only_change_inside_support() -> None:
    module = _module()
    canonical, _authoring, images, _hashes = module._validate_inputs(ASSET_DIR, CANONICAL)
    support, ring = module._binary_support(images)
    changed = canonical.copy()
    inside_point = next(
        (x, y)
        for y in range(canonical.height)
        for x in range(canonical.width)
        if support.getpixel((x, y)) > 0
    )
    red, green, blue, alpha = changed.getpixel(inside_point)
    changed.putpixel(inside_point, ((red + 1) % 256, green, blue, alpha))
    frames = [canonical.copy() for _ in range(FRAME_COUNT)]
    frames[84] = changed

    with pytest.raises(ValueError, match="final six frames"):
        module._validate_rendered_frames(frames, canonical, support, ring)


def test_gif_timeline_fixed_palette_and_statistics(preview: tuple[Path, dict]) -> None:
    module = _module()
    output, stats = preview
    decoded, decoded_durations, loop = _decode_gif(output / "eye-follow.gif")
    assert loop == 0
    assert sum(decoded_durations) == 3000
    assert sum(DURATIONS) == 3000
    expected = [_fixed_palette_rgb(module.compose_pose(ASSET_DIR, *offset)) for offset in module.preview_offsets()]
    expected_ticks = _tick_schedule(expected, list(DURATIONS))
    decoded_ticks = _tick_schedule(decoded, decoded_durations)
    assert len(expected_ticks) == len(decoded_ticks) == 300
    assert all(left.tobytes() == right.tobytes() for left, right in zip(expected_ticks, decoded_ticks, strict=True))

    recorded = json.loads((output / "stats.json").read_text(encoding="utf-8"))
    assert recorded == stats
    assert recorded["constants"] == {
        "frame_count": 90,
        "fps": 30,
        "dt_seconds": 1 / 30,
        "time_constant_seconds": 0.060,
        "alpha": 1 - math.exp(-(1 / 30) / 0.060),
        "motion_limits": MOTION_LIMITS,
        "cursor_mapping_formula": "radial-clamped-elliptical-v1",
        "virtual_cursor_activation_radius": module.VIRTUAL_CURSOR_ACTIVATION_RADIUS,
        "matte_rgb": [31, 33, 36],
        "palette": "Pillow WEB dither=NONE",
    }
    assert len(recorded["frames"]) == FRAME_COUNT
    assert recorded["source_durations_ms"] == list(DURATIONS)
    assert recorded["gif"]["decoded_durations_ms"] == decoded_durations
    assert recorded["gif"]["decoded_frame_count"] == len(decoded)
    assert recorded["gif"]["loop"] == 0
    assert recorded["gif"]["sha256"] == _sha256(output / "eye-follow.gif")
    assert recorded["inputs"]["canonical"]["sha256"] == CANONICAL_SHA256
    assert "stats.json" not in recorded.get("hashes", {})


def test_existing_output_replaced_successfully_without_temporary_siblings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    output = tmp_path / "replacement"
    output.mkdir()
    (output / "sentinel.txt").write_bytes(b"replace me")
    canonical = Image.open(CANONICAL).convert("RGBA")
    monkeypatch.setattr(module, "compose_pose", lambda *_args: canonical.copy())

    stats = module.build_preview(ASSET_DIR, CANONICAL, output)

    assert not (output / "sentinel.txt").exists()
    assert (output / "eye-follow.gif").is_file()
    assert (output / "stats.json").is_file()
    assert stats["gif"]["sha256"] == _sha256(output / "eye-follow.gif")
    assert json.loads((output / "stats.json").read_text(encoding="utf-8")) == stats
    assert not list(tmp_path.glob(".replacement.staging-*"))
    assert not list(tmp_path.glob(".replacement.backup-*"))


def test_double_build_committed_outputs_and_transactional_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, preview: tuple[Path, dict]
) -> None:
    module = _module()
    first, _stats = preview
    second = tmp_path / "second"
    module.build_preview(ASSET_DIR, CANONICAL, second)
    for filename in ("eye-follow.gif", "stats.json"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
        assert (first / filename).read_bytes() == (COMMITTED_OUTPUT / filename).read_bytes()

    output = tmp_path / "replacement"
    output.mkdir()
    (output / "old.txt").write_bytes(b"original")
    canonical = Image.open(CANONICAL).convert("RGBA")
    monkeypatch.setattr(module, "compose_pose", lambda *_args: canonical.copy())
    real_replace = os.replace
    rename_calls = 0

    def fail_second_rename(source: str | Path, destination: str | Path) -> None:
        nonlocal rename_calls
        rename_calls += 1
        if rename_calls == 2:
            raise OSError("injected between-rename failure")
        real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_second_rename)
    with pytest.raises(OSError, match="injected"):
        module.build_preview(ASSET_DIR, CANONICAL, output)
    assert (output / "old.txt").read_bytes() == b"original"
    assert not list(tmp_path.glob(".replacement.*"))


def test_transaction_keeps_backup_when_restore_rename_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    output = tmp_path / "replacement"
    output.mkdir()
    (output / "old.txt").write_bytes(b"original")
    canonical = Image.open(CANONICAL).convert("RGBA")
    monkeypatch.setattr(module, "compose_pose", lambda *_args: canonical.copy())
    real_replace = os.replace
    rename_calls = 0

    def fail_install_and_restore(source: str | Path, destination: str | Path) -> None:
        nonlocal rename_calls
        rename_calls += 1
        if rename_calls in (2, 3):
            raise OSError("injected rename failure")
        real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_install_and_restore)
    with pytest.raises(OSError, match=r"\.replacement\.backup-"):
        module.build_preview(ASSET_DIR, CANONICAL, output)

    backups = list(tmp_path.glob(".replacement.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "old.txt").read_bytes() == b"original"
    assert not list(tmp_path.glob(".replacement.staging-*"))

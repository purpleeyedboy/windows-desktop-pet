from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from tools import build_approved_runtime_assets as assembler


ROOT = Path(__file__).resolve().parents[1]
APPROVED_DIR = ROOT / "assets/rig/v1/source/approved"
RUNTIME_SOURCE_DIR = ROOT / "assets/rig/v1/source/eye-neutral-v1"
APPROVED_HEAD = APPROVED_DIR / "猫头-精准抠图.png"
APPROVED_BODY = APPROVED_DIR / "猫身-原像素保留-仅补头部缺口.png"
PREVIOUS_UNDERLAY = (
    ROOT / "tests/fixtures/approved_runtime_assets/previous-underlay.png"
)
APPROVED_HEAD_SHA256 = (
    "6e57c1be03db1a97a484576f6f88be8639d8f01bbfe5b0d792c68e3d985864e6"
)
APPROVED_BODY_SHA256 = (
    "527eaad70a84c611f0839bc3898b5c00f41df383c191771c7e07a1af588e5ce8"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _copy_inputs(tmp_path: Path) -> tuple[Path, Path]:
    approved_dir = tmp_path / "approved"
    runtime_source_dir = tmp_path / "eye-neutral-v1"
    shutil.copytree(APPROVED_DIR, approved_dir)
    shutil.copytree(RUNTIME_SOURCE_DIR, runtime_source_dir)
    return approved_dir, runtime_source_dir


def test_approved_sources_have_exact_bytes_dimensions_and_mode() -> None:
    assert _sha256(APPROVED_HEAD.read_bytes()) == APPROVED_HEAD_SHA256
    assert _sha256(APPROVED_BODY.read_bytes()) == APPROVED_BODY_SHA256
    with Image.open(APPROVED_HEAD) as head:
        assert (head.mode, head.size) == ("RGBA", (230, 241))
    with Image.open(APPROVED_BODY) as body:
        assert (body.mode, body.size) == ("RGBA", (512, 768))


def test_build_is_deterministic_and_preserves_sources_and_eye_apertures(
    tmp_path: Path,
) -> None:
    approved_dir, runtime_source_dir = _copy_inputs(tmp_path)
    assert _sha256(PREVIOUS_UNDERLAY.read_bytes()) == (
        "28bc087f2d45a9e2dc2774c96a0b853b55b65795726d0eecb374d90310c5aac9"
    )
    shutil.copyfile(PREVIOUS_UNDERLAY, runtime_source_dir / "underlay.png")
    head_path = approved_dir / APPROVED_HEAD.name
    body_path = approved_dir / APPROVED_BODY.name
    source_bytes_before = {
        head_path.name: head_path.read_bytes(),
        body_path.name: body_path.read_bytes(),
    }
    eye_bytes_before = {
        path.name: path.read_bytes()
        for path in runtime_source_dir.glob("eye-*.png")
    }
    previous_underlay = Image.open(runtime_source_dir / "underlay.png").convert("RGBA")
    left_mask = Image.open(runtime_source_dir / "eye-left-mask.png").convert("L")
    right_mask = Image.open(runtime_source_dir / "eye-right-mask.png").convert("L")
    eye_union = ImageChops.lighter(left_mask, right_mask)

    expected_composite = Image.open(body_path).convert("RGBA")
    expected_composite.alpha_composite(
        Image.open(head_path).convert("RGBA"), assembler.HEAD_OFFSET
    )

    first_hashes = assembler.build(approved_dir, runtime_source_dir)
    first_underlay_bytes = (runtime_source_dir / "underlay.png").read_bytes()
    first_backplate_bytes = (runtime_source_dir / "body-backplate.png").read_bytes()
    second_hashes = assembler.build(approved_dir, runtime_source_dir)

    assert assembler.HEAD_OFFSET == (24, 204)
    assert assembler.APPROVED_HEAD_SHA256 == APPROVED_HEAD_SHA256
    assert assembler.APPROVED_BODY_SHA256 == APPROVED_BODY_SHA256
    assert first_hashes == second_hashes == {
        "underlay.png": _sha256(first_underlay_bytes),
        "body-backplate.png": APPROVED_BODY_SHA256,
    }
    assert (
        runtime_source_dir / "underlay.png"
    ).read_bytes() == first_underlay_bytes
    assert (
        runtime_source_dir / "body-backplate.png"
    ).read_bytes() == first_backplate_bytes
    assert first_backplate_bytes == source_bytes_before[body_path.name]

    actual_underlay = Image.open(runtime_source_dir / "underlay.png").convert("RGBA")
    outside_eye_union = eye_union.point(
        lambda value: 255 if value == 0 else 0
    )
    outside_difference = Image.composite(
        ImageChops.difference(actual_underlay, expected_composite),
        Image.new("RGBA", expected_composite.size),
        outside_eye_union,
    )
    assert outside_difference.getbbox(alpha_only=False) is None

    fully_masked = eye_union.point(lambda value: 255 if value == 255 else 0)
    masked_difference = Image.composite(
        ImageChops.difference(actual_underlay, previous_underlay),
        Image.new("RGBA", previous_underlay.size),
        fully_masked,
    )
    assert masked_difference.getbbox(alpha_only=False) is None
    assert {
        head_path.name: head_path.read_bytes(),
        body_path.name: body_path.read_bytes(),
    } == source_bytes_before
    assert {
        path.name: path.read_bytes()
        for path in runtime_source_dir.glob("eye-*.png")
    } == eye_bytes_before


def test_build_rejects_a_byte_changed_eye_mask(tmp_path: Path) -> None:
    approved_dir, runtime_source_dir = _copy_inputs(tmp_path)
    mask_path = runtime_source_dir / "eye-left-mask.png"
    mask = Image.open(mask_path).convert("L")
    mask.putpixel((0, 0), 255)
    mask.save(mask_path)

    with pytest.raises(ValueError, match="eye-left-mask.png SHA mismatch"):
        assembler.build(approved_dir, runtime_source_dir)


def test_second_replace_failure_restores_both_previous_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    approved_dir, runtime_source_dir = _copy_inputs(tmp_path)
    shutil.copyfile(PREVIOUS_UNDERLAY, runtime_source_dir / "underlay.png")
    output_paths = (
        runtime_source_dir / "underlay.png",
        runtime_source_dir / "body-backplate.png",
    )
    previous_outputs = {path: path.read_bytes() for path in output_paths}
    real_replace = assembler.os.replace
    replace_calls = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls == 2:
            raise OSError("simulated second replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(assembler.os, "replace", fail_second_replace)

    with pytest.raises(OSError, match="simulated second replace failure"):
        assembler.build(approved_dir, runtime_source_dir)

    assert replace_calls == 3
    assert {path: path.read_bytes() for path in output_paths} == previous_outputs

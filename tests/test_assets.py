from pathlib import Path

import pytest
from PIL import Image

from desktop_pet import assets as assets_module
from desktop_pet.assets import (
    find_frame_paths,
    load_frames,
    validate_frame_file,
)


def make_action(action: Path, count: int) -> None:
    action.mkdir(parents=True)
    for index in range(count):
        image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
        image.putpixel((1, 1), (1, 2, 3, 255))
        image.save(action / f"{index:02d}.png")


def test_find_frame_paths_requires_exact_six(tmp_path: Path):
    make_action(tmp_path / "jump", count=5)
    with pytest.raises(RuntimeError, match="6"):
        find_frame_paths(tmp_path, "jump")


def test_validate_frame_file_requires_rgba_canvas(tmp_path: Path):
    path = tmp_path / "bad.png"
    Image.new("RGB", (256, 256), "white").save(path)
    with pytest.raises(RuntimeError, match="512x768 RGBA"):
        validate_frame_file(path)


def test_load_frames_returns_three_six_frame_actions(tmp_path: Path):
    for action in ("jump", "squash", "shake"):
        make_action(tmp_path / action, count=6)

    frames = load_frames(tmp_path)
    assert set(frames) == {"jump", "squash", "shake"}
    assert {len(action_frames) for action_frames in frames.values()} == {6}
    assert all(frame.size == (512, 768) for action in frames.values() for frame in action)


def test_runtime_frame_root_uses_archived_clean_keyframes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_asset_path(*parts: str) -> Path:
        calls.append(parts)
        return tmp_path

    monkeypatch.setattr("desktop_pet.assets.asset_path", fake_asset_path)

    assert assets_module.runtime_frame_root() == tmp_path
    assert calls == [("assets", "keyframes")]


def test_neutral_eye_source_probe_root_is_explicitly_source_checkout_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        assets_module,
        "asset_path",
        lambda *_parts: (_ for _ in ()).throw(
            AssertionError("source probe must not use bundled asset resolution")
        ),
    )

    root = assets_module.neutral_eye_source_probe_root()

    assert root == (
        Path(assets_module.__file__).resolve().parents[2]
        / "assets"
        / "rig"
        / "v1"
        / "source"
        / "eye-neutral-v1"
    )
    assert "source-checkout-only" in (
        assets_module.neutral_eye_source_probe_root.__doc__ or ""
    ).lower()


def test_neutral_eye_runtime_root_uses_bundled_asset_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_asset_path(*parts: str) -> Path:
        calls.append(parts)
        return tmp_path

    monkeypatch.setattr(assets_module, "asset_path", fake_asset_path)

    assert assets_module.neutral_eye_runtime_root() == tmp_path
    assert calls == [("assets", "rig", "v1", "runtime", "eye-neutral-v1")]


def test_load_neutral_eye_compositor_passes_explicit_root_directly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sentinel = object()
    calls: list[Path] = []

    monkeypatch.setattr(
        assets_module.NeutralEyeCompositor,
        "load",
        lambda path: calls.append(path) or sentinel,
    )

    assert assets_module.load_neutral_eye_compositor(tmp_path) is sentinel
    assert calls == [tmp_path]


def test_load_neutral_eye_compositor_uses_runtime_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    source_root = tmp_path / "source"
    calls: list[Path] = []

    monkeypatch.setattr(assets_module, "neutral_eye_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(
        assets_module, "neutral_eye_source_probe_root", lambda: source_root
    )
    monkeypatch.setattr(
        assets_module.NeutralEyeCompositor, "load", lambda path: calls.append(path)
    )

    assets_module.load_neutral_eye_compositor()

    assert calls == [runtime_root]


def test_load_neutral_eye_compositor_falls_back_to_source_in_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime_root = tmp_path / "missing-runtime"
    source_root = tmp_path / "source"
    calls: list[Path] = []

    monkeypatch.delattr(assets_module.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(assets_module, "neutral_eye_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(
        assets_module, "neutral_eye_source_probe_root", lambda: source_root
    )
    monkeypatch.setattr(
        assets_module.NeutralEyeCompositor, "load", lambda path: calls.append(path)
    )

    assets_module.load_neutral_eye_compositor()

    assert calls == [source_root]


def test_load_neutral_eye_compositor_uses_runtime_in_frozen_bundle_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime_root = tmp_path / "missing-runtime"
    source_root = tmp_path / "source"
    calls: list[Path] = []

    monkeypatch.setattr(assets_module.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(assets_module, "neutral_eye_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(
        assets_module, "neutral_eye_source_probe_root", lambda: source_root
    )
    monkeypatch.setattr(
        assets_module.NeutralEyeCompositor, "load", lambda path: calls.append(path)
    )

    assets_module.load_neutral_eye_compositor()

    assert calls == [runtime_root]


def test_load_neutral_eye_source_probe_uses_validated_compositor_loader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sentinel = object()
    calls: list[Path] = []

    def load(path: Path):
        calls.append(path)
        return sentinel

    monkeypatch.setattr(
        assets_module.NeutralEyeCompositor,
        "load",
        load,
    )

    assert assets_module.load_neutral_eye_source_probe(tmp_path) is sentinel
    assert calls == [tmp_path]
    assert "source-checkout-only" in (
        assets_module.load_neutral_eye_source_probe.__doc__ or ""
    ).lower()


def test_load_head_neck_compositor_wraps_the_selected_neutral_eye_compositor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    neutral = object()
    wrapped = object()
    calls: list[object] = []
    monkeypatch.setattr(
        assets_module,
        "load_neutral_eye_compositor",
        lambda: neutral,
    )
    monkeypatch.setattr(
        assets_module,
        "ContinuousHeadNeckCompositor",
        lambda base: calls.append(base) or wrapped,
    )

    assert assets_module.load_head_neck_compositor() is wrapped
    assert calls == [neutral]

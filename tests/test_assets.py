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

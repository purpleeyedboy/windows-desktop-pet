from pathlib import Path

import pytest
from PIL import Image

from desktop_pet.assets import find_frame_paths, load_frames, validate_frame_file


def make_action(action: Path, count: int) -> None:
    action.mkdir(parents=True)
    for index in range(count):
        image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
        image.putpixel((1, 1), (1, 2, 3, 255))
        image.save(action / f"{index:02d}.png")


def test_find_frame_paths_requires_exact_thirty(tmp_path: Path):
    make_action(tmp_path / "jump", count=29)
    with pytest.raises(RuntimeError, match="30"):
        find_frame_paths(tmp_path, "jump")


def test_validate_frame_file_requires_rgba_canvas(tmp_path: Path):
    path = tmp_path / "bad.png"
    Image.new("RGB", (256, 256), "white").save(path)
    with pytest.raises(RuntimeError, match="512x768 RGBA"):
        validate_frame_file(path)


def test_load_frames_returns_three_thirty_frame_actions(tmp_path: Path):
    for action in ("jump", "squash", "shake"):
        make_action(tmp_path / action, count=30)

    frames = load_frames(tmp_path)
    assert set(frames) == {"jump", "squash", "shake"}
    assert {len(action_frames) for action_frames in frames.values()} == {30}
    assert all(frame.size == (512, 768) for action in frames.values() for frame in action)

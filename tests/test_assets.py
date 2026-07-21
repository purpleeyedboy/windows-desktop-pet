from pathlib import Path

import pytest
from PIL import Image

from desktop_pet.assets import find_frame_paths, load_frames, validate_frame_file


def test_find_frame_paths_requires_exact_six(tmp_path: Path):
    action = tmp_path / "jump"
    action.mkdir()
    for index in range(5):
        Image.new("RGBA", (512, 768), (1, 2, 3, 255)).save(action / f"{index:02d}.png")
    with pytest.raises(RuntimeError, match="jump.*6"):
        find_frame_paths(tmp_path, "jump")


def test_validate_frame_file_requires_rgba_canvas(tmp_path: Path):
    path = tmp_path / "bad.png"
    Image.new("RGB", (256, 256), "white").save(path)
    with pytest.raises(RuntimeError, match="512x768 RGBA"):
        validate_frame_file(path)


def test_load_frames_returns_three_six_frame_actions():
    frames = load_frames()
    assert set(frames) == {"jump", "squash", "shake"}
    assert {len(action_frames) for action_frames in frames.values()} == {6}
    assert all(frame.size == (512, 768) for action in frames.values() for frame in action)

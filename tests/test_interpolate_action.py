from pathlib import Path

import pytest
from PIL import Image

from tools.interpolate_action import (
    FINAL_POSITIONS,
    INTERMEDIATE_COUNTS,
    build_action,
    interpolate_pair,
)


FRAME_SIZE = (512, 768)


def moving_square(left: int, *, color: tuple[int, int, int] = (235, 120, 40)) -> Image.Image:
    image = Image.new("RGBA", FRAME_SIZE, (17, 31, 47, 0))
    for x in range(left, left + 48):
        for y in range(320, 384):
            image.putpixel((x, y), (*color, 255))
    return image


def alpha_centroid(image: Image.Image) -> tuple[float, float]:
    alpha = image.getchannel("A")
    total = sum(alpha.getdata())
    x_sum = 0
    y_sum = 0
    for y in range(alpha.height):
        for x in range(alpha.width):
            value = alpha.getpixel((x, y))
            x_sum += x * value
            y_sum += y * value
    return x_sum / total, y_sum / total


def make_keyframes(root: Path) -> Path:
    root.mkdir(parents=True)
    for index, left in enumerate((80, 104, 132, 164, 200, 240)):
        moving_square(left, color=(220, 100 + index * 10, 45)).save(
            root / f"{index:02d}.png"
        )
    return root


def test_interpolate_pair_moves_monotonically_and_cleans_hidden_rgb():
    frames = interpolate_pair(moving_square(80), moving_square(160), 5)

    assert len(frames) == 5
    centers = [alpha_centroid(frame)[0] for frame in frames]
    assert centers == sorted(centers)
    assert centers[0] > alpha_centroid(moving_square(80))[0]
    assert centers[-1] < alpha_centroid(moving_square(160))[0]
    assert any(
        0 < alpha < 255
        for frame in frames
        for alpha in frame.getchannel("A").getdata()
    )
    for frame in frames:
        assert frame.mode == "RGBA"
        assert frame.size == FRAME_SIZE
        assert all(
            (red, green, blue) == (0, 0, 0)
            for red, green, blue, alpha in frame.getdata()
            if alpha == 0
        )


def test_interpolate_pair_requires_runtime_canvas():
    with pytest.raises(ValueError, match="512x768"):
        interpolate_pair(Image.new("RGBA", (32, 32)), Image.new("RGBA", (32, 32)), 1)


def test_build_action_preserves_keyframe_bytes(tmp_path: Path):
    keys = make_keyframes(tmp_path / "keys")
    output = tmp_path / "out"

    report = build_action(keys, output, tmp_path / "qa", "jump")

    assert INTERMEDIATE_COUNTS == (5, 5, 4, 5, 5)
    assert FINAL_POSITIONS == (0, 6, 12, 17, 23, 29)
    assert [path.name for path in sorted(output.glob("*.png"))] == [
        f"{index:02d}.png" for index in range(30)
    ]
    for source, final in enumerate(FINAL_POSITIONS):
        assert (output / f"{final:02d}.png").read_bytes() == (
            keys / f"{source:02d}.png"
        ).read_bytes()
    assert report["action"] == "jump"
    assert report["frame_count"] == 30
    assert set(report["artifacts"]) == {
        "contact-sheet.png",
        "normal.gif",
        "slow.gif",
        "stats.json",
    }

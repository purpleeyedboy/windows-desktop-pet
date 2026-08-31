import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tools.interpolate_action import (
    FINAL_POSITIONS,
    INTERMEDIATE_COUNTS,
    build_action,
    interpolate_pair,
    render_between,
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


def relative_alias(path: Path) -> Path:
    target = path.resolve()
    try:
        return Path(os.path.relpath(target, Path.cwd()))
    except ValueError:
        return target


def test_relative_alias_uses_absolute_target_when_paths_have_different_drives(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "target"

    def different_drive(*_args: object) -> str:
        raise ValueError("path is on mount 'C:', start on mount 'D:'")

    monkeypatch.setattr(os.path, "relpath", different_drive)

    assert relative_alias(target) == target.resolve()


def tree_snapshot(path: Path) -> dict[str, bytes] | None:
    root = path.resolve()
    if not root.exists():
        return None
    return {
        candidate.relative_to(root).as_posix(): candidate.read_bytes()
        for candidate in sorted(root.rglob("*"))
        if candidate.is_file()
    }


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


def constant_horizontal_flow(
    size: tuple[int, int], distance: float
) -> np.ndarray:
    width, height = size
    flow = np.zeros((height, width, 2), dtype=np.float32)
    flow[..., 0] = distance
    return flow


def test_render_between_counts_partial_border_samples_once():
    size = (4, 2)
    opaque_white = Image.new("RGBA", size, (255, 255, 255, 255))

    rendered = render_between(
        opaque_white,
        opaque_white,
        constant_horizontal_flow(size, 1.0),
        constant_horizontal_flow(size, -1.0),
        0.5,
    )

    assert set(rendered.getchannel("A").getdata()) == {255}
    assert set(rendered.getdata()) == {(255, 255, 255, 255)}


def test_render_between_uses_flow_direction_instead_of_cross_dissolving():
    size = (7, 3)
    first = Image.new("RGBA", size, (0, 0, 0, 0))
    second = Image.new("RGBA", size, (0, 0, 0, 0))
    first.putpixel((1, 1), (240, 80, 20, 255))
    second.putpixel((5, 1), (240, 80, 20, 255))

    rendered = render_between(
        first,
        second,
        constant_horizontal_flow(size, 4.0),
        constant_horizontal_flow(size, -4.0),
        0.5,
    )

    assert rendered.getchannel("A").getbbox() == (3, 1, 4, 2)
    assert rendered.getpixel((3, 1)) == (240, 80, 20, 255)
    assert rendered.getpixel((1, 1))[3] == 0
    assert rendered.getpixel((5, 1))[3] == 0


@pytest.mark.parametrize(
    ("conflict", "expected_roles"),
    (
        ("output_is_keyframes", "keyframe_dir and output_dir"),
        ("qa_is_output", "output_dir and qa_dir"),
        ("qa_is_keyframes", "keyframe_dir and qa_dir"),
    ),
)
def test_build_action_rejects_equal_resolved_directory_roles_before_writes(
    tmp_path: Path, conflict: str, expected_roles: str
):
    keyframe_dir = make_keyframes(tmp_path / "keys").resolve()
    output_dir = (tmp_path / "out").resolve()
    qa_dir = (tmp_path / "qa").resolve()
    if conflict == "output_is_keyframes":
        output_dir = relative_alias(keyframe_dir)
    elif conflict == "qa_is_output":
        qa_dir = relative_alias(output_dir)
    else:
        qa_dir = relative_alias(keyframe_dir)

    role_roots = {
        path.resolve() for path in (keyframe_dir, output_dir, qa_dir)
    }
    before = {root: tree_snapshot(root) for root in role_roots}
    keyframe_bytes = {
        path.name: path.read_bytes() for path in sorted(keyframe_dir.glob("*.png"))
    }

    with pytest.raises((RuntimeError, ValueError), match=expected_roles):
        build_action(keyframe_dir, output_dir, qa_dir, "jump")

    assert {
        path.name: path.read_bytes() for path in sorted(keyframe_dir.glob("*.png"))
    } == keyframe_bytes
    assert {root: tree_snapshot(root) for root in role_roots} == before
    for root in role_roots:
        assert not any(
            (root / name).exists()
            for name in (
                "contact-sheet.png",
                "normal.gif",
                "slow.gif",
                "stats.json",
            )
        )


def test_build_action_preserves_keyframe_bytes(tmp_path: Path):
    keys = make_keyframes(tmp_path / "keys")
    output = tmp_path / "out"
    output.mkdir()
    (output / "99.png").write_bytes(b"stale managed frame")
    (output / "agent-report.md").write_text("keep me", encoding="utf-8")

    report = build_action(keys, output, tmp_path / "qa", "jump")

    assert INTERMEDIATE_COUNTS == (5, 5, 4, 5, 5)
    assert FINAL_POSITIONS == (0, 6, 12, 17, 23, 29)
    assert [path.name for path in sorted(output.glob("*.png"))] == [
        f"{index:02d}.png" for index in range(30)
    ]
    assert (output / "agent-report.md").read_text(encoding="utf-8") == "keep me"
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

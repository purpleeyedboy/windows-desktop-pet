import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tools.animation_qa import write_action_qa


FRAME_SIZE = (512, 768)
REQUIRED_STATS = {
    "sha256",
    "alpha_bbox",
    "alpha_centroid",
    "effective_area",
    "largest_component_ratio",
    "edge_chroma_count",
    "aligned_mask_iou",
}


def make_thirty_frames() -> list[Image.Image]:
    frames = []
    for index in range(30):
        frame = Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame)
        left = 80 + index * 2
        draw.rectangle((left, 310, left + 63, 405), fill=(225, 135, 70, 255))
        frames.append(frame)
    return frames


def make_precise_metric_frames() -> list[Image.Image]:
    frames = []
    for index in range(30):
        frame = Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0))
        frame.putpixel((10 + index, 20), (255, 0, 0, 255))
        frame.putpixel((11 + index, 20), (0, 255, 0, 128))
        frames.append(frame)
    return frames


def test_qa_writer_creates_required_artifacts(tmp_path: Path):
    report = write_action_qa(make_thirty_frames(), tmp_path, "jump")

    assert set(report["artifacts"]) == {
        "contact-sheet.png",
        "normal.gif",
        "slow.gif",
        "stats.json",
    }
    assert all((tmp_path / name).is_file() for name in report["artifacts"])
    with Image.open(tmp_path / "normal.gif") as normal:
        assert normal.n_frames == 30
    with Image.open(tmp_path / "slow.gif") as slow:
        assert slow.n_frames == 30


def test_qa_stats_include_required_per_frame_metrics(tmp_path: Path):
    report = write_action_qa(make_thirty_frames(), tmp_path, "shake")
    saved = json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))

    assert saved == report
    assert saved["action"] == "shake"
    assert saved["frame_count"] == 30
    assert saved["normal_duration_ms"] == 33
    assert saved["slow_duration_ms"] == 132
    assert len(saved["frames"]) == 30
    assert REQUIRED_STATS <= set(saved["frames"][0])
    assert saved["frames"][0]["aligned_mask_iou"] is None
    assert all(
        frame["aligned_mask_iou"] == pytest.approx(1.0)
        for frame in saved["frames"][1:]
    )
    assert all(len(frame["sha256"]) == 64 for frame in saved["frames"])
    assert all(frame["alpha_bbox"] for frame in saved["frames"])
    assert all(frame["effective_area"] > 0 for frame in saved["frames"])
    assert all(frame["largest_component_ratio"] == 1.0 for frame in saved["frames"])


def test_qa_stats_have_exact_documented_metric_definitions(tmp_path: Path):
    report = write_action_qa(make_precise_metric_frames(), tmp_path, "jump")
    first = report["frames"][0]
    second = report["frames"][1]

    assert first["sha256"] == (
        "8b45311457f4c6f5d425ae6e111819e3c2acbf536b58b6bce39789b46fa87f7f"
    )
    assert first["alpha_bbox"] == [10, 20, 12, 21]
    assert first["alpha_centroid"] == [10.334204, 20.0]
    assert first["effective_area"] == 1.501961
    assert first["largest_component_ratio"] == 1.0
    assert first["edge_chroma_count"] == 1
    assert first["aligned_mask_iou"] is None
    assert second["aligned_mask_iou"] == 1.0


def test_qa_writer_requires_exactly_thirty_runtime_frames(tmp_path: Path):
    with pytest.raises(ValueError, match="30"):
        write_action_qa(make_thirty_frames()[:-1], tmp_path, "jump")

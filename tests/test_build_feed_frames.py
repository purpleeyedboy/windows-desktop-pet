import hashlib
import json
from pathlib import Path

from PIL import Image

from tools.build_feed_frames import build_feed_assets, decode_source_bundle, locate_subjects


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/feed/v1/manifest.json"


def test_supplied_sources_have_recorded_identity_and_six_non_grid_subjects():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source_root = MANIFEST.parent / "source"
    assert manifest["source_size"] == [1024, 1536]
    bundle = source_root / manifest["source_bundle"]
    assert bundle.suffix == ".txt"
    assert max(map(len, bundle.read_text(encoding="ascii").splitlines())) <= 120
    decoded = decode_source_bundle(bundle)
    for key in ("color", "mask"):
        data = decoded[key]
        assert hashlib.sha256(data).hexdigest() == manifest["sources"][key]["sha256"]
        assert Image.open(__import__("io").BytesIO(data)).size == (1024, 1536)

    boxes = locate_subjects(Image.open(__import__("io").BytesIO(decoded["mask"])))
    assert len(boxes) == 6
    assert [box[3] for box in boxes[:3]] == sorted(box[3] for box in boxes[:3]) or all(
        745 <= box[3] <= 790 for box in boxes[:3]
    )
    assert all(1325 <= box[3] <= 1380 for box in boxes[3:])
    assert len({box[2] - box[0] for box in boxes}) > 1


def test_builder_writes_deterministic_foot_aligned_rgba_frames(tmp_path):
    first = build_feed_assets(MANIFEST, tmp_path / "first")
    second = build_feed_assets(MANIFEST, tmp_path / "second")
    assert [item.sha256 for item in first] == [item.sha256 for item in second]
    assert [item.name for item in first] == [f"{index:02d}.png" for index in range(6)]

    for item in first:
        with Image.open(item.path) as frame:
            assert frame.mode == "RGBA"
            assert frame.size == (672, 768)
            alpha_box = frame.getchannel("A").getbbox()
            assert alpha_box is not None
            assert alpha_box[3] == 736
            assert alpha_box[3] - alpha_box[1] == 524
            assert frame.getchannel("A").getextrema() == (0, 255)


def test_manifest_is_compact_and_describes_requested_pose_order():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert MANIFEST.stat().st_size < 4096
    assert not list((MANIFEST.parent / "source").glob("*.png"))
    assert len(list((MANIFEST.parent / "source").glob("*.txt"))) == 1
    assert manifest["poses"] == [
        "half_open",
        "wide_open",
        "puffed_closed",
        "wide_open_repeat",
        "upper_lip_lick",
        "corner_lick",
    ]
    assert manifest["canonical"] == {
        "canvas": [672, 768],
        "subject_height": 524,
        "feet_y": 736,
        "center_x": 336,
        "original_offset": [80, 0],
        "original_sha256": "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7",
    }

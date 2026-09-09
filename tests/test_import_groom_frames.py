from __future__ import annotations

import hashlib
import base64
import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from desktop_pet.groom_import import extract_sheet_subject, opaque_subject_box

from tools.import_groom_frames import (
    ART_SIZE,
    RUNTIME_OFFSET,
    RUNTIME_SIZE,
    build_alpha,
    import_groom_frames,
    primary_subject_box,
)


ROOT = Path(__file__).resolve().parents[1]


def test_build_alpha_keeps_enclosed_black_paw_line_opaque() -> None:
    mask = Image.new("L", (12, 12), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((2, 2, 9, 9), fill=255)
    draw.line((5, 4, 5, 7), fill=0, width=1)

    alpha = build_alpha(mask)

    assert alpha.getpixel((0, 0)) == 0
    assert alpha.getpixel((5, 5)) == 255


def test_approved_sheet_rebuilds_twelve_anchored_runtime_frames(tmp_path: Path) -> None:
    manifest = ROOT / "assets/groom/v2.1/manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    encoded = (manifest.parent / data["source"]).read_text(encoding="ascii")
    assert max(map(len, encoded.splitlines())) <= 120
    assert hashlib.sha256(base64.b64decode(encoded)).hexdigest() == data["decoded_png_sha256"]
    frames = import_groom_frames(manifest, tmp_path)

    assert len(frames) == 12
    assert all(frame.mode == "RGBA" and frame.size == RUNTIME_SIZE for frame in frames)
    assert ART_SIZE == (512, 768)
    assert RUNTIME_OFFSET == (64, 0)
    # Check the real following compositor so an internally consistent but
    # wider animation cannot resize/clamp the pet window at screen edges.
    from desktop_pet.assets import load_head_neck_compositor
    from desktop_pet.head_neck_deformation import HeadPose
    compositor = load_head_neck_compositor()
    neutral = compositor.compose(0.0, 0.0, HeadPose(0.0, 0.0))
    assert frames[0].size == neutral.size
    assert frames[0].tobytes() == neutral.tobytes()
    assert frames[0].tobytes() == frames[-1].tobytes()
    assert len({hashlib.sha256(frame.tobytes()).hexdigest() for frame in frames[1:-1]}) >= 7
    for index in range(12):
        assert (tmp_path / f"{index:02d}.png").is_file()


def test_import_is_byte_deterministic(tmp_path: Path) -> None:
    manifest = ROOT / "assets/groom/v2.1/manifest.json"
    first = tmp_path / "first"
    second = tmp_path / "second"
    import_groom_frames(manifest, first)
    import_groom_frames(manifest, second)

    assert [p.read_bytes() for p in sorted(first.glob("*.png"))] == [
        p.read_bytes() for p in sorted(second.glob("*.png"))
    ]


def test_each_action_uses_one_grounded_primary_subject_without_neighbor_feet(tmp_path: Path) -> None:
    frames = import_groom_frames(ROOT / "assets/groom/v2.1/manifest.json", tmp_path)
    for index, frame in enumerate(frames[1:11], 1):
        box = primary_subject_box(frame.getchannel("A"))
        assert box is not None
        assert box[3] >= 733, f"frame {index:02d} primary subject is not grounded: {box}"
        assert box[3] - box[1] >= 515, f"frame {index:02d} was shrunk by cell-edge debris: {box}"
        assert opaque_subject_box(frame)[3] == opaque_subject_box(frames[0])[3]
    # The approved fifth pose has an extended ear silhouette (337 source pixels
    # versus 329 in the default). It must retain that difference at a common
    # scale, rather than being independently squeezed to the default's height.
    default_box = opaque_subject_box(frames[0])
    raised_box = opaque_subject_box(frames[4])
    default_height = default_box[3] - default_box[1]
    raised_height = raised_box[3] - raised_box[1]
    assert abs(raised_height / default_height - 337 / 329) < 0.004


def test_approved_atlas_subject_crossing_grid_line_keeps_ear_and_hindquarters() -> None:
    encoded = (ROOT / "assets/groom/v2.1/source/groom-left-approved.png.b64").read_bytes()
    sheet = Image.open(BytesIO(base64.b64decode(encoded))).convert("RGBA")
    fifth = extract_sheet_subject(sheet, 4)
    box = opaque_subject_box(fifth)
    # Measured against the complete approved sheet: x=96..363, y=359..695.
    # A hard crop at x/y=362 loses both the right flank and the ear tip.
    assert (box[2] - box[0], box[3] - box[1]) == (268, 337)
    assert sum(value >= 128 for value in fifth.getchannel("A").getdata()) == 51923

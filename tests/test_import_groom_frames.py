from __future__ import annotations

import hashlib
import base64
import json
from pathlib import Path

from PIL import Image, ImageDraw

from tools.import_groom_frames import (
    ART_SIZE,
    RUNTIME_OFFSET,
    RUNTIME_SIZE,
    build_alpha,
    import_groom_frames,
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
    assert RUNTIME_OFFSET == (80, 0)
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

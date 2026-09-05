from __future__ import annotations

import json

from PIL import Image

from tools.build_idle_lick_preview import build_preview


def test_preview_script_writes_only_requested_temporary_output(tmp_path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGBA", (512, 768), (120, 90, 60, 255)).save(source)
    output = tmp_path / "preview"

    report = build_preview(source, output)

    assert sorted(path.name for path in output.iterdir()) == [
        "idle-lick-contact-sheet.png",
        "idle-lick-preview.json",
    ]
    assert report["frames"] == 10
    assert report["sides"] == ["left", "right"]
    assert json.loads((output / "idle-lick-preview.json").read_text())["frames"] == 10

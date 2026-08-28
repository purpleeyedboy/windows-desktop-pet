from pathlib import Path

import pytest
from PIL import Image

from tools.rig_center_contract import CANONICAL_SHA256, copy_canonical, validate_rgba


def make_canonical(path: Path) -> None:
    image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    image.putpixel((100, 200), (210, 140, 80, 255))
    image.save(path)


def test_copy_canonical_preserves_source_bytes(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "rig" / "canonical-idle.png"
    make_canonical(source)
    monkeypatch.setattr("tools.rig_center_contract.CANONICAL_SHA256", __import__("hashlib").sha256(source.read_bytes()).hexdigest())
    report = copy_canonical(source, destination)
    assert destination.read_bytes() == source.read_bytes()
    assert report == {"sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest(), "mode": "RGBA", "size": [512, 768]}


def test_copy_canonical_rejects_wrong_hash(tmp_path: Path) -> None:
    source = tmp_path / "wrong.png"
    make_canonical(source)
    with pytest.raises(RuntimeError, match="canonical SHA-256"):
        copy_canonical(source, tmp_path / "copy.png")


def test_validate_rgba_rejects_hidden_rgb_and_visible_border(tmp_path: Path) -> None:
    path = tmp_path / "bad.png"
    image = Image.new("RGBA", (512, 768), (1, 2, 3, 0))
    image.putpixel((0, 0), (50, 60, 70, 255))
    image.save(path)
    errors = validate_rgba(path)
    assert "Alpha-0 RGB must be zero" in errors
    assert "outer border must be transparent" in errors

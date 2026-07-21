from pathlib import Path
import sys

from desktop_pet.paths import asset_path


def test_asset_path_uses_source_root(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    resolved = asset_path("assets", "pet", "idle.png")
    assert resolved.parts[-3:] == ("assets", "pet", "idle.png")


def test_asset_path_uses_pyinstaller_root(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert asset_path("assets", "pet") == tmp_path / "assets" / "pet"

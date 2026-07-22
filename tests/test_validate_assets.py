import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

from tools.validate_assets import main, validate_assets


ACTIONS = ("jump", "squash", "shake")
FINAL_POSITIONS = (0, 6, 12, 17, 23, 29)


def make_valid_thirty_frame_tree(tmp_path: Path) -> tuple[Path, Path]:
    pet = tmp_path / "pet"
    keys = tmp_path / "keyframes"
    manifest = {"version": 1, "actions": {}}
    for action in ACTIONS:
        action_dir = pet / action
        key_dir = keys / action
        action_dir.mkdir(parents=True)
        key_dir.mkdir(parents=True)
        for index in range(30):
            image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
            image.putpixel((1, 1), (index, 2, 3, 255))
            image.save(action_dir / f"{index:02d}.png")

        action_manifest = {}
        for key_index, frame_index in enumerate(FINAL_POSITIONS):
            source = action_dir / f"{frame_index:02d}.png"
            destination = key_dir / f"{key_index:02d}.png"
            destination.write_bytes(source.read_bytes())
            action_manifest[destination.name] = {
                "final_name": source.name,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        manifest["actions"][action] = action_manifest
    (keys / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pet, keys


def test_validator_accepts_valid_temporary_thirty_frame_tree(tmp_path: Path):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)

    report = validate_assets(pet, keys)

    assert report == {"errors": [], "actions": 3, "total_frames": 90}
    json.dumps(report)


def test_validator_rejects_changed_mapped_keyframe(tmp_path: Path):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)
    Image.new("RGBA", (512, 768), (255, 0, 0, 255)).save(pet / "jump" / "06.png")

    report = validate_assets(pet, keys)

    assert any("SHA-256" in error for error in report["errors"])


def test_validator_rejects_missing_manifest_mapping(tmp_path: Path):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)
    manifest_path = keys / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["actions"]["jump"]["00.png"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = validate_assets(pet, keys)

    assert any("missing mapped SHA-256" in error for error in report["errors"])


def test_validator_rejects_non_rgba_frame(tmp_path: Path):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)
    Image.new("RGB", (512, 768), "white").save(pet / "jump" / "01.png")

    report = validate_assets(pet, keys)

    assert any("512x768 RGBA" in error for error in report["errors"])


def test_validator_rejects_wrong_canvas_size(tmp_path: Path):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)
    Image.new("RGBA", (256, 256), (0, 0, 0, 0)).save(pet / "jump" / "01.png")

    report = validate_assets(pet, keys)

    assert any("512x768 RGBA" in error for error in report["errors"])


def test_validator_rejects_missing_alpha_extrema(tmp_path: Path):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)
    Image.new("RGBA", (512, 768), (0, 0, 0, 0)).save(pet / "jump" / "01.png")

    report = validate_assets(pet, keys)

    assert any("transparent background and opaque subject" in error for error in report["errors"])


def test_validator_rejects_transparent_rgb_residue(tmp_path: Path):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)
    image = Image.new("RGBA", (512, 768), (1, 2, 3, 0))
    image.putpixel((1, 1), (1, 2, 3, 255))
    image.save(pet / "jump" / "01.png")

    report = validate_assets(pet, keys)

    assert any("transparent RGB" in error for error in report["errors"])


def test_validator_rejects_opaque_outer_border(tmp_path: Path):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)
    image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    image.putpixel((1, 1), (1, 2, 3, 255))
    image.putpixel((0, 0), (1, 2, 3, 255))
    image.save(pet / "jump" / "01.png")

    report = validate_assets(pet, keys)

    assert any("outer border" in error for error in report["errors"])


def test_cli_writes_json_report(tmp_path: Path, monkeypatch, capsys):
    pet, keys = make_valid_thirty_frame_tree(tmp_path)
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["validate_assets.py", str(pet), "--keyframe-root", str(keys), "--report", str(report_path)],
    )

    assert main() == 0

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "errors": [],
        "actions": 3,
        "total_frames": 90,
    }
    assert capsys.readouterr().out == "OK: 3 actions, 90 frames, 512x768 RGBA\n"

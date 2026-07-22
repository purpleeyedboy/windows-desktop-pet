from pathlib import Path

import pytest

from tools.keyframes import ACTIONS, archive_keyframes


def make_six_frame_source(root: Path) -> Path:
    for action in ACTIONS:
        action_dir = root / action
        action_dir.mkdir(parents=True)
        for index in range(6):
            (action_dir / f"{index:02d}.png").write_bytes(
                f"{action}-{index}".encode("ascii")
            )
    return root


def test_archive_copies_bytes_and_records_mapping(tmp_path: Path):
    source = make_six_frame_source(tmp_path / "pet")
    archive = tmp_path / "keyframes"

    manifest = archive_keyframes(source, archive)

    assert manifest["final_positions"] == [0, 6, 12, 17, 23, 29]
    for action in ACTIONS:
        for index in range(6):
            name = f"{index:02d}.png"
            assert (archive / action / name).read_bytes() == (
                source / action / name
            ).read_bytes()
            assert len(manifest["actions"][action][name]["sha256"]) == 64


def test_archive_refuses_changed_keyframe(tmp_path: Path):
    source = make_six_frame_source(tmp_path / "pet")
    archive = tmp_path / "keyframes"
    archive_keyframes(source, archive)

    (source / "jump" / "00.png").write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="keyframe mismatch"):
        archive_keyframes(source, archive)

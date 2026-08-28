from pathlib import Path

import pytest
from PyInstaller.archive.readers import ArchiveReadError

import tools.verify_release_archive as release_archive


def _write_required_release_tree(project_root: Path) -> dict[str, bytes]:
    contents = {
        **{
            f"assets/keyframes/{action}/{index:02d}.png": (
                f"{action}-{index}".encode()
            )
            for action in ("jump", "squash", "shake")
            for index in range(6)
        },
        **{
            f"assets/bubble/{name}.png": name.encode()
            for name in (
                "cat-ear-bow-body",
                "tail-down",
                "tail-up",
                "tail-left",
                "tail-right",
            )
        },
        "assets/fonts/ZCOOLKuaiLe-Regular.ttf": b"zcool-font",
        "assets/fonts/NotoSans-Variable.ttf": b"noto-sans-font",
        "assets/fonts/NotoSansMath-Regular.ttf": b"noto-math-font",
        "assets/fonts/licenses/ZCOOLKuaiLe-OFL-1.1.txt": b"zcool-license",
        "assets/fonts/licenses/NotoSans-OFL-1.1.txt": b"noto-sans-license",
        "assets/fonts/licenses/NotoSansMath-OFL-1.1.txt": b"noto-math-license",
        "assets/dialogue/phrases.json": b'{"jump": []}',
        "THIRD_PARTY_NOTICES.txt": b"third-party notices",
    }
    for relative, data in contents.items():
        path = project_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return contents


def _install_fake_archive(monkeypatch, contents: dict[str, bytes]) -> None:
    class FakeArchiveReader:
        def __init__(self, _filename: str):
            self.toc = {
                relative.replace("/", "\\"): object() for relative in contents
            }

        def extract(self, archived_name: str) -> bytes:
            return contents[archived_name.replace("\\", "/")]

    monkeypatch.setattr(release_archive, "CArchiveReader", FakeArchiveReader)


def test_verify_archive_reports_missing_required_font(tmp_path, monkeypatch):
    contents = _write_required_release_tree(tmp_path)
    contents.pop("assets/fonts/NotoSansMath-Regular.ttf")
    _install_fake_archive(monkeypatch, contents)

    with pytest.raises(
        ValueError,
        match=r"missing archive resource: assets/fonts/NotoSansMath-Regular\.ttf",
    ):
        release_archive.verify_archive(tmp_path / "release.exe", tmp_path)


def test_verify_archive_reports_source_byte_mismatch(tmp_path, monkeypatch):
    contents = _write_required_release_tree(tmp_path)
    archived_contents = dict(contents)
    archived_contents["assets/dialogue/phrases.json"] = b"different archive bytes"
    _install_fake_archive(monkeypatch, archived_contents)

    with pytest.raises(
        ValueError,
        match=r"archive resource differs from source: assets/dialogue/phrases\.json",
    ):
        release_archive.verify_archive(tmp_path / "release.exe", tmp_path)


def test_main_reports_verified_category_counts(tmp_path, monkeypatch, capsys):
    contents = _write_required_release_tree(tmp_path)
    _install_fake_archive(monkeypatch, contents)
    monkeypatch.setattr(release_archive, "ROOT", tmp_path)

    assert release_archive.main([str(tmp_path / "release.exe")]) == 0
    assert capsys.readouterr().out.strip() == (
        "release archive verified: keyframes 18, bubbles 5, fonts 3, "
        "licenses 3, dialogue 1, notice 1"
    )


def test_main_reports_unreadable_archive_as_release_gate_failure(
    tmp_path, monkeypatch, capsys
):
    def raise_archive_error(_filename: str):
        raise ArchiveReadError("invalid CArchive")

    monkeypatch.setattr(release_archive, "CArchiveReader", raise_archive_error)
    monkeypatch.setattr(release_archive, "ROOT", tmp_path)

    assert release_archive.main([str(tmp_path / "release.exe")]) == 1
    assert capsys.readouterr().err.strip() == (
        "release archive verification failed: invalid CArchive"
    )

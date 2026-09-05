from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image

from tools.build_ears_preview import build_preview


ROOT = Path(__file__).resolve().parents[1]
V21_BASE = "c3b218df9dd0cfc84d96231701e771f0382388e1"


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )


def test_complete_ears_diff_contains_no_binary_entries() -> None:
    binary = []
    for line in _git("diff", "--numstat", V21_BASE).splitlines():
        added, deleted, path = line.split("\t", 2)
        if added == "-" or deleted == "-":
            binary.append(path)
    assert binary == []


def test_all_158_baseline_assets_keep_their_exact_git_blob_hashes() -> None:
    baseline = {
        path: blob
        for _mode, _kind, blob, path in (
            line.split(maxsplit=3)
            for line in _git("ls-tree", "-r", V21_BASE, "assets").splitlines()
        )
    }
    assert len(baseline) == 158
    assert set(baseline) == {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "assets").rglob("*")
        if path.is_file()
    }
    current = {
        path: _git("hash-object", path).strip() for path in baseline
    }
    assert current == baseline


def test_preview_is_deterministic_temporary_output_not_a_tracked_png(tmp_path) -> None:
    first = tmp_path / "first" / "ears-preview.png"
    second = tmp_path / "second" / "ears-preview.png"

    build_preview(first)
    build_preview(second)

    assert first.read_bytes() == second.read_bytes()
    assert Image.open(first).size == (3072, 1536)
    assert "qa/v21-ears-preview.png" not in _git("ls-files").splitlines()
    assert "/qa/v21-ears-preview.png" in (ROOT / ".gitignore").read_text(
        encoding="utf-8"
    ).splitlines()


def test_windows_gate_skips_automated_tests_and_preserves_exe_contract() -> None:
    workflow = (ROOT / ".github/workflows/windows-ears-candidate.yml").read_text(
        encoding="utf-8"
    )
    assert "fetch-depth: 0" in workflow
    assert "pytest" not in workflow.lower()
    assert "tools/build_ears_preview.py" not in workflow
    assert "-SkipTests" not in workflow
    assert "未自动测试" in workflow
    assert 'if ($exes.Count -ne 1)' in workflow
    assert "桌面宠物_双耳点击反馈.exe" in workflow
    assert "Get-FileHash" in workflow

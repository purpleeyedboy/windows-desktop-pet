from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from tools.build_ears_preview import build_preview
from desktop_pet.ear_interaction import EAR_KEYFRAMES


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
    assert set(baseline) | {"assets/keyframes/playback.json"} == {
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
    assert Image.open(first).size == (256 * max(len(s.frames) for s in EAR_KEYFRAMES.values()), 768)
    assert "qa/v21-ears-preview.png" not in _git("ls-files").splitlines()
    assert "/qa/v21-ears-preview.png" in (ROOT / ".gitignore").read_text(
        encoding="utf-8"
    ).splitlines()


def test_windows_gate_runs_ear_regressions_and_preserves_exe_contract() -> None:
    workflow = (ROOT / ".github/workflows/windows-ears-candidate.yml").read_text(
        encoding="utf-8"
    )
    assert "fetch-depth: 0" in workflow
    assert "python -m pytest -q" in workflow.lower()
    assert "tools/build_ears_preview.py" not in workflow
    assert "-SkipTests" not in workflow
    assert "已通过双耳自动化回归" in workflow
    assert 'if ($exes.Count -ne 1)' in workflow
    assert "桌面宠物_耳朵防触摸系统_单次躲闪-20260910.exe" in workflow
    assert "Get-FileHash" in workflow
    assert "1a18477faa4caa28170e648437d7cb8b39612ac0" in workflow


def test_verified_pr5_source_manifest_and_runtime_wiring_are_present() -> None:
    source_path = ROOT / "docs/v2.1-ears-foundation-source.json"
    source = source_path.read_text(encoding="utf-8")
    manifest = json.loads(source)
    assert '"source_commit": "e178f371bd2da1c0b4e892609acfdf79bfcab450"' in source
    assert '"current_core_commit": "1a18477faa4caa28170e648437d7cb8b39612ac0"' in source
    assert '"blob": "a58b54aa1d3cb1bfe1b88e9554697a417e7e2dcb"' in source
    assert '"base_commit": "c3b218df9dd0cfc84d96231701e771f0382388e1"' in source
    assert source.count('"blob":') == 30
    override = manifest["synchronized_overrides"]
    assert override == [{
        "path": "src/desktop_pet/foundation/animation.py",
        "status": "modified",
        "blob": "a58b54aa1d3cb1bfe1b88e9554697a417e7e2dcb",
    }]
    assert _git("hash-object", override[0]["path"]).strip() == override[0]["blob"]
    window = (ROOT / "src/desktop_pet/window.py").read_text(encoding="utf-8")
    assert 'runtime.bind("input.ear", self._consume_ear)' in window
    assert 'self.services.animation.play("ears", side, token)' in window

import hashlib
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BASELINE = "c3b218df9dd0cfc84d96231701e771f0382388e1"


def test_drag_diff_gate_rejects_binary_changes_and_locks_all_158_assets():
    result = subprocess.run(
        [
            sys.executable,
            "tools/verify_drag_source_diff.py",
            "--baseline",
            BASELINE,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "binary diff entries: 0" in result.stdout
    assert "approved assets unchanged: 158" in result.stdout


def test_preview_is_generated_only_in_requested_temporary_directory(tmp_path):
    output = tmp_path / "drag-expectation-qa"
    result = subprocess.run(
        [
            sys.executable,
            "tools/build_drag_expectation_preview.py",
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    preview = output / "before-after.png"
    report = output / "stats.json"
    assert preview.is_file()
    assert report.is_file()
    with Image.open(preview) as image:
        assert image.mode == "RGBA"
        assert image.size == (1024, 768)
    assert hashlib.sha256(preview.read_bytes()).hexdigest() in report.read_text(
        encoding="utf-8"
    )
    assert not (ROOT / "qa/drag-expectation/before-after.png").exists()


def test_windows_candidate_generates_and_uploads_temporary_qa_artifact():
    workflow = (
        ROOT / ".github/workflows/windows-drag-expectation-candidate.yml"
    ).read_text(encoding="utf-8")

    assert "verify_drag_source_diff.py" in workflow
    assert "build_drag_expectation_preview.py" in workflow
    assert "$env:RUNNER_TEMP" in workflow
    assert "desktop-pet-v2-1-drag-expectation-qa" in workflow
    assert "qa/drag-expectation/before-after.png" not in workflow
    assert "fetch-depth: 0" in workflow
    assert "qa/drag-expectation/*.png" in (ROOT / ".gitignore").read_text(
        encoding="utf-8"
    )

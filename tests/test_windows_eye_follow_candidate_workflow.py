from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "windows-eye-follow-candidate.yml"
)


def test_windows_candidate_workflow_is_pinned_read_only_and_uploads_only_candidate():
    assert WORKFLOW.is_file(), "Windows eye-follow candidate workflow is missing"
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "on:\n"
        "  pull_request:\n"
        "    branches:\n"
        "      - codex/head-neck-continuous-preview\n"
        "  workflow_dispatch:\n\n"
        "permissions:\n"
        "  contents: read\n" in workflow
    )
    assert "runs-on: windows-latest" in workflow
    assert "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0" in workflow
    assert "persist-credentials: false" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert "python-version: \"3.11\"" in workflow
    assert "python -m pip install \".[dev]\" -r requirements-assets.txt" in workflow
    assert "PIL.__version__.split(\".\", 1)[0] == \"11\"" in workflow
    assert "python -m pytest -q" in workflow
    assert "--ignore" not in workflow
    assert ".\\build_eye_follow_candidate.ps1 -SkipTests" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow
    assert "Get-FileHash" in workflow
    assert "name: desktop-pet-v2-1-baseline" in workflow
    assert "dist-eye-follow-candidate/桌面宠物_最终素材与转头角度基线修正版.exe" in workflow
    assert "retention-days: 7" in workflow
    assert "if-no-files-found: error" in workflow
    assert "secrets." not in workflow.lower()
    assert "release" not in workflow.lower()
    assert workflow.count("uses: ") == 3

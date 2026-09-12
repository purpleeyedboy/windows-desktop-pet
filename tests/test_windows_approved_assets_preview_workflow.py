from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/windows-approved-assets-preview.yml"


def test_preview_workflow_is_pinned_read_only_and_builds_verified_candidate() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "codex/head-neck-continuous-preview" in workflow
    assert "contents: read" in workflow
    assert "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0" in workflow
    assert "persist-credentials: false" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert 'python-version: "3.11"' in workflow
    assert "requirements-assets.txt" in workflow
    assert ".\\build_eye_follow_candidate.ps1 -SkipTests" in workflow
    assert "Get-FileHash" in workflow
    assert "name: desktop-pet-v2-1-baseline" in workflow
    assert "dist-eye-follow-candidate/桌面宠物_最终素材与转头角度基线修正版.exe" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow
    assert "retention-days: 7" in workflow
    assert "if-no-files-found: error" in workflow
    assert "secrets." not in workflow.lower()
    assert "release" not in workflow.lower()
    assert workflow.count("uses: ") == 3

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE = "桌面宠物_双耳点击反馈.exe"


def test_ears_candidate_has_independent_onefile_spec_and_build_metadata() -> None:
    spec = (ROOT / "desktop_pet_ears.spec").read_text(encoding="utf-8")
    script = (ROOT / "build_ears_candidate.ps1").read_text(encoding="utf-8-sig")
    version = (ROOT / "version_info_ears.txt").read_text(encoding="utf-8")

    assert "name='桌面宠物_双耳点击反馈'" in spec
    assert "COLLECT(" not in spec
    assert "build-metadata.json" in spec
    assert "version_info_ears.txt" in spec
    assert EXE in script
    assert "git rev-parse --short HEAD" in script
    assert "Get-Date -Format 'yyyy-MM-dd'" in script
    assert "BASE-001" in script
    assert "双耳点击反馈" in script
    assert "候选版" in script
    assert "Get-FileHash" in script
    assert "Candidate size:" in script
    assert "[switch]$SkipTests" not in script
    assert "pytest" not in script.lower()
    assert "validate_assets.py" not in script
    assert "validate_dialogue.py" not in script
    assert "verify_eye_follow_candidate_archive.py" not in script
    assert "未自动测试" in script
    assert script.index("Clear-CandidateOutputs") < script.index("-m PyInstaller")
    assert "filevers=(2, 1, 1, 0)" in version
    assert EXE in version


def test_windows_ears_workflow_checks_only_expected_exe_size_hash_and_upload() -> None:
    workflow = (ROOT / ".github/workflows/windows-ears-candidate.yml").read_text(encoding="utf-8")
    assert "runs-on: windows-latest" in workflow
    assert "pytest" not in workflow.lower()
    assert "requirements-assets.txt" not in workflow
    assert ".\\build_ears_candidate.ps1" in workflow
    assert "-SkipTests" not in workflow
    assert "tools/build_ears_preview.py" not in workflow
    assert 'if ($exes.Count -ne 1)' in workflow
    assert EXE in workflow
    assert "Length" in workflow
    assert "Get-FileHash" in workflow
    assert "actions/upload-artifact@" in workflow
    assert workflow.count("actions/upload-artifact@") == 1
    assert "未自动测试" in workflow
    assert "secrets." not in workflow.lower()

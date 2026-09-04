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
    assert "测试版" in script
    assert "Get-FileHash" in script
    assert "--metadata $MetadataPath" in script
    assert "Candidate size:" in script
    assert "filevers=(2, 1, 1, 0)" in version
    assert EXE in version


def test_windows_ears_workflow_checks_only_expected_exe_size_hash_and_upload() -> None:
    workflow = (ROOT / ".github/workflows/windows-ears-candidate.yml").read_text(encoding="utf-8")
    assert "runs-on: windows-latest" in workflow
    assert "python -m pytest -q" in workflow
    assert ".\\build_ears_candidate.ps1 -SkipTests" in workflow
    assert 'if ($exes.Count -ne 1)' in workflow
    assert EXE in workflow
    assert "Length" in workflow
    assert "Get-FileHash" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "secrets." not in workflow.lower()

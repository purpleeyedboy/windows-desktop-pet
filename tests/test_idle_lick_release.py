from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE_NAME = "桌面宠物_空闲随机舔手.exe"


def test_idle_lick_candidate_spec_is_independent_one_file_with_version_metadata() -> None:
    spec = (ROOT / "desktop_pet_idle_lick.spec").read_text(encoding="utf-8")
    assert "COLLECT(" not in spec
    assert "name='桌面宠物_空闲随机舔手'" in spec
    assert "version=str(ROOT / 'version_info_idle_lick.txt')" in spec
    assert 'excludes=["numpy", "cv2"]' in spec


def test_build_records_complete_metadata_and_checks_unique_size_and_sha256() -> None:
    script = (ROOT / "build_idle_lick_candidate.ps1").read_text(encoding="utf-8-sig")
    for value in (
        EXE_NAME,
        "2.1-LICK",
        "BASE-001",
        "idle-random-left-right-hand-lick",
        "test_build=true",
        "debug_menu=false",
        "V2.1_LICK_BUILD.md",
        "git rev-parse --short HEAD",
        "Get-Date -AsUTC",
        "Get-FileHash",
        "MaxCandidateBytes",
        r"tools\verify_eye_follow_candidate_archive.py",
    ):
        assert value in script
    assert "& $Python -m pytest -q" in script
    assert "CandidateExes.Count -ne 1" in script


def test_windows_actions_runs_tests_and_uploads_only_the_verified_candidate() -> None:
    workflow = (ROOT / ".github/workflows/windows-idle-lick-candidate.yml").read_text(
        encoding="utf-8"
    )
    assert "runs-on: windows-latest" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "python -m pytest -q" in workflow
    assert EXE_NAME in workflow
    assert "if ($exes.Count -ne 1)" in workflow
    assert "Get-FileHash" in workflow
    assert "MaxCandidateBytes" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "if-no-files-found: error" in workflow
    assert "secrets." not in workflow.lower()

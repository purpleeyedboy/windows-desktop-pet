from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE_NAME = "桌面宠物_空闲随机舔手.exe"


def test_idle_lick_candidate_spec_is_independent_one_file_with_version_metadata() -> None:
    spec = (ROOT / "desktop_pet_idle_lick.spec").read_text(encoding="utf-8")
    assert "COLLECT(" not in spec
    assert "name='桌面宠物_空闲随机舔手'" in spec
    assert "version=str(ROOT / 'version_info_idle_lick.txt')" in spec
    assert 'excludes=["numpy", "cv2"]' in spec


def test_build_marks_candidate_untested_and_checks_unique_size_and_sha256() -> None:
    script = (ROOT / "build_idle_lick_candidate.ps1").read_text(encoding="utf-8-sig")
    for value in (
        EXE_NAME,
        "2.1-LICK",
        "BASE-001",
        "idle-random-left-right-hand-lick",
        "automated_tests=false",
        "acceptance_status=awaiting-user-windows-validation",
        "debug_menu=false",
        "V2.1_LICK_BUILD.md",
        "git rev-parse --short HEAD",
        "Get-Date -AsUTC",
        "Get-FileHash",
        "MaxCandidateBytes",
    ):
        assert value in script
    assert "pytest" not in script
    assert "verify_eye_follow_candidate_archive" not in script
    assert "CandidateExes.Count -ne 1" in script


def test_windows_actions_skips_tests_and_uploads_only_the_checked_candidate() -> None:
    workflow = (ROOT / ".github/workflows/windows-idle-lick-candidate.yml").read_text(
        encoding="utf-8"
    )
    assert "runs-on: windows-latest" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "pytest" not in workflow
    assert ".\\build_idle_lick_candidate.ps1 -SkipTests" in workflow
    assert EXE_NAME in workflow
    assert "if ($exes.Count -ne 1)" in workflow
    assert "Get-FileHash" in workflow
    assert "MaxCandidateBytes" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "desktop-pet-v2-1-idle-lick-untested-candidate" in workflow
    assert "UNTESTED - awaiting user Windows validation" in workflow
    assert "if-no-files-found: error" in workflow
    assert "secrets." not in workflow.lower()

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE = "桌面宠物_饥饿值与饥饿动画.exe"


def test_hunger_build_skips_tests_and_checks_name_size_hash() -> None:
    script = (ROOT / "build_hunger.ps1").read_text(encoding="utf-8-sig")
    assert "desktop_pet_hunger.spec" in script
    assert "pytest" not in script.lower()
    assert "SkipTests" not in script
    assert "verify_eye_follow_candidate_archive" not in script
    assert EXE in script
    assert "Count -ne 1" in script
    assert "52428800" in script
    assert "Get-FileHash" in script and "SHA256" in script


def test_hunger_spec_keeps_baseline_assets_and_has_exact_name() -> None:
    spec = (ROOT / "desktop_pet_hunger.spec").read_text(encoding="utf-8")
    assert "桌面宠物_饥饿值与饥饿动画" in spec
    assert "assets/rig/v1/runtime/eye-neutral-v1" in spec
    assert "build_metadata.json" in spec
    assert 'excludes=["numpy", "cv2"]' in spec


def test_windows_action_checks_and_uploads_only_hunger_exe() -> None:
    workflow = (ROOT / ".github/workflows/windows-hunger.yml").read_text(encoding="utf-8")
    assert "runs-on: windows-latest" in workflow
    assert "build_hunger.ps1" in workflow
    assert "pytest" not in workflow.lower()
    assert "requirements-assets.txt" not in workflow
    assert "Count -ne 1" in workflow
    assert EXE in workflow
    assert "Get-FileHash" in workflow and "SHA256" in workflow
    assert "actions/upload-artifact@" in workflow


def test_build_metadata_declares_required_candidate_identity() -> None:
    script = (ROOT / "build_hunger.ps1").read_text(encoding="utf-8-sig")
    for text in (
        "version", "date", "git_short_hash", "baseline_tag", "enabled_features",
        "test_build", "debug_menu", "documentation_baseline",
        "automated_tests", "windows_acceptance",
    ):
        assert text in script
    assert "automated_tests = $false" in script
    assert 'windows_acceptance = "pending_user_validation"' in script


def test_workflow_labels_candidate_as_untested_pending_user_acceptance() -> None:
    workflow = (ROOT / ".github/workflows/windows-hunger.yml").read_text(encoding="utf-8")
    assert "UNTESTED" in workflow
    assert "pending user Windows validation" in workflow


def test_windows_version_resource_labels_exe_as_untested_candidate() -> None:
    version_info = (ROOT / "version_info_hunger.txt").read_text(encoding="utf-8")
    assert "候选版" in version_info
    assert "未经自动测试" in version_info

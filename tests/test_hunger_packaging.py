from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE = "桌面宠物_饥饿真实帧与公共基础接入.exe"


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
    assert EXE.removesuffix(".exe") in spec
    assert "assets/rig/v1/runtime/eye-neutral-v1" in spec
    assert "build_metadata.json" in spec
    assert 'excludes=["numpy", "cv2"]' in spec


def test_windows_action_runs_isolated_hunger_acceptance_and_uploads_only_hunger_exe() -> None:
    workflow = (ROOT / ".github/workflows/windows-hunger.yml").read_text(encoding="utf-8")
    assert "runs-on: windows-latest" in workflow
    assert "build_hunger.ps1" in workflow
    assert "python -m pytest -q" in workflow
    for test_file in (
        "tests/test_foundation_animation.py",
        "tests/test_hunger.py",
        "tests/test_hunger_runtime.py",
        "tests/test_hunger_feedback.py",
        "tests/test_hunger_animation.py",
        "tests/test_hunger_window_integration.py",
    ):
        assert test_file in workflow
    assert "tests/ " not in workflow
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
        "automated_tests", "windows_acceptance", "baseline_commit", "foundation_commit",
        "activity_recovery_fix_commit",
    ):
        assert text in script
    assert "automated_tests = $false" in script
    assert 'windows_acceptance = "pending_user_validation"' in script


def test_workflow_keeps_build_and_visual_acceptance_separate() -> None:
    workflow = (ROOT / ".github/workflows/windows-hunger.yml").read_text(encoding="utf-8")
    assert "startup survived seven seconds; this is not visual acceptance" in workflow
    assert "pending user Windows visual acceptance" in workflow


def test_provenance_records_published_activity_recovery_source() -> None:
    provenance = (ROOT / "docs/hunger-foundation-provenance.json").read_text(
        encoding="utf-8"
    )
    assert (
        '"activity_recovery_fix_commit": '
        '"1a18477faa4caa28170e648437d7cb8b39612ac0"'
    ) in provenance


def test_windows_version_resource_labels_exe_as_test_candidate() -> None:
    version_info = (ROOT / "version_info_hunger.txt").read_text(encoding="utf-8")
    assert "饥饿真实帧候选版（待Windows验收）" in version_info
    assert EXE in version_info

import codecs
import json
from pathlib import Path


NAME = "桌面宠物_文件拖动期待反馈.exe"


def test_drag_candidate_metadata_is_complete_and_scope_limited():
    metadata = json.loads(Path("DRAG_EXPECTATION_BUILD_INFO.json").read_text(encoding="utf-8"))
    assert metadata == {
        "version": "2.1-drag.1",
        "date": "2026-09-04",
        "git_short_hash": "c3b218d",
        "baseline": "BASE-001 / V2.1",
        "enabled_features": ["approved-v2.1-baseline", "file-drag-expectation-feedback"],
        "test_build": True,
        "debug_menu": True,
        "documentation_baseline": "BASELINE_V2.1.md",
        "file_operations": "none",
        "hunger_changes": "none",
        "visual_acceptance": "pending",
        "automated_test_status": "not-run",
        "candidate_status": "awaiting-user-windows-acceptance",
    }


def test_drag_candidate_spec_is_onefile_with_exact_name_and_metadata():
    spec = Path("desktop_pet_drag_expectation.spec").read_text(encoding="utf-8")
    assert "COLLECT(" not in spec
    assert "name='桌面宠物_文件拖动期待反馈'" in spec
    assert "DRAG_EXPECTATION_BUILD_INFO.json" in spec
    assert "desktop_pet_drag_version_info.txt" in spec
    assert 'excludes=["numpy", "cv2"]' in spec
    assert "qa" not in spec.lower()


def test_drag_build_and_actions_skip_tests_but_enforce_candidate_artifact_gates():
    build_path = Path("build_drag_expectation_candidate.ps1")
    assert build_path.read_bytes().startswith(codecs.BOM_UTF8)
    build = build_path.read_text(encoding="utf-8-sig")
    for required in ("[switch]$SkipTests", NAME, "52428800", "Get-FileHash", "-m PyInstaller"):
        assert required in build
    for forbidden in (
        "pytest",
        "verify_drag_source_diff.py",
        "validate_assets.py",
        "validate_dialogue.py",
        "verify_drag_candidate_archive.py",
    ):
        assert forbidden not in build
    assert '$env:PYTHONUTF8 = "1"' in build
    assert '$env:PYTHONIOENCODING = "utf-8"' in build
    assert "[Console]::OutputEncoding" in build
    workflow = Path(".github/workflows/windows-drag-expectation-candidate.yml").read_text(encoding="utf-8")
    for required in ("windows-latest", r".\build_drag_expectation_candidate.ps1 -SkipTests", NAME, "SHA-256", "upload-artifact"):
        assert required in workflow
    assert "pytest" not in workflow.lower()
    assert "build_drag_expectation_preview.py" not in workflow
    assert workflow.count("actions/upload-artifact@") == 1
    assert 'python -m pip install . "PyInstaller>=6,<7"' in workflow
    assert "requirements-assets.txt" not in workflow
    assert '".[dev]"' not in workflow
    assert "codex/-v2.1" in workflow
    assert "fetch-depth" not in workflow

    version_info = Path("desktop_pet_drag_version_info.txt").read_text(
        encoding="utf-8"
    )
    assert "automated tests not run" in version_info
    assert "awaiting user Windows acceptance" in version_info
    assert "Automated tests: NOT RUN" in workflow
    assert "Awaiting user Windows acceptance" in workflow
    assert 'PYTHONUTF8: "1"' in workflow
    assert "PYTHONIOENCODING: utf-8" in workflow


def test_debug_menu_and_docs_name_the_feedback_only_candidate():
    window = Path("src/desktop_pet/window.py").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "调试：拖动期待态" in window
    assert NAME in readme
    assert "不复制、移动、删除、回收、打开、上传或修改文件" in readme

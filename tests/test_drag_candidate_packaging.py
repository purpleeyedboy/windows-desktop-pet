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
    }


def test_drag_candidate_spec_is_onefile_with_exact_name_and_metadata():
    spec = Path("desktop_pet_drag_expectation.spec").read_text(encoding="utf-8")
    assert "COLLECT(" not in spec
    assert "name='桌面宠物_文件拖动期待反馈'" in spec
    assert "DRAG_EXPECTATION_BUILD_INFO.json" in spec
    assert "desktop_pet_drag_version_info.txt" in spec
    assert 'excludes=["numpy", "cv2"]' in spec
    assert "qa" not in spec.lower()


def test_drag_build_and_actions_enforce_tests_unique_exe_size_hash_and_upload():
    build_path = Path("build_drag_expectation_candidate.ps1")
    assert build_path.read_bytes().startswith(codecs.BOM_UTF8)
    build = build_path.read_text(encoding="utf-8-sig")
    for required in ("-m pytest -q", NAME, "52428800", "Get-FileHash", "verify_drag_candidate_archive.py"):
        assert required in build
    workflow = Path(".github/workflows/windows-drag-expectation-candidate.yml").read_text(encoding="utf-8")
    for required in ("windows-latest", "python -m pytest -q", NAME, "SHA-256", "upload-artifact"):
        assert required in workflow
    assert "codex/-v2.1" in workflow


def test_debug_menu_and_docs_name_the_feedback_only_candidate():
    window = Path("src/desktop_pet/window.py").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "调试：拖动期待态" in window
    assert NAME in readme
    assert "不复制、移动、删除、回收、打开、上传或修改文件" in readme

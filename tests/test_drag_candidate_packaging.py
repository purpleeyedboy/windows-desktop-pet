import codecs
import json
from pathlib import Path


NAME = "桌面宠物_期待逐帧与公共基础接入.exe"
FOUNDATION_COMMIT = "77a4f3a90c74c549a66052bebb4b652500e1f7be"


def test_drag_candidate_metadata_is_complete_and_scope_limited():
    metadata = json.loads(Path("DRAG_EXPECTATION_BUILD_INFO.json").read_text(encoding="utf-8"))
    assert metadata == {
        "version": "2.1-expect-frames.2",
        "date": "2026-09-11",
        "git_short_hash": "BUILD_TIME_REQUIRED",
        "foundation_commit": FOUNDATION_COMMIT,
        "baseline": "BASE-001 / V2.1",
        "enabled_features": [
            "approved-v2.1-baseline",
            "common-foundation",
            "expectation-5-real-frames",
            "shared-hunger-preview-gate",
        ],
        "incomplete_features": ["feed-business-handoff-consumer-in-independent-candidate"],
        "test_build": True,
        "debug_menu": True,
        "documentation_baseline": "BASELINE_V2.1.md",
        "file_operations": "none",
        "hunger_changes": "none; shared hunger is read only for preview eligibility",
        "visual_acceptance": "pending",
        "automated_test_status": "windows-ci-lifecycle-and-non-destructive-gates",
        "candidate_status": "pending-windows-build-real-machine-and-visual-review",
    }


def test_drag_candidate_spec_is_onefile_with_exact_name_and_metadata():
    spec = Path("desktop_pet_drag_expectation.spec").read_text(encoding="utf-8")
    assert "COLLECT(" not in spec
    assert "name='桌面宠物_期待逐帧与公共基础接入'" in spec
    assert "DRAG_EXPECTATION_BUILD_INFO.json" in spec
    assert "desktop_pet_drag_version_info.txt" in spec
    assert "DESKTOP_PET_BUILD_INFO" in spec
    assert "DESKTOP_PET_VERSION_INFO" in spec
    assert 'excludes=["numpy", "cv2"]' in spec
    assert "qa" not in spec.lower()


def test_drag_build_and_actions_run_regressions_and_enforce_candidate_artifact_gates():
    build_path = Path("build_drag_expectation_candidate.ps1")
    assert build_path.read_bytes().startswith(codecs.BOM_UTF8)
    build = build_path.read_text(encoding="utf-8-sig")
    for required in ("[switch]$SkipTests", NAME, "52428800", "Get-FileHash", "-m PyInstaller"):
        assert required in build
    for forbidden in (
        "verify_drag_source_diff.py",
        "validate_assets.py",
        "validate_dialogue.py",
        "verify_drag_candidate_archive.py",
    ):
        assert forbidden not in build
    assert '$env:PYTHONUTF8 = "1"' in build
    assert '$env:PYTHONIOENCODING = "utf-8"' in build
    assert "[Console]::OutputEncoding" in build
    assert "git rev-parse --short HEAD" in build
    assert "$BuildInfo.git_short_hash = $GitShortHash" in build
    assert "if (-not $SkipTests)" in build
    workflow = Path(".github/workflows/windows-drag-expectation-candidate.yml").read_text(encoding="utf-8")
    for required in (
        "windows-latest",
        "python -m pytest tests/test_expectation_exit_recovery.py",
        "python tools/verify_drag_runtime.py",
        "python tools/verify_graphic_animation_contract.py",
        r".\build_drag_expectation_candidate.ps1 -SkipTests",
        NAME,
        "SHA-256",
        "upload-artifact",
    ):
        assert required in workflow
    assert "build_drag_expectation_preview.py" not in workflow
    assert workflow.count("actions/upload-artifact@") == 1
    assert 'python -m pip install . "pytest>=8,<9" "PyInstaller>=6,<7"' in workflow
    assert "requirements-assets.txt" not in workflow
    assert '".[dev]"' not in workflow
    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "fetch-depth" not in workflow

    version_info = Path("desktop_pet_drag_version_info.txt").read_text(
        encoding="utf-8"
    )
    assert FOUNDATION_COMMIT in version_info
    assert "Windows lifecycle/non-destructive tests: PASS" in workflow
    assert f"Foundation source: PR #5 {FOUNDATION_COMMIT}" in workflow
    assert 'PYTHONUTF8: "1"' in workflow
    assert "PYTHONIOENCODING: utf-8" in workflow


def test_debug_menu_and_docs_name_the_feedback_only_candidate():
    window = Path("src/desktop_pet/window.py").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    assert 'label="调试"' in window
    expectation_window = Path("src/desktop_pet/expectation_window.py").read_text(encoding="utf-8")
    assert "期待动画预览（3秒，不改变饥饿）" in expectation_window
    assert "停止期待预览" in expectation_window
    assert NAME in readme
    assert "不执行复制、移动、删除、回收、打开、上传或修改文件" in readme

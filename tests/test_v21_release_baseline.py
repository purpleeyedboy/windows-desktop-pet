from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]
EXE_NAME = "桌面宠物_最终素材与转头角度基线修正版.exe"


def test_v21_version_and_reproducible_test_dependencies_are_declared() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == "2.1.0"
    assert set(project["optional-dependencies"]["dev"]) >= {
        "pytest>=8,<9",
        "PyInstaller>=6,<7",
        "numpy>=2.0,<3",
        "opencv-python-headless>=4.10,<5",
    }


def test_v21_pyinstaller_spec_uses_final_name_and_windows_version_file() -> None:
    spec = (ROOT / "desktop_pet_eye_follow.spec").read_text(encoding="utf-8")
    assert "name='桌面宠物_最终素材与转头角度基线修正版'" in spec
    assert "version=str(ROOT / 'version_info.txt')" in spec
    version_info = (ROOT / "version_info.txt").read_text(encoding="utf-8")
    assert "filevers=(2, 1, 0, 0)" in version_info
    assert "prodvers=(2, 1, 0, 0)" in version_info


def test_windows_v21_workflow_builds_hashes_and_uploads_the_unique_exe() -> None:
    workflow = (ROOT / ".github/workflows/windows-approved-assets-preview.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "runs-on: windows-latest" in workflow
    assert 'if ($exes.Count -ne 1)' in workflow
    assert "Get-FileHash" in workflow
    assert EXE_NAME in workflow
    assert "actions/upload-artifact@" in workflow

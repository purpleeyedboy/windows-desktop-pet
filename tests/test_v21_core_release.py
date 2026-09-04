import codecs
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE_NAME = "桌面宠物_V2.1公共基础架构.exe"


def test_core_spec_builds_one_exe_without_offline_tooling():
    spec = (ROOT / "desktop_pet_v21_core.spec").read_text(encoding="utf-8")
    assert "name='桌面宠物_V2.1公共基础架构'" in spec
    assert "COLLECT(" not in spec
    assert 'excludes=["numpy", "cv2"]' in spec
    assert "version=str(ROOT / 'build-v21-core' / 'version_info.txt')" in spec
    for module in ("actions", "config", "persistence", "platform", "sources"):
        assert f'"desktop_pet.foundation.{module}"' in spec


def test_core_build_embeds_required_metadata_and_verifies_unique_hash():
    path = ROOT / "build_v21_core.ps1"
    assert path.read_bytes().startswith(codecs.BOM_UTF8)
    script = path.read_text(encoding="utf-8")
    for required in (
        "2.1.0", "V2.1-CORE", "common-foundation", "Test build: false",
        "Debug menu: false", "BASE-001", "git rev-parse --short HEAD",
        "Get-Date -AsUTC", EXE_NAME, "Get-FileHash", "SHA-256",
    ):
        assert required in script
    assert '$exes.Count -ne 1' in script


def test_windows_core_workflow_builds_and_uploads_only_the_unique_exe():
    workflow = (ROOT / ".github/workflows/windows-v21-core.yml").read_text(encoding="utf-8")
    assert "runs-on: windows-latest" in workflow
    assert "contents: read" in workflow
    assert ".\\build_v21_core.ps1" in workflow
    assert EXE_NAME in workflow
    assert "Get-FileHash" in workflow
    assert "Candidate size" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "secrets." not in workflow.lower()

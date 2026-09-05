from pathlib import Path

from tools.v21_paws_gate import inspect_release_diff, verify_baseline_assets

ROOT = Path(__file__).parents[1]
EXE = "桌面宠物_双前肢按压鼠标.exe"


def test_paws_spec_is_independent_one_file_and_packages_only_feature_assets():
    text = (ROOT / "desktop_pet_paws.spec").read_text(encoding="utf-8")
    assert 'name="桌面宠物_双前肢按压鼠标"' in text
    assert "COLLECT(" not in text
    assert '"assets" / "paws"' in text
    assert "version_info_paws.txt" in text
    build = (ROOT / "build_paws.ps1").read_text(encoding="utf-8")
    assert ".venv" not in build
    assert "-m pytest" not in build
    assert "-m PyInstaller" in build


def test_version_resource_contains_required_traceability():
    text = (ROOT / "version_info_paws.txt").read_text(encoding="utf-8")
    for value in ("2.1.1.0", "BASE-001", "双前肢按压鼠标", "未自动测试候选版",
                  "调试菜单", "BASELINE_V2.1.md", "2026-09-05", "18d921a"):
        assert value in text


def test_windows_action_builds_untested_candidate_and_checks_unique_exe():
    text = (ROOT / ".github/workflows/windows-v21-paws.yml").read_text(encoding="utf-8")
    expected_name = (ROOT / "paws_exe_name.txt").read_text(encoding="utf-8").strip()
    assert "pytest" not in text
    assert ".[dev]" not in text
    assert "build_paws.ps1" in text
    assert 'if ($exes.Count -ne 1)' in text
    assert EXE in text
    assert "Length" in text and "Get-FileHash" in text
    assert "actions/upload-artifact@" in text
    assert "untested-windows-candidate" in text
    assert "pending user Windows acceptance" in text
    assert expected_name == EXE
    inline_powershell = text.split("run: |", 1)[1].split(
        "- uses: actions/upload-artifact@", 1
    )[0]
    assert EXE not in inline_powershell
    assert "Get-Content" in inline_powershell
    assert "-Encoding UTF8" in inline_powershell


def test_release_diff_contains_no_binary_files_and_no_tracked_preview_pngs():
    report = inspect_release_diff(ROOT, "c3b218d")
    assert report.binary_paths == ()
    assert not any(path.startswith("qa/v2.1-paws/") and path.endswith(".png")
                   for path in report.changed_paths)


def test_all_158_baseline_asset_hashes_are_unchanged():
    checked = verify_baseline_assets(ROOT / "assets/v2.1-baseline.sha256", ROOT)
    assert checked == 158

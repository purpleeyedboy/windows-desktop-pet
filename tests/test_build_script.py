import codecs
from pathlib import Path


def test_build_validates_six_direct_archived_keyframes():
    script = Path("build.ps1").read_text(encoding="utf-8")

    assert "--keyframe-root" in script
    assert r"assets\keyframes" in script
    assert "--frame-count 6" in script
    assert "--keyframe-layout direct" in script


def test_build_script_has_utf8_bom_for_windows_powershell_5():
    script_bytes = Path("build.ps1").read_bytes()

    assert script_bytes.startswith(codecs.BOM_UTF8)


def test_pyinstaller_packages_complete_runtime_data_with_release_name():
    spec = Path("desktop_pet.spec").read_text(encoding="utf-8")

    for source, destination in (
        ('"assets" / "keyframes"', '"assets/keyframes"'),
        ('"assets" / "bubble"', '"assets/bubble"'),
        ('"assets" / "fonts"', '"assets/fonts"'),
        ('"assets" / "dialogue"', '"assets/dialogue"'),
        ('"THIRD_PARTY_NOTICES.txt"', '"."'),
    ):
        assert source in spec
        assert destination in spec
    assert '"assets" / "pet"' not in spec
    assert 'name="桌面宠物-6帧猫耳颜文字版"' in spec


def test_build_runs_release_gates_before_pyinstaller_in_required_order():
    script = Path("build.ps1").read_text(encoding="utf-8")

    assets = script.index(r"tools\validate_assets.py")
    dialogue = script.index(r"tools\validate_dialogue.py")
    pytest = script.index("-m pytest")
    pyinstaller = script.index("-m PyInstaller")

    assert assets < dialogue < pytest < pyinstaller
    assert "--basetemp" in script


def test_build_verifies_archive_after_pyinstaller():
    script = Path("build.ps1").read_text(encoding="utf-8")

    build = script.index("-m PyInstaller")
    archive = script.index(r"tools\verify_release_archive.py")

    assert build < archive


def test_build_cleans_only_its_validated_pytest_temp_root_in_finally():
    script = Path("build.ps1").read_text(encoding="utf-8")

    temp_root = script.index("$pytestTempRoot =")
    validation = script.index("$insidePytestTempBase", temp_root)
    create = script.index("New-Item -ItemType Directory -Path $pytestTempRoot", validation)
    try_block = script.index("try {", create)
    core_tests = script.index("-m pytest", try_block)
    finally_block = script.index("finally {", core_tests)
    cleanup = script.index(
        "Remove-Item -LiteralPath $pytestTempRoot -Recurse -Force",
        finally_block,
    )
    pyinstaller = script.index("-m PyInstaller", cleanup)

    assert temp_root < validation < create < try_block
    assert try_block < core_tests < finally_block < cleanup < pyinstaller
    assert "$pytestTempPrefix" in script
    assert "StartsWith(" in script[validation:create]


def test_pyinstaller_spec_builds_exactly_one_file():
    spec = Path("desktop_pet.spec").read_text(encoding="utf-8")

    assert "COLLECT(" not in spec


def test_pyinstaller_excludes_offline_image_tooling():
    spec = Path("desktop_pet.spec").read_text(encoding="utf-8")

    assert 'excludes=["numpy", "cv2"]' in spec

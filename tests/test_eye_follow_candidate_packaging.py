import codecs
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from PyInstaller.archive.writers import CArchiveWriter

from tools import verify_eye_follow_candidate_archive as verifier

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "desktop_pet_eye_follow.spec"
BUILD = ROOT / "build_eye_follow_candidate.ps1"
VERIFIER = ROOT / "tools" / "verify_eye_follow_candidate_archive.py"

CANDIDATE_NAME = "桌面宠物_最终素材与转头角度基线修正版.exe"
RUNTIME_EYE = "assets/rig/v1/runtime/eye-neutral-v1"
SOURCE_EYE = "assets/rig/v1/source/eye-neutral-v1"
EYE_FILES = (
    "authoring.json",
    "body-backplate.png",
    "eye-left-mask.png",
    "eye-left.png",
    "eye-right-mask.png",
    "eye-right.png",
    "head-cutout.png",
    "underlay.png",
)


def test_candidate_spec_is_onefile_and_packages_only_runtime_eye_assets():
    assert SPEC.is_file(), "candidate PyInstaller spec is missing"
    spec = SPEC.read_text(encoding="utf-8")

    assert "onefile" not in spec.lower()  # EXE() without COLLECT is PyInstaller one-file.
    assert "EXE(" in spec
    assert "name='桌面宠物_最终素材与转头角度基线修正版'" in spec
    assert "assets/keyframes" in spec
    assert "assets/bubble" in spec
    assert "assets/fonts" in spec
    assert "assets/dialogue" in spec
    assert "THIRD_PARTY_NOTICES.txt" in spec
    assert SOURCE_EYE in spec
    assert RUNTIME_EYE in spec
    assert (
        "datas.extend((str(EYE_SOURCE / file_name), EYE_RUNTIME) "
        "for file_name in EYE_FILES)"
    ) in spec
    for file_name in EYE_FILES:
        assert file_name in spec
    assert 'excludes=["numpy", "cv2"]' in spec
    assert 'hiddenimports=["PIL._tkinter_finder"]' in spec
    assert "qa" not in spec.lower()
    assert ".gif" not in spec.lower()
    assert "COLLECT(" not in spec


def test_candidate_build_script_uses_isolated_outputs_and_required_gates():
    assert BUILD.is_file(), "candidate build script is missing"
    assert BUILD.read_bytes().startswith(codecs.BOM_UTF8)
    script = BUILD.read_text(encoding="utf-8-sig")

    assert "[switch]$SkipTests" in script
    assert "[switch]$CleanupOnly" in script
    assert ".venv\\Scripts\\python.exe" in script
    assert (
        "tools/validate_assets.py assets/keyframes --keyframe-root assets/keyframes "
        "--frame-count 6 --keyframe-layout direct "
        "--report qa/six-frame-alpha-validation.json"
    ) in script.replace("`\n", "").replace("\\", "/")
    assert "tools/validate_dialogue.py" in script
    assert "-m pytest -q" in script
    assert "dist-eye-follow-candidate" in script
    assert "build-eye-follow-candidate" in script
    assert "desktop_pet_eye_follow.spec" in script
    assert "-noconfirm" in script
    assert CANDIDATE_NAME in script
    assert "verify_eye_follow_candidate_archive.py" in script
    assert str(50 * 1024 * 1024) in script
    assert "Get-FileHash" in script
    assert "build.ps1" not in script
    assert "desktop_pet.spec" not in script


def test_candidate_build_script_configures_tk_and_safely_cleans_reparse_points():
    script = BUILD.read_text(encoding="utf-8-sig")

    base_prefix = '$basePrefix = & $Python -c "import sys; print(sys.base_prefix)"'
    tcl = "$env:TCL_LIBRARY = Join-Path $basePrefix 'tcl\\tcl8.6'"
    tk = "$env:TK_LIBRARY = Join-Path $basePrefix 'tcl\\tk8.6'"
    assert base_prefix in script
    assert "Failed to resolve Python base prefix" in script
    assert tcl in script
    assert tk in script
    assert script.index(base_prefix) < script.index(tcl) < script.index("tools\\validate_assets.py")
    assert script.index(base_prefix) < script.index(tk) < script.index("-m PyInstaller")

    assert "[IO.FileAttributes]::ReparsePoint" in script
    assert not re.search(r"(?im)^\s*Remove-Item\b[^\r\n]*\b-Recurse\b", script)
    assert "Get-ChildItem -LiteralPath $Path -Force" in script
    assert "Remove-CandidateOutput $child.FullName" in script
    assert "[IO.Directory]::Delete($Path, $false)" in script
    assert "if ($item.PSIsContainer)" in script


@pytest.mark.skipif(os.name != "nt", reason="requires a real Windows junction")
def test_candidate_cleanup_does_not_traverse_a_nested_windows_junction(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    script = repository / BUILD.name
    script.write_bytes(BUILD.read_bytes())

    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_text("must survive", encoding="utf-8")

    dist = repository / "dist-eye-follow-candidate"
    nested = dist / "ordinary" / "nested"
    nested.mkdir(parents=True)
    (nested / "candidate.tmp").write_text("candidate", encoding="utf-8")
    junction = nested / "external-junction"
    junction_result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(external)],
        capture_output=True,
        text=True,
    )
    assert junction_result.returncode == 0, junction_result.stderr or junction_result.stdout

    work = repository / "build-eye-follow-candidate"
    work.mkdir()
    (work / "build.tmp").write_text("build", encoding="utf-8")

    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    assert powershell is not None, "PowerShell is required on the hosted Windows runner"
    cleanup = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-CleanupOnly",
        ],
        capture_output=True,
        text=True,
    )

    assert cleanup.returncode == 0, cleanup.stderr or cleanup.stdout
    assert not dist.exists()
    assert not work.exists()
    assert sentinel.read_text(encoding="utf-8") == "must survive"


def test_archive_verifier_enforces_the_candidate_archive_contract():
    assert VERIFIER.is_file(), "candidate archive verifier is missing"
    verifier = VERIFIER.read_text(encoding="utf-8")

    assert "CArchiveReader" in verifier
    assert "assets/keyframes" in verifier
    assert "assets/bubble" in verifier
    assert "assets/fonts" in verifier
    assert "assets/dialogue" in verifier
    assert "THIRD_PARTY_NOTICES.txt" in verifier
    assert SOURCE_EYE in verifier
    assert RUNTIME_EYE in verifier
    for file_name in EYE_FILES:
        assert file_name in verifier
    assert "neutral-eye {len(eyes)}" in verifier
    assert ".gif" in verifier
    assert "byte" in verifier.lower()


def test_archive_verifier_allows_tk_runtime_gif_but_rejects_project_gifs():
    verifier.validate_forbidden_paths({"_tk_data/images/logoLarge.gif"})

    with pytest.raises(verifier.VerificationError, match="forbidden GIF archive path"):
        verifier.validate_forbidden_paths({"assets/bubble/preview.gif"})


def test_archive_verifier_compares_all_resource_bytes_and_rejects_forbidden_paths(
    tmp_path, monkeypatch, capsys
):
    source_root = tmp_path / "project"
    monkeypatch.setattr(verifier, "ROOT", source_root)

    sources = {
        "assets/keyframes/shake/00.png": b"keyframe",
        "assets/bubble/frame.png": b"bubble",
        "assets/fonts/font.ttf": b"font",
        "assets/dialogue/lines.json": b"dialogue",
        "THIRD_PARTY_NOTICES.txt": b"notices",
    }
    for eye_name in EYE_FILES:
        sources[f"{SOURCE_EYE}/{eye_name}"] = f"eye:{eye_name}".encode()
    for name, contents in sources.items():
        path = source_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    entries = []
    for name in sorted(sources):
        archive_member = name.replace(SOURCE_EYE, RUNTIME_EYE)
        entries.append((archive_member, str(source_root / name), True, "x"))
    executable = tmp_path / "candidate.exe"
    CArchiveWriter(str(executable), entries, "libpython3.12.so")

    verifier.verify_archive(executable)
    assert "neutral-eye 8" in capsys.readouterr().out

    (source_root / "assets/keyframes/shake/00.png").write_bytes(b"changed")
    with pytest.raises(verifier.VerificationError, match="byte mismatch"):
        verifier.verify_archive(executable)

    forbidden = tmp_path / "candidate-with-gif.exe"
    gif_source = tmp_path / "evidence.gif"
    gif_source.write_bytes(b"gif")
    CArchiveWriter(
        str(forbidden),
        entries + [("qa/evidence.gif", str(gif_source), True, "x")],
        "libpython3.12.so",
    )
    with pytest.raises(verifier.VerificationError, match="forbidden QA archive path"):
        verifier.verify_archive(forbidden)

    extra_eye_source = tmp_path / "extra.png"
    extra_eye_source.write_bytes(b"extra")
    extra_runtime = tmp_path / "candidate-with-extra-eye.exe"
    CArchiveWriter(
        str(extra_runtime),
        entries + [(f"{RUNTIME_EYE}/extra.png", str(extra_eye_source), True, "x")],
        "libpython3.12.so",
    )
    with pytest.raises(verifier.VerificationError, match="unexpected neutral-eye runtime"):
        verifier.verify_archive(extra_runtime)


def test_archive_verifier_normalizes_windows_member_names_and_rejects_collisions(
    tmp_path, monkeypatch, capsys
):
    source_root = tmp_path / "project"
    monkeypatch.setattr(verifier, "ROOT", source_root)
    sources = {
        "assets/keyframes/shake/00.png": b"keyframe",
        "assets/bubble/frame.png": b"bubble",
        "assets/fonts/font.ttf": b"font",
        "assets/dialogue/lines.json": b"dialogue",
        "THIRD_PARTY_NOTICES.txt": b"notices",
    }
    for eye_name in EYE_FILES:
        sources[f"{SOURCE_EYE}/{eye_name}"] = f"eye:{eye_name}".encode()
    for name, contents in sources.items():
        path = source_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    entries = []
    for name in sorted(sources):
        archive_member = name.replace(SOURCE_EYE, RUNTIME_EYE).replace("/", "\\")
        entries.append((archive_member, str(source_root / name), True, "x"))
    windows_archive = tmp_path / "windows-member-names.exe"
    CArchiveWriter(str(windows_archive), entries, "libpython3.12.so")

    verifier.verify_archive(windows_archive)
    assert "neutral-eye 8" in capsys.readouterr().out

    with pytest.raises(verifier.VerificationError, match="normalized archive path collision"):
        verifier.normalized_archive_members(
            [
                r"assets\keyframes\shake\00.png",
                "assets/keyframes/shake/00.png",
            ]
        )


def test_archive_verifier_wraps_source_read_errors(tmp_path, monkeypatch):
    source_root = tmp_path / "project"
    monkeypatch.setattr(verifier, "ROOT", source_root)
    sources = {
        "assets/keyframes/shake/00.png": b"keyframe",
        "assets/bubble/frame.png": b"bubble",
        "assets/fonts/font.ttf": b"font",
        "assets/dialogue/lines.json": b"dialogue",
        "THIRD_PARTY_NOTICES.txt": b"notices",
    }
    for eye_name in EYE_FILES:
        sources[f"{SOURCE_EYE}/{eye_name}"] = f"eye:{eye_name}".encode()
    for name, contents in sources.items():
        path = source_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    entries = [
        (
            name.replace(SOURCE_EYE, RUNTIME_EYE),
            str(source_root / name),
            True,
            "x",
        )
        for name in sorted(sources)
    ]
    executable = tmp_path / "source-read-error.exe"
    CArchiveWriter(str(executable), entries, "libpython3.12.so")

    failed_source = source_root / "assets/keyframes/shake/00.png"
    original_read_bytes = Path.read_bytes

    def read_bytes_with_failure(path):
        if path == failed_source:
            raise OSError("simulated source read failure")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes_with_failure)
    with pytest.raises(
        verifier.VerificationError,
        match="source read error for assets/keyframes/shake/00.png",
    ):
        verifier.verify_archive(executable)

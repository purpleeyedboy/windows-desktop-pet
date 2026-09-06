# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from datetime import date
import json
import subprocess


ROOT = Path(SPECPATH).resolve()
GENERATED = ROOT / "build" / "paws-release"
GENERATED.mkdir(parents=True, exist_ok=True)
try:
    GIT_COMMIT = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
except (OSError, subprocess.CalledProcessError):
    GIT_COMMIT = "unknown"
IDENTITY = GENERATED / "build_identity.json"
IDENTITY.write_text(json.dumps({
    "version": "V2.1-PAWS REPAIR-20260906",
    "git_commit": GIT_COMMIT,
    "foundation_commit": "pending PR5 integration",
    "build_date": date.today().isoformat(),
    "features": ["dual forepaw press", "bounded cursor push"],
    "acceptance": "NOT ACCEPTED - user Windows validation and foundation integration pending",
}, ensure_ascii=False), encoding="utf-8")
EYE_SOURCE = ROOT / "assets/rig/v1/source/eye-neutral-v1"
EYE_RUNTIME = "assets/rig/v1/runtime/eye-neutral-v1"
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

datas = [
    (str(ROOT / "assets" / "keyframes"), "assets/keyframes"),
    (str(ROOT / "assets" / "bubble"), "assets/bubble"),
    (str(ROOT / "assets" / "fonts"), "assets/fonts"),
    (str(ROOT / "assets" / "dialogue"), "assets/dialogue"),
    (str(ROOT / "THIRD_PARTY_NOTICES.txt"), "."),
    (str(IDENTITY), "."),
]
datas.extend((str(EYE_SOURCE / file_name), EYE_RUNTIME) for file_name in EYE_FILES)
datas.append((str(ROOT / "assets" / "paws"), "assets/paws"))

a = Analysis(
    [str(ROOT / "run_desktop_pet.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "cv2"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="桌面宠物_双前肢按压鼠标_20260906修复候选",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(ROOT / 'version_info_paws.txt'),
)

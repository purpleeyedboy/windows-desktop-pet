# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


ROOT = Path(SPECPATH).resolve()
EYE_SOURCE = ROOT / "assets/rig/v1/source/eye-neutral-v1"
EYE_RUNTIME = "assets/rig/v1/runtime/eye-neutral-v1"
EYE_FILES = (
    "authoring.json",
    "body-backplate.png",
    "eye-left-mask.png",
    "eye-left.png",
    "eye-right-mask.png",
    "eye-right.png",
    "underlay.png",
)

datas = [
    (str(ROOT / "assets" / "keyframes"), "assets/keyframes"),
    (str(ROOT / "assets" / "bubble"), "assets/bubble"),
    (str(ROOT / "assets" / "fonts"), "assets/fonts"),
    (str(ROOT / "assets" / "dialogue"), "assets/dialogue"),
    (str(ROOT / "THIRD_PARTY_NOTICES.txt"), "."),
]
datas.extend((str(EYE_SOURCE / file_name), EYE_RUNTIME) for file_name in EYE_FILES)

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
    name='桌面宠物-自然跟随候选版',
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
)

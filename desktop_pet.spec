# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path.cwd()

a = Analysis(
    [str(PROJECT_ROOT / "run_desktop_pet.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "assets" / "keyframes"), "assets/keyframes"),
        (str(PROJECT_ROOT / "assets" / "bubble"), "assets/bubble"),
        (str(PROJECT_ROOT / "assets" / "fonts"), "assets/fonts"),
        (str(PROJECT_ROOT / "assets" / "dialogue"), "assets/dialogue"),
        (str(PROJECT_ROOT / "THIRD_PARTY_NOTICES.txt"), "."),
    ],
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "cv2"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="桌面宠物-6帧猫耳气泡版",
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

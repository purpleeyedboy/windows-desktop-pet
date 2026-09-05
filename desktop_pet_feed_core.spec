# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os

ROOT = Path.cwd()
FEED_CORE_HIDDEN_IMPORTS = [
    "desktop_pet.feed_core.model",
    "desktop_pet.feed_core.validation",
    "desktop_pet.feed_core.journal",
    "desktop_pet.feed_core.coordinator",
    "desktop_pet.feed_core.adapters",
    "desktop_pet.feed_core.simulation",
    "desktop_pet.feed_core.windows_recycle",
]
a = Analysis(
    [str(ROOT / "run_feed_core.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(os.environ.get("DESKTOP_PET_FEED_BUILD_INFO", str(ROOT / "BUILD_INFO_FEED_CORE.json")), ".")],
    hiddenimports=FEED_CORE_HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "cv2"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="桌面宠物_文件喂食与回收站事务",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False,
)

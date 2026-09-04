# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
ROOT=Path.cwd()
a=Analysis([str(ROOT/'run_feed_core.py')],pathex=[str(ROOT/'src')],binaries=[],datas=[(os.environ.get('DESKTOP_PET_FEED_BUILD_INFO',str(ROOT/'BUILD_INFO_FEED_CORE.json')),'.')],hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['numpy','cv2'],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='桌面宠物_文件喂食与回收站事务',debug=False,bootloader_ignore_signals=False,strip=False,upx=True,console=False)

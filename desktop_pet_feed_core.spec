# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
ROOT=Path(SPECPATH).resolve()
EYE_SOURCE=ROOT/'assets/rig/v1/source/eye-neutral-v1'; EYE_RUNTIME='assets/rig/v1/runtime/eye-neutral-v1'
EYE_FILES=('authoring.json','body-backplate.png','eye-left-mask.png','eye-left.png','eye-right-mask.png','eye-right.png','head-cutout.png','underlay.png')
datas=[(str(ROOT/'assets/keyframes'),'assets/keyframes'),(str(ROOT/'assets/bubble'),'assets/bubble'),(str(ROOT/'assets/fonts'),'assets/fonts'),(str(ROOT/'assets/dialogue'),'assets/dialogue'),(str(ROOT/'THIRD_PARTY_NOTICES.txt'),'.'),(os.environ.get('DESKTOP_PET_FEED_BUILD_INFO',str(ROOT/'BUILD_INFO_FEED_CORE.json')),'.')]
datas.extend((str(EYE_SOURCE/name),EYE_RUNTIME) for name in EYE_FILES)
hiddenimports=['PIL._tkinter_finder','desktop_pet.feed_core.model','desktop_pet.feed_core.validation','desktop_pet.feed_core.journal','desktop_pet.feed_core.coordinator','desktop_pet.feed_core.adapters','desktop_pet.feed_core.wiring','desktop_pet.feed_core.windows_drop','desktop_pet.feed_core.windows_recycle']
a=Analysis([str(ROOT/'run_desktop_pet.py')],pathex=[str(ROOT/'src')],binaries=[],datas=datas,hiddenimports=hiddenimports,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['numpy','cv2'],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='桌面宠物_文件喂食与回收站事务',debug=False,bootloader_ignore_signals=False,strip=False,upx=True,console=False,version=str(ROOT/'version_info_feed_core.txt'))

# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPECPATH).resolve()
datas = [(str(ROOT / name), name) for name in (
    'assets/keyframes', 'assets/bubble', 'assets/fonts', 'assets/dialogue',
    'assets/hunger/v1', 'assets/expectation/runtime',
    'assets/groom/v2.1/runtime', 'assets/groom/v2.1/runtime-right',
)]
datas += [
    (str(ROOT / 'assets/generated/work/feed/v1'), 'assets/feed/v1/frames'),
    (str(ROOT / 'build/integrated/build_identity.json'), '.'),
    (str(ROOT / 'THIRD_PARTY_NOTICES.txt'), '.'),
]
for name in ('ear_asset_manifest.json', 'ear_keyframes.json'):
    datas.append((str(ROOT / 'src/desktop_pet' / name), 'desktop_pet'))
for name in ('authoring.json', 'generated-frames.json'):
    datas.append((str(ROOT / 'assets/paws/v1' / name), 'assets/paws/v1'))
for name in ('authoring.json', 'body-backplate.png', 'eye-left-mask.png', 'eye-left.png',
             'eye-right-mask.png', 'eye-right.png', 'head-cutout.png', 'underlay.png'):
    datas.append((str(ROOT / 'assets/rig/v1/source/eye-neutral-v1' / name),
                  'assets/rig/v1/runtime/eye-neutral-v1'))

a = Analysis([str(ROOT / 'run_integrated_pet.py')], pathex=[str(ROOT / 'src')],
             binaries=[], datas=datas, hiddenimports=['PIL._tkinter_finder'],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['numpy', 'cv2'],
             noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='桌面宠物_全部功能合并测试版_20260915', console=False,
          debug=False, strip=False, upx=False,
          manifest=str(ROOT / 'desktop_pet_v21_core.manifest'))

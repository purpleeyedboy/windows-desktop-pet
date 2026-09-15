"""Verify the shipped EXE's modules, feature identity and exact resource bytes."""
import json
from pathlib import Path
import sys

from PyInstaller.archive.readers import CArchiveReader
from verify_eye_follow_candidate_archive import verify_archive
from verify_feed_core_archive import archived_python_modules, missing_required_modules

ROOT = Path(__file__).resolve().parents[1]


def main():
    executable = Path(sys.argv[1])
    verify_archive(executable)
    archive = CArchiveReader(str(executable))
    members = {name.replace('\\', '/'): name for name in archive.toc}
    resources = {'build_identity.json': ROOT / 'build/integrated/build_identity.json'}
    for source, target in (
        ('assets/hunger/v1', 'assets/hunger/v1'),
        ('assets/expectation/runtime', 'assets/expectation/runtime'),
        ('assets/generated/work/feed/v1', 'assets/feed/v1/frames'),
        ('assets/groom/v2.1/runtime', 'assets/groom/v2.1/runtime'),
        ('assets/groom/v2.1/runtime-right', 'assets/groom/v2.1/runtime-right'),
    ):
        for path in (ROOT / source).rglob('*'):
            if path.is_file():
                resources[target + '/' + path.relative_to(ROOT / source).as_posix()] = path
    for name in ('ear_asset_manifest.json', 'ear_keyframes.json'):
        resources['desktop_pet/' + name] = ROOT / 'src/desktop_pet' / name
    for name in ('authoring.json', 'generated-frames.json'):
        resources['assets/paws/v1/' + name] = ROOT / 'assets/paws/v1' / name
    for name, path in resources.items():
        if name not in members or archive.extract(members[name]) != path.read_bytes():
            raise RuntimeError('Missing or mismatched integrated resource: ' + name)
    modules = archived_python_modules(executable)
    required = ('integrated_main', 'integrated_window', 'ear_interaction', 'paw_press',
                'win32_pointer', 'groom_adapter', 'groom_frames', 'hunger_graphic_runtime',
                'hunger_window', 'drag_runtime', 'expectation_window')
    missing = missing_required_modules(modules)
    missing.extend('desktop_pet.' + name for name in required if 'desktop_pet.' + name not in modules)
    if missing:
        raise RuntimeError(f'Missing integrated Python modules: {missing}')
    identity = json.loads(archive.extract(members['build_identity.json']))
    if len(identity['enabled_features']) != 7:
        raise RuntimeError('Incorrect integrated identity')
    print(f'PASS: all integrated modules and {len(resources)} exact feature resources')


if __name__ == '__main__':
    main()

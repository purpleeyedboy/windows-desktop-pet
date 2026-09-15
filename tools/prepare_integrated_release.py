"""Rebuild existing approved feature sources and record the integrated identity."""
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from desktop_pet.integrated_main import INTEGRATED_FEATURES

SOURCES = {
    'common-foundation': '38caa9a674763111664dc7b05c40768b049fbd3f',
    'ears': 'a997b1e891ae602374611b69c8857b8a702ce114',
    'paws': 'd037802b1797092c37114a20c0c6b1566aa45d98',
    'hunger': '6b3dd5e938a1203b1319df8820e6970f4c6d60ee',
    'groom': '27b0ae3bf2616559b3d27fa4f922822b121f7621',
    'drag-expectation': '553057c5d1cef21c75b545cb3be51fde488dc746',
    'feed': '8f72e804dbbc26b7e22f66ecf6c8fcc4c9d3797a',
}


def build_identity(commit):
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('full Git SHA required')
    return dict(product_version='2.1.4-integrated', build_date=date.today().isoformat(),
                git_short_hash=commit[:8], git_commit=commit,
                foundation_commit=SOURCES['common-foundation'],
                enabled_features=list(INTEGRATED_FEATURES), source_commits=SOURCES,
                test_build=True, debug_enabled=True, debug_menu_enabled=True,
                windows_desktop_acceptance='pending-user-validation')


def verify_baseline():
    records = (ROOT / 'assets/v2.1-baseline.sha256').read_text('utf-8').splitlines()
    count = 0
    for line in records:
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Approved asset changed: {name}')
        count += 1
    if count != 158:
        raise ValueError(f'Expected 158 approved assets, found {count}')
    return count


def main():
    verify_baseline()
    commands = [
        ['tools/build_expectation_assets.py'], ['tools/build_feed_frames.py'],
        ['scripts/build_hunger_assets.py'],
        ['tools/import_groom_frames.py', '--output', 'assets/groom/v2.1/runtime'],
        ['tools/import_groom_frames.py', '--manifest', 'assets/groom/v2.1/manifest-right.json',
         '--output', 'assets/groom/v2.1/runtime-right'],
    ]
    for command in commands:
        subprocess.run([sys.executable, *command], cwd=ROOT, check=True)
    verify_baseline()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    destination = ROOT / 'build/integrated'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'build_identity.json').write_text(
        json.dumps(build_identity(commit), ensure_ascii=False, indent=2), encoding='utf-8')
    print('Prepared all seven features; 158 immutable baseline assets verified.')


if __name__ == '__main__':
    main()

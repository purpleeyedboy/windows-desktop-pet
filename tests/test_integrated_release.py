from pathlib import Path
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]


def release_module():
    path = ROOT / 'tools/prepare_integrated_release.py'
    assert path.is_file(), 'integrated reproducible release preparation is missing'
    spec = importlib.util.spec_from_file_location('integrated_release', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_identity_names_every_feature_and_keeps_acceptance_pending():
    module = release_module()
    identity = module.build_identity('a' * 40)
    assert set(identity['enabled_features']) == {
        'common-foundation', 'ears', 'paws', 'groom', 'hunger', 'drag-expectation', 'feed'}
    assert identity['windows_desktop_acceptance'] == 'pending-user-validation'
    assert identity['git_commit'] == 'a' * 40
    assert len(identity['source_commits']) == 7


def test_integrated_spec_uses_one_real_entrypoint_and_all_frame_families():
    path = ROOT / 'desktop_pet_integrated.spec'
    assert path.is_file(), 'integrated EXE specification is missing'
    source = path.read_text('utf-8')
    assert 'run_integrated_pet.py' in source
    assert 'desktop_pet_v21_core.manifest' in source
    for family in ('ear_keyframes.json', 'assets/paws/v1', 'assets/hunger/v1',
                   'assets/expectation/runtime', 'assets/feed/v1/frames',
                   'assets/groom/v2.1/runtime', 'assets/groom/v2.1/runtime-right'):
        assert family in source


def test_all_approved_baseline_assets_are_byte_identical():
    assert release_module().verify_baseline() == 158

import json
from pathlib import Path

def test_build_info_marks_high_risk_untested_real_candidate():
    info=json.loads(Path('BUILD_INFO_FEED_CORE.json').read_text(encoding='utf-8'))
    assert info['base_label']=='V2.1-FEED-CORE'
    assert info['test_build'] is True and info['automated_test_gate'] is False
    assert info['features']['real_user_confirmed_feed'] is True
    assert info['acceptance']=='pending_user_windows_acceptance_high_risk'

def test_spec_packages_real_desktop_entry_and_all_feed_modules():
    spec=Path('desktop_pet_feed_core.spec').read_text(encoding='utf-8')
    assert 'run_desktop_pet.py' in spec and 'run_feed_core.py' not in spec
    for name in ('model','validation','journal','coordinator','wiring','windows_drop','windows_recycle'):
        assert f'desktop_pet.feed_core.{name}' in spec
    assert 'assets/keyframes' in spec and 'assets/bubble' in spec

def test_workflow_skips_pytest_and_verifies_unique_candidate():
    workflow=Path('.github/workflows/windows-feed-core.yml').read_text(encoding='utf-8')
    assert 'pytest' not in workflow
    assert 'compileall' in workflow and 'verify_feed_core_archive.py' in workflow
    assert '桌面宠物_文件喂食与回收站事务.exe' in workflow
    assert 'SHA256' in workflow and 'upload-artifact' in workflow

def test_archive_verifier_requires_runtime_wiring():
    from tools.verify_feed_core_archive import missing_required_modules
    required={f'desktop_pet.feed_core.{n}' for n in ('model','validation','journal','coordinator','adapters','wiring','windows_drop','windows_recycle')}
    assert missing_required_modules(required)==[]

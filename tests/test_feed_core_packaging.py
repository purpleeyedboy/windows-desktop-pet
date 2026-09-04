import json
from pathlib import Path

def test_build_info_is_truthful_and_versioned():
    info=json.loads(Path('BUILD_INFO_FEED_CORE.json').read_text(encoding='utf-8'))
    assert info['version']=='2.1.0' and info['date']=='2026-09-04'
    assert info['base_label']=='V2.1-FEED-CORE'
    assert info['features']['ifileoperation_recycle'] is True
    assert info['features']['drop']=='fake_adapter' and info['features']['hunger_reward']=='idempotent_fake'
    assert info['test_build'] is True and info['debug_menu'] is False
    assert info['documentation_baseline']=='BASE-001'

def test_spec_and_workflow_exact_unique_exe_contract():
    spec=Path('desktop_pet_feed_core.spec').read_text(encoding='utf-8')
    build=Path('build_feed_core.ps1').read_text(encoding='utf-8-sig')
    workflow=Path('.github/workflows/windows-feed-core.yml').read_text(encoding='utf-8')
    expected='桌面宠物_文件喂食与回收站事务.exe'
    assert '桌面宠物_文件喂食与回收站事务' in spec
    for text in (build,workflow):
        assert expected in text and 'SHA256' in text and 'Count -ne 1' in text
    assert 'Get-Command python' in build
    assert 'git rev-parse --short HEAD' in build
    assert 'DESKTOP_PET_FEED_BUILD_INFO' in spec
    assert 'python -m pytest' in build and 'python -m pytest' in workflow
    assert 'size' in workflow.lower() and 'upload-artifact' in workflow

def test_real_e2e_is_opt_in_and_temp_scoped():
    text=Path('tests/test_feed_core_ifileoperation_e2e.py').read_text(encoding='utf-8')
    assert 'DESKTOP_PET_RUN_RECYCLE_E2E' in text and 'TemporaryDirectory' in text

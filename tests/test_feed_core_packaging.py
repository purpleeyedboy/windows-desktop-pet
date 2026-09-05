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

def test_real_e2e_is_absent_and_cannot_be_enabled():
    assert not Path('tests/test_feed_core_ifileoperation_e2e.py').exists()
    assert 'DESKTOP_PET_RUN_RECYCLE_E2E' not in Path('.github/workflows/windows-feed-core.yml').read_text(encoding='utf-8')

def test_candidate_entrypoint_imports_and_runs_safe_simulation():
    source=Path('run_feed_core.py').read_text(encoding='utf-8')
    assert 'desktop_pet.feed_core.simulation' in source
    assert '--self-test' in source and 'SIMULATION' in source
    assert 'askopenfilename' not in source and 'register_drop_target' not in source

def test_frozen_build_explicitly_collects_and_verifies_feed_core():
    spec=Path('desktop_pet_feed_core.spec').read_text(encoding='utf-8')
    build=Path('build_feed_core.ps1').read_text(encoding='utf-8-sig')
    workflow=Path('.github/workflows/windows-feed-core.yml').read_text(encoding='utf-8')
    required=('model','validation','journal','coordinator','adapters','simulation','windows_recycle')
    for module in required:
        assert f'desktop_pet.feed_core.{module}' in spec
    assert 'verify_feed_core_archive.py' in build and '--self-test' in build
    assert 'open_embedded_archive' in Path('tools/verify_feed_core_archive.py').read_text(encoding='utf-8')
    assert 'verify_feed_core_archive.py' in workflow and '--self-test' in workflow

def test_archive_verifier_detects_missing_core_modules():
    from tools.verify_feed_core_archive import missing_required_modules
    present={f'desktop_pet.feed_core.{name}' for name in ('model','validation','journal','coordinator','adapters','simulation','windows_recycle')}
    assert missing_required_modules(present)==[]
    assert missing_required_modules(present-{'desktop_pet.feed_core.journal'})==['desktop_pet.feed_core.journal']

def test_source_candidate_can_write_headless_simulation_report(tmp_path):
    import run_feed_core
    report=tmp_path/'report.json'
    assert run_feed_core.main(['--self-test-output',str(report)])==0
    payload=json.loads(report.read_text(encoding='utf-8'))
    assert payload['mode']=='SIMULATION' and payload['source_still_exists'] is True

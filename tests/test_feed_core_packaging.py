from pathlib import Path

def test_repair_packages_only_foundation_adapter_and_blocks_without_handler():
    spec=Path("desktop_pet_feed_core.spec").read_text(encoding="utf-8")
    gate=Path("tools/check_feed_foundation_gate.py").read_text(encoding="utf-8")
    assert "foundation_contract" in spec and "windows_drop" in spec
    assert "foundation_feed_ready" in gate
    assert "ProgressSink FEED handler" in gate

def test_repaired_candidate_name_and_no_pytest_gate():
    workflow=Path(".github/workflows/windows-feed-core.yml").read_text(encoding="utf-8")
    build=Path("build_feed_core.ps1").read_text(encoding="utf-8-sig")
    assert "桌面宠物_文件喂食与回收站事务修复.exe" in workflow
    assert "pytest" not in workflow and "pytest" not in build

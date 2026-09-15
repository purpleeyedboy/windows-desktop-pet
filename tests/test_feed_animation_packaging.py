from pathlib import Path

from tools.verify_feed_core_archive import missing_required_modules, missing_required_resources


CANDIDATE = "桌面宠物_文件进食动画恢复候选.exe"


def test_build_reconstructs_frames_and_uses_independent_candidate_name():
    build = Path("build_feed_core.ps1").read_text(encoding="utf-8-sig")
    assert "tools\\build_feed_frames.py" in build
    assert CANDIDATE in build
    assert "pytest" not in build


def test_spec_packages_real_generated_frames_not_source_or_base64_duplicates():
    spec = Path("desktop_pet_feed_core.spec").read_text(encoding="utf-8")
    assert "assets/generated/work/feed/v1" in spec
    assert "assets/feed/v1/frames" in spec
    assert "feed-color.png" not in spec
    assert "base64" not in spec.lower()
    assert "desktop_pet.feed_animation" in spec


def test_archive_gate_requires_player_module_and_all_six_real_frames():
    modules = {
        "desktop_pet.feed_core.foundation_contract",
        "desktop_pet.feed_core.business",
        "desktop_pet.feed_core.progress_receipt",
        "desktop_pet.feed_core.confirmation",
        "desktop_pet.feed_core.recovery",
        "desktop_pet.feed_core.review",
        "desktop_pet.feed_core.windows_identity",
        "desktop_pet.feed_core.windows_recycle",
        "desktop_pet.feed_core.wiring",
        "desktop_pet.feed_core.windows_drop",
        "desktop_pet.feed_animation",
    }
    resources = {f"assets/feed/v1/frames/{index:02d}.png" for index in range(6)}
    assert missing_required_modules(modules) == []
    assert missing_required_resources(resources) == []
    assert missing_required_resources(set()) == sorted(resources)


def test_workflow_uploads_only_the_new_candidate():
    workflow = Path(".github/workflows/windows-feed-core.yml").read_text(encoding="utf-8")
    assert CANDIDATE in workflow
    assert "desktop-pet-v2.1-feed-animation-recovery" in workflow


def test_generated_frames_and_preview_are_ignored():
    ignored = Path(".gitignore").read_text(encoding="utf-8").splitlines()
    assert "assets/generated/work/feed/" in ignored


def test_reviewable_source_is_one_text_bundle_not_tracked_pngs():
    attributes = Path(".gitattributes").read_text(encoding="utf-8")
    assert "feed-sources.base64.txt text eol=lf" in attributes
    source_files = sorted(Path("assets/feed/v1/source").iterdir())
    assert [path.name for path in source_files] == ["feed-sources.base64.txt"]

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_build_records_pull_request_source_head_not_merge_commit() -> None:
    workflow = (ROOT / ".github/workflows/windows-idle-lick-candidate.yml").read_text()
    script = (ROOT / "build_idle_lick_candidate.ps1").read_text(encoding="utf-8-sig")

    assert "SOURCE_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "$env:SOURCE_HEAD_SHA" in script
    assert "git_short_hash = $SourceShortHash" in script

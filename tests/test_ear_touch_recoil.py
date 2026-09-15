from pathlib import Path
from desktop_pet.ear_interaction import EAR_KEYFRAMES, EarFeatureAdapter, EarRasterPose


def test_each_ear_recoils_once_and_returns_in_one_second():
    for sequence in EAR_KEYFRAMES.values():
        frames = sequence.frames
        assert sum(frame.duration_ms for frame in frames) == 1000
        angles = [abs(frame.angle_degrees) for frame in frames]
        peak = angles.index(max(angles))
        assert angles[:peak + 1] == sorted(angles[:peak + 1])
        assert angles[peak:] == sorted(angles[peak:], reverse=True)
        assert frames[-1].frame_id == 'neutral-end'
        assert sum(frame.duration_ms for frame in frames[:peak]) <= 200


def test_completed_click_can_replay_immediately_without_auto_repeat():
    pending, completed = [], []
    adapter = EarFeatureAdapter(
        lambda delay, callback: pending.append(callback), lambda _: None,
        lambda: 0.0, lambda *_: None, lambda *args: completed.append(args),
    )
    assert adapter.start_approved('left', 'first')
    assert not adapter.start_approved('right', 'ignored')
    while pending:
        pending.pop(0)()
    assert completed == [('first', True)]
    assert not adapter.active
    assert adapter.start_approved('right', 'second')


def test_stale_timer_after_interruption_cannot_advance_new_click():
    pending, rendered = [], []
    adapter = EarFeatureAdapter(
        lambda delay, callback: pending.append(callback), lambda _: None,
        lambda: 0.0, lambda *args: rendered.append(args), lambda *_: None,
    )
    adapter.start_approved('left', 'first')
    stale = pending.pop()
    assert adapter.cancel_active()
    assert rendered[-1] == ('left', EarRasterPose())
    assert adapter.start_approved('right', 'second')
    count = len(rendered)
    stale()
    assert len(rendered) == count
    assert adapter.active


def test_release_filename_is_consistent_across_packaging_and_smoke_check():
    root = Path(__file__).resolve().parents[1]
    stem = '桌面宠物_耳朵防触摸系统_单次躲闪-20260910'
    for name in ('build_ears_candidate.ps1', 'desktop_pet_ears.spec',
                 'version_info_ears.txt', 'tools/smoke_test_ears_candidate.ps1',
                 '.github/workflows/windows-ears-candidate.yml'):
        assert stem in (root / name).read_text(encoding='utf-8-sig')

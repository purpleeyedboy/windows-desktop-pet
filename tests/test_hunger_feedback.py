from desktop_pet.hunger_feedback import HungerFeedback, CORPUS, bar_color, motion
from desktop_pet.hunger_window import HungerWindow


def test_thresholds_are_value_driven_not_time_driven():
    f = HungerFeedback()
    assert f.update(100000) is None
    assert f.update(21000) is None
    assert f.update(20000) == 'mild'
    assert f.update(20000) is None
    assert f.update(19000) is None
    assert f.update(18000) == 'mild'
    assert f.update(10000) == 'mild'
    assert f.update(9999) == 'severe'
    assert f.update(8000) == 'severe'
    assert f.update(2000) == 'severe'
    assert f.update(1000) is None
    assert f.update(999) == 'critical'
    assert f.update(0) is None
    assert f.critical
    f.update(1000)
    assert not f.critical


def test_refeeding_rearms_full_and_threshold_without_upward_hunger():
    f = HungerFeedback()
    f.update(20000)
    assert f.update(100000) == 'full'
    assert f.update(100000) is None
    assert f.update(20000) == 'mild'
    assert f.update(30000) is None
    assert f.update(20000) == 'mild'


def test_corpus_and_feedback_parameters():
    assert set(CORPUS) == {'mild', 'severe', 'critical', 'full'}
    for phrases in CORPUS.values():
        assert len(phrases) == len(set(phrases)) == 100
        assert all(0 < len(p) <= 18 for p in phrases)
    assert bar_color(100000) == (75, 196, 107)
    assert bar_color(0) == (235, 75, 75)
    assert motion('full', 0)[2] < motion('full', .2)[2]


def test_corpus_does_not_repeat_a_thought_with_different_endings():
    for phrases in CORPUS.values():
        thoughts = [p.split('，')[0] for p in phrases]
        assert len(set(thoughts)) == 100
    assert all('嘿嘿' not in p and '哈哈' not in p
               for mood in ('severe', 'critical') for p in CORPUS[mood])


def test_critical_start_recovery_and_large_offline_crossings():
    f = HungerFeedback()
    assert f.update(999) == 'critical'
    assert f.update(998) is None and f.critical
    assert f.update(1000) is None and not f.critical
    assert f.update(999) == 'critical'
    assert f.update(100000) == 'full' and not f.critical
    assert f.update(5000) == 'severe'
    assert f.update(5000) is None
    assert f.update(4000) == 'severe'


def test_window_exposes_feedback_entrypoint():
    assert callable(getattr(HungerWindow, 'show_hunger_feedback', None))


def test_graphic_runtime_plays_only_crossings():
    from types import SimpleNamespace as NS
    from desktop_pet.hunger_graphic_runtime import HungerGraphicRuntime
    from desktop_pet.hunger import HungerService
    from desktop_pet.foundation.runtime import Activity
    units = [21000]
    clips, feedback = [], []
    coordinator = NS(current_token=None, permits=lambda _: True)
    runtime = NS(coordinator=coordinator, set_health=lambda *a, **k: None,
                 drain=lambda: None, snapshot=lambda: NS(activity=Activity.IDLE))
    service = NS(snapshot=lambda: NS(units=units[0], level=HungerService.level_for(units[0])))
    window = NS(root=NS(after=lambda *a: 1), refresh_hunger_presentation=lambda _: None,
                show_hunger_feedback=feedback.append, request_graphic_clip=lambda *a: clips.append(a))
    r = HungerGraphicRuntime(services=NS(runtime=runtime), service=service, window=window, clock=NS(monotonic=lambda: 9999))
    r.start()
    units[0] = 20000
    r._tick()
    r._tick()
    assert len(clips) == 1 and feedback == ['mild']
    units[0] = 18000
    r._tick()
    assert len(clips) == 2
    units[0] = 9999
    r._tick()
    assert clips[-1][0] == 'hunger.severe'

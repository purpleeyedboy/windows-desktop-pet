from desktop_pet.foundation.platform import DpiScale, HitRegion, InputMode, InputState, MonitorSnapshot, Point, Rect


def test_hit_regions_monitor_bounds_and_dpi_are_deterministic():
    region = HitRegion("eyes", Rect(10, 20, 30, 40))
    assert region.contains(Point(10, 20))
    assert not region.contains(Point(40, 60))
    monitor = MonitorSnapshot(Rect(-1920, -100, 1920, 1080), Rect(-1920, -60, 1920, 1040), 144)
    assert monitor.work_area.x == -1920
    assert DpiScale(144).logical_to_physical(20) == 30
    assert DpiScale(144).logical_to_physical(3) == 5
    assert DpiScale(144).logical_to_physical(-3) == -5


def test_transparent_pass_through_restores_exact_previous_input_state():
    state = InputState(mode=InputMode.INTERACTIVE, regions=(HitRegion("body", Rect(0, 0, 10, 10)),))
    snapshot = state.snapshot()
    state.set_pass_through()
    assert state.mode is InputMode.PASS_THROUGH
    state.restore(snapshot)
    assert state.snapshot() == snapshot

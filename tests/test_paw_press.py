from dataclasses import dataclass

from desktop_pet.paw_press import (
    ActivityApproval, PawPressController, PawSide, PawState, PointerBounds,
    PointerPoint,
)


@dataclass
class FakeCursor:
    point: PointerPoint = PointerPoint(-100, 20)
    pointer_height: int = 32
    clip: PointerBounds | None = PointerBounds(-500, 10, 900, 700)
    monitor: PointerBounds = PointerBounds(-1920, 0, 1920, 1080)

    def __post_init__(self): self.moves = []
    def position(self): return self.point
    def set_position(self, point): self.moves.append(point); self.point = point
    def pointer_nominal_height(self): return self.pointer_height
    def monitor_bounds_for(self, _point): return self.monitor
    def current_clip(self): return self.clip


class FakeGate:
    def __init__(self): self.buttons = False; self.blocked = False; self.allowed = True
    def any_button_down(self): return self.buttons
    def pointer_interaction_blocked(self): return self.blocked
    def paw_activity_allowed(self): return self.allowed


def approval(version=4, token='token'):
    return ActivityApproval('paw-17', version, token)


def valid(identity): return identity == approval()


def test_timing_moves_only_selected_paw_and_cools_down():
    cursor, gate = FakeCursor(), FakeGate()
    c = PawPressController(cursor, gate, approval_validator=valid)
    assert c.start(PawSide.LEFT, approval(), 0.0)
    assert c.sample(0.06).left_y < 0 and c.sample(0.06).right_y == 0
    assert c.sample(0.16).state is PawState.PAUSE
    assert c.sample(0.28).state is PawState.PRESS
    assert c.sample(0.48).state is PawState.RECOVER
    assert c.sample(0.60).left_y == 0
    assert not c.start(PawSide.RIGHT, approval(), 1.0)
    assert c.sample(1.21).state is PawState.IDLE


def test_cursor_total_is_35_not_per_frame_and_x_never_changes():
    cursor, gate = FakeCursor(), FakeGate()
    c = PawPressController(cursor, gate, approval_validator=valid)
    c.start(PawSide.RIGHT, approval(), 0)
    c.sample(.19); c.sample(.20); c.sample(.24); c.sample(.28); c.sample(.359)
    assert cursor.moves
    assert all(p.x == -100 for p in cursor.moves)
    assert cursor.moves[-1].y == 55
    assert max(p.y for p in cursor.moves) - 20 == 35


def test_next_paw_action_uses_its_own_cursor_start_after_cooldown():
    cursor, gate = FakeCursor(), FakeGate()
    controller = PawPressController(cursor, gate, approval_validator=valid)
    assert controller.start(PawSide.LEFT, approval(), 0)
    controller.sample(.20); controller.sample(.359); controller.sample(1.21)
    cursor.point = PointerPoint(-200, 100)
    cursor.moves.clear()
    assert controller.start(PawSide.RIGHT, approval(), 2)
    controller.sample(2.20); controller.sample(2.359)
    assert cursor.point == PointerPoint(-200, 135)
    assert all(point.x == -200 and 100 <= point.y <= 135 for point in cursor.moves)


def test_pointer_height_scales_once_and_clamps_total_distance():
    for height, expected in ((16, 20), (32, 35), (64, 70), (128, 70), (0, 35)):
        cursor, gate = FakeCursor(pointer_height=height), FakeGate()
        c = PawPressController(cursor, gate, approval_validator=valid)
        c.start(PawSide.LEFT, approval(), 0); c.sample(.20); c.sample(.359)
        assert cursor.point.y == 20 + expected


def test_packaged_motion_config_uses_new_displacement():
    from desktop_pet.assets import load_paw_motion_config
    config = load_paw_motion_config()
    assert (config.cursor_base_pixels, config.cursor_min_pixels, config.cursor_max_pixels) == (35, 20, 70)


def test_user_motion_during_lift_cancels_only_cursor_not_animation():
    cursor, gate = FakeCursor(), FakeGate()
    c = PawPressController(cursor, gate, approval_validator=valid)
    c.start(PawSide.LEFT, approval(), 0)
    cursor.point = PointerPoint(-94, 20)
    assert c.sample(.10).state is PawState.LIFT
    c.sample(.20); c.sample(.30)
    assert cursor.moves == []
    assert c.sample(.30).left_y != 0


def test_user_motion_or_button_during_press_never_pulls_cursor_back():
    cursor, gate = FakeCursor(), FakeGate()
    c = PawPressController(cursor, gate, approval_validator=valid)
    c.start(PawSide.LEFT, approval(), 0); c.sample(.20); c.sample(.25)
    moved = len(cursor.moves)
    cursor.point = PointerPoint(cursor.point.x + 5, cursor.point.y)
    c.sample(.27); c.sample(.35)
    assert len(cursor.moves) == moved
    assert c.sample(.35).state is PawState.PRESS


def test_boundaries_negative_coordinates_clip_and_zero_remaining():
    cursor = FakeCursor(point=PointerPoint(-2, 697))
    gate = FakeGate(); c = PawPressController(cursor, gate, approval_validator=valid)
    c.start(PawSide.RIGHT, approval(), 0); c.sample(.20); c.sample(.359)
    assert cursor.point == PointerPoint(-2, 709)
    count = len(cursor.moves); c.sample(.359)
    assert len(cursor.moves) == count


def test_stale_approval_or_permission_cancels_and_restores_pose():
    cursor, gate = FakeCursor(), FakeGate()
    c = PawPressController(cursor, gate, approval_validator=lambda _: False)
    c.start(PawSide.LEFT, approval(), 0)
    assert c.sample(.01).state is PawState.IDLE
    assert c.sample(.01).left_y == c.sample(.01).right_y == 0


def test_cursor_failure_is_not_retried_and_animation_continues():
    cursor, gate = FakeCursor(), FakeGate()
    def fail(_point): raise OSError('injected')
    cursor.set_position = fail
    c = PawPressController(cursor, gate, approval_validator=valid)
    c.start(PawSide.LEFT, approval(), 0); c.sample(.20); c.sample(.25); c.sample(.30)
    assert c.sample(.30).state is PawState.PRESS


def test_recovery_finishes_skipped_press_endpoint_without_accumulating():
    cursor, gate = FakeCursor(), FakeGate()
    c = PawPressController(cursor, gate, approval_validator=valid)
    c.start(PawSide.RIGHT, approval(), 0)
    c.sample(.20); c.sample(.28)
    assert cursor.point.y < 55
    c.sample(.40)
    assert cursor.point.y == 55
    moves = len(cursor.moves)
    c.sample(.50); c.sample(.59)
    assert len(cursor.moves) == moves


def test_graphic_frame_sequence_and_recovery_are_time_based():
    cursor, gate = FakeCursor(), FakeGate()
    c = PawPressController(cursor, gate, approval_validator=valid)
    c.start(PawSide.LEFT, approval(), 0)
    for milliseconds, frame in ((0, 0), (39, 0), (40, 1), (120, 3),
                                (199, 3), (200, 4), (360, 8), (600, 14)):
        assert c.sample(milliseconds / 1000).frame_index == frame
    assert c.sample(1.21).state is PawState.IDLE

from desktop_pet.hunger import HungerLevel
from desktop_pet.hunger_animation import HungerAnimationController, HungerVisual


def test_visual_state_and_tears_form_closed_mapping() -> None:
    controller = HungerAnimationController(clock=lambda: 0.0)
    assert controller.update(HungerLevel.NORMAL).visual is HungerVisual.NORMAL_HUNGRY
    assert controller.update(HungerLevel.SEVERE).visual is HungerVisual.SEVERE_HUNGRY
    extreme = controller.update(HungerLevel.EXTREME)
    assert extreme.visual is HungerVisual.EXTREME_HUNGRY
    assert extreme.tears_visible is True
    assert controller.update(HungerLevel.NORMAL).tears_visible is False


def test_user_animation_preempts_and_resume_uses_current_hunger_state() -> None:
    now = [0.0]
    controller = HungerAnimationController(clock=lambda: now[0])
    controller.update(HungerLevel.EXTREME)
    controller.user_animation_started()
    now[0] = 10_000.0
    assert controller.update(HungerLevel.SEVERE).visual is HungerVisual.SUSPENDED
    resumed = controller.user_animation_finished()
    assert resumed.visual is HungerVisual.SEVERE_HUNGRY
    assert resumed.tears_visible is False


def test_large_monotonic_step_keeps_phase_bounded() -> None:
    now = [0.0]
    controller = HungerAnimationController(clock=lambda: now[0])
    controller.update(HungerLevel.EXTREME)
    now[0] = 10**20
    frame = controller.update(HungerLevel.EXTREME)
    assert 0 <= frame.phase_millis < frame.cycle_millis

from random import Random

from desktop_pet.hunger import HungerLevel
from desktop_pet.hunger_animation import HungerAnimationController, HungerVisual


def test_visual_state_and_tears_form_closed_mapping():
    now = [0.0]
    controller = HungerAnimationController(clock=lambda: now[0], rng=Random(1))
    controller.update_health(HungerLevel.HUNGRY)
    now[0] = 0.1
    assert controller.frame().visual is HungerVisual.MOUTH
    controller.update_health(HungerLevel.CRITICAL_HUNGRY)
    critical = controller.frame()
    assert critical.visual is HungerVisual.CRITICAL
    assert critical.tears_visible
    controller.update_health(HungerLevel.NORMAL)
    assert not controller.frame().tears_visible


def test_user_animation_preempts_and_resume_uses_current_hunger_state():
    now = [0.0]
    controller = HungerAnimationController(clock=lambda: now[0], rng=Random(2))
    controller.update_health(HungerLevel.SEVERE_HUNGRY)
    controller.cancel_for_interruption()
    now[0] = 10_000.0
    controller.update_health(HungerLevel.CRITICAL_HUNGRY)
    assert controller.frame().visual is HungerVisual.SUSPENDED
    controller.resume_after_interruption()
    resumed = controller.frame()
    assert resumed.visual is HungerVisual.CRITICAL
    assert resumed.tears_visible


def test_large_monotonic_step_keeps_critical_phase_bounded():
    now = [0.0]
    controller = HungerAnimationController(clock=lambda: now[0])
    controller.update_health(HungerLevel.CRITICAL_HUNGRY)
    now[0] = 10**20
    assert 0 <= controller.frame().phase_millis < 1_000

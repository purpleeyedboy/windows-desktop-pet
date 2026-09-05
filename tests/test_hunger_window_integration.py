from types import SimpleNamespace

from PIL import Image, ImageChops

from desktop_pet.hunger_animation import HungerAnimationFrame, HungerVisual
from desktop_pet.model import Rect
from desktop_pet.window import PetWindow


class Bubble:
    def __init__(self): self.messages = []
    def show_message(self, text, pet, screen): self.messages.append(text)


def bare_window() -> PetWindow:
    window = object.__new__(PetWindow)
    window._closed = False
    window._last_hunger_presentation = None
    window._hunger_frame = None
    window._eye_interaction_boxes = ((170, 250, 220, 290), (290, 250, 340, 290))
    window._current_image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    window._presentation_snapshot = SimpleNamespace()
    window._window_rect = Rect(0, 0, 200, 300)
    window.bubble = Bubble()
    window.current_screen = lambda: Rect(0, 0, 1920, 1080)
    rendered = []
    window._apply_image = lambda image, anchor=None: rendered.append(
        window._compose_hunger_image(image)
    )
    window._anchor = lambda: (100, 300)
    window.rendered = rendered
    return window


def test_window_consumes_tears_and_phase_in_rendered_output() -> None:
    window = bare_window()
    dry = HungerAnimationFrame(HungerVisual.EXTREME_HUNGRY, False, 0, 1_600)
    wet = HungerAnimationFrame(HungerVisual.EXTREME_HUNGRY, True, 600, 1_600)
    window.present_hunger(dry)
    window.present_hunger(wet)
    assert len(window.rendered) == 2
    assert ImageChops.difference(*window.rendered).convert("RGB").getbbox() is not None


def test_bubble_only_shows_on_level_transition_not_animation_ticks() -> None:
    window = bare_window()
    for phase in (0, 400, 800, 1_200):
        window.present_hunger(
            HungerAnimationFrame(HungerVisual.SEVERE_HUNGRY, False, phase, 2_400)
        )
    assert window.bubble.messages == ["肚子好饿……"]
    window.present_hunger(
        HungerAnimationFrame(HungerVisual.EXTREME_HUNGRY, True, 0, 1_600)
    )
    assert window.bubble.messages == ["肚子好饿……", "真的非常饿了……"]

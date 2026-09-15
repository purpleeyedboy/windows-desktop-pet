from PIL import Image

from desktop_pet.hunger import HungerLevel
from desktop_pet.hunger_animation import HungerAnimationFrame, HungerVisual
from desktop_pet.hunger_effect import compose_hunger_effect


def frame(visual):
    return HungerAnimationFrame(
        HungerLevel.HUNGRY, visual, 1.0, False, 0.0, 400, None, 1,
    )


class Library:
    def __init__(self, overlay):
        self.overlay = overlay

    def overlay_for(self, _frame):
        return self.overlay


def test_authored_frame_replaces_live_pose_without_mutating_either_image():
    source = Image.new("RGBA", (640, 768), (1, 2, 3, 4))
    authored = Image.new("RGBA", (640, 768), (5, 6, 7, 8))
    source_before, authored_before = source.tobytes(), authored.tobytes()
    result = compose_hunger_effect(source, frame(HungerVisual.MOUTH), Library(authored))
    assert result.tobytes() == authored_before
    assert result is not authored
    assert source.tobytes() == source_before
    assert authored.tobytes() == authored_before


def test_suspended_frame_returns_unmodified_pixel_copy():
    source = Image.new("RGBA", (32, 32), (1, 2, 3, 4))
    result = compose_hunger_effect(source, frame(HungerVisual.SUSPENDED), Library(None))
    assert result.tobytes() == source.tobytes()
    assert result is not source

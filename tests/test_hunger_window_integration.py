from types import SimpleNamespace as NS

from PIL import Image

from desktop_pet.foundation.runtime import Activity
from desktop_pet.hunger import HungerLevel
from desktop_pet.hunger_window import HungerWindow


def bare_window(activity):
    window = HungerWindow.__new__(HungerWindow)
    window.services = NS(
        runtime=NS(
            clock=NS(monotonic=lambda: 0.0),
            snapshot=lambda: NS(activity=activity[0]),
        )
    )
    window._hunger_snapshot = None
    window._critical_visible = False
    window._critical_index = None
    window._critical_frames = (
        Image.new("RGBA", (640, 768), (1, 2, 3, 4)),
        Image.new("RGBA", (640, 768), (5, 6, 7, 8)),
    )
    window._critical_durations = (240, 240)
    window._critical_art = window._critical_frames[0]
    window._neutral_center_frame = Image.new("RGBA", (640, 768), (9, 10, 11, 12))
    window._refresh_meter = lambda _units: None
    window._refresh_feedback = lambda _units: None
    applied = []
    window._apply_image = lambda image, anchor: applied.append((image, anchor))
    window._anchor = lambda: (320, 768)
    return window, applied


def test_critical_art_hides_during_interaction_and_recovers_when_idle():
    activity = [Activity.IDLE]
    window, applied = bare_window(activity)
    snapshot = NS(level=HungerLevel.CRITICAL_HUNGRY, units=999)

    window.refresh_hunger_presentation(snapshot)
    assert window._critical_visible
    assert applied[-1][0] is window._neutral_center_frame

    activity[0] = Activity.BODY_ACTION
    window.refresh_hunger_presentation(snapshot)
    assert not window._critical_visible

    activity[0] = Activity.IDLE
    window.refresh_hunger_presentation(snapshot)
    assert window._critical_visible
    assert len(applied) == 3

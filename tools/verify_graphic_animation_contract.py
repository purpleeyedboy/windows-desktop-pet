"""Non-pytest verification for the shared real-graphic animation contract."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from PIL import Image

from desktop_pet.animation import AnimationController, AnimationSequence, FrameStep
from desktop_pet.assets import compose_local_graphic_frame, load_frames, load_playback_sequences, validate_runtime_graphic_frame
from desktop_pet.foundation.animation import AnimationChannels
from desktop_pet.foundation.runtime import Activity, RuntimeContext
from desktop_pet.foundation.sources import FixedTimeSource
from desktop_pet.window import PetWindow


def verify_feature_activity_playback() -> None:
    """Exercise the actual window/queue/channel/player chain without Tk or files."""
    clock = FixedTimeSource(datetime(2026, 9, 9, tzinfo=timezone.utc), 0)
    runtime = RuntimeContext(clock)
    window = PetWindow.__new__(PetWindow)
    window.services = SimpleNamespace(runtime=runtime, animation=AnimationChannels(runtime.coordinator))
    window.frames = {}
    window.eye_session = None
    window._closed = False
    window._legacy_fallback = False
    window._rendering_available = True
    window._active_animation_action = None
    window._activity_token = None
    window._presentation_snapshot = None
    neutral = Image.new("RGBA", (2, 2), (20, 20, 20, 255))
    window._neutral_center_frame = neutral
    window._anchor = lambda: (0, 0)
    shown = []
    scheduled = []
    window._apply_image = lambda frame, *_args, **_kwargs: shown.append(frame)

    def schedule(_delay, callback):
        scheduled.append(callback)
        return callback

    window.animation = AnimationController(
        {}, schedule, window._show_animation_frame, lambda _action: None,
        cancel=lambda callback: scheduled.remove(callback),
        finished_with_id=window._animation_finished,
    )
    runtime.bind("input.graphic-clip", window._consume_graphic_clip)
    window.services.animation.register("body", window._play_registered_graphic, window._recover_body_channel)
    frames = tuple(Image.new("RGBA", (2, 2), color) for color in ((80, 20, 20, 255), (20, 80, 20, 255)))
    window.register_graphic_clip("feature.test", frames, AnimationSequence((FrameStep(0, 40), FrameStep(1, 60)), (0, 0)))
    activities = (
        Activity.BODY_ACTION, Activity.GROOM, Activity.NORMAL_HUNGER_ANIMATION,
        Activity.SEVERE_HUNGER_ANIMATION, Activity.FEED_ANIMATION,
    )
    for activity in activities:
        shown.clear()
        window.request_graphic_clip("feature.test", activity)
        if runtime.snapshot().activity is not activity or not window.animation.busy or shown != [frames[0]]:
            raise RuntimeError(f"{activity.value} did not enter the real graphic player")
        while scheduled:
            scheduled.pop(0)()
        if runtime.snapshot().activity is not Activity.IDLE or window.animation.busy or shown != [*frames, neutral]:
            raise RuntimeError(f"{activity.value} did not finish and restore the neutral frame")

    window.request_graphic_clip("feature.test", Activity.GROOM)
    stale = window._activity_token
    stale_callback = scheduled[0]
    window.request_graphic_clip("feature.test", Activity.FEED_ANIMATION)
    current = window._activity_token
    before = len(shown)
    stale_callback()
    window._animation_finished("feature.test", stale.cancellation_id)
    if window._activity_token != current or window._active_animation_action != "feature.test" or len(shown) != before:
        raise RuntimeError("stale completion changed the replacement graphic clip")
    runtime.coordinator.cancel_and_recover(current)
    if window.animation.busy or scheduled or shown[-1] is not neutral or runtime.snapshot().activity is not Activity.IDLE:
        raise RuntimeError("graphic cancellation did not physically and logically recover")
    window.request_graphic_clip("feature.test", Activity.GROOM)
    clock.advance(31)
    runtime.drain()
    if window.animation.busy or scheduled or shown[-1] is not neutral or runtime.snapshot().activity is not Activity.IDLE:
        raise RuntimeError("graphic timeout did not physically and logically recover")
    for activity in (Activity.DRAG_PREVIEW, Activity.FEED_PROCESSING, Activity.TRANSACTION_REVIEW, Activity.SHUTTING_DOWN):
        try:
            window.request_graphic_clip("feature.test", activity)
        except ValueError:
            pass
        else:
            raise RuntimeError(f"non-graphic activity {activity.value} was accepted as animation")


def main() -> int:
    verify_feature_activity_playback()
    frames = load_frames()
    sequences = load_playback_sequences()
    scheduled: list[tuple[int, object]] = []
    shown: list[tuple[str, int]] = []

    def schedule(delay: int, callback):
        scheduled.append((delay, callback))
        return callback

    controller = AnimationController(
        sequences,
        schedule,
        lambda action, index: shown.append((action, index)),
        lambda action: shown.append(("finished", action)),
    )
    if not controller.play("jump"):
        raise RuntimeError("wired graphic clip was rejected")
    while scheduled:
        delay, callback = scheduled.pop(0)
        if delay != sequences["jump"].steps[len(shown) - 1].duration_ms:
            raise RuntimeError("frame duration was not used by the scheduler")
        callback()
    if shown != [("jump", index) for index in range(6)] + [("finished", "jump")]:
        raise RuntimeError("graphic frame order changed")

    looped = AnimationSequence(
        (FrameStep(0, 40), FrameStep(1, 50), FrameStep(2, 60)),
        (256, 768),
        loop_start=1,
        loop_end=2,
        loop_count=2,
    )
    if [step.frame_index for step in looped.timeline()] != [0, 1, 2, 1, 2, 1, 2]:
        raise RuntimeError("finite loop segment is incorrect")

    base = frames["jump"][0]
    restoration = Image.new("RGBA", base.size)
    restoration.putpixel((10, 10), base.getpixel((10, 10)))
    layer = Image.new("RGBA", (2, 2), (120, 80, 40, 255))
    composed = compose_local_graphic_frame(
        base,
        layer,
        offset=(10, 10),
        restoration=restoration,
    )
    if composed.getpixel((10, 10)) != (120, 80, 40, 255):
        raise RuntimeError("local graphic layer did not composite")
    dirty = Image.new("RGBA", base.size)
    dirty.putpixel((0, 0), (255, 0, 0, 0))
    try:
        validate_runtime_graphic_frame(dirty, base.size)
    except ValueError:
        pass
    else:
        raise RuntimeError("dirty transparent edge was accepted")
    print("real-graphic animation contract verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

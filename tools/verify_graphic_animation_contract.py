"""Non-pytest verification for the shared real-graphic animation contract."""
from __future__ import annotations

from PIL import Image

from desktop_pet.animation import AnimationController, AnimationSequence, FrameStep
from desktop_pet.assets import compose_local_graphic_frame, load_frames, load_playback_sequences, validate_runtime_graphic_frame


def main() -> int:
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

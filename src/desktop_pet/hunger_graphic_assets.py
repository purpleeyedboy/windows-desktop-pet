"""Bridge the recovered asset manifest to the verified common graphic player."""
from dataclasses import dataclass
from PIL import Image

from .animation import AnimationSequence, FrameStep
from .assets import validate_runtime_graphic_frame
from .hunger_effect import HungerFrameLibrary


@dataclass(frozen=True)
class HungerGraphicAssets:
    clips: dict
    critical_frames: tuple[Image.Image, ...]
    critical_durations: tuple[int, ...]


def load_hunger_graphic_assets(neutral: Image.Image) -> HungerGraphicAssets:
    library = HungerFrameLibrary()
    if neutral.size != (640, 768) or neutral.mode != "RGBA":
        raise ValueError("hunger art requires the accepted live 640x768 neutral")
    clips = {}
    for name in ("hungry", "severe"):
        sequence = library.sequences[name]
        frames = tuple(
            neutral if index in {0, len(sequence) - 1} else library._runtime_frame(item.image)
            for index, item in enumerate(sequence)
        )
        for frame in frames:
            validate_runtime_graphic_frame(frame, neutral.size)
        timeline = AnimationSequence(
            tuple(FrameStep(index, item.duration_millis) for index, item in enumerate(sequence)),
            (320, 768),
        )
        clips[f"hunger.{name}"] = (frames, timeline)
    critical = library.sequences["critical"]
    critical_frames = tuple(library._runtime_frame(item.image) for item in critical)
    for frame in critical_frames:
        validate_runtime_graphic_frame(frame, neutral.size)
    return HungerGraphicAssets(clips, critical_frames, tuple(item.duration_millis for item in critical))

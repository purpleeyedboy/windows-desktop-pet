"""Bridge the recovered asset manifest to the verified common graphic player."""
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageChops
import hashlib
import json

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
    payload = json.loads((library.root / "manifest.json").read_text("utf-8"))
    if payload.get("composition") != "fixed-runtime-neutral-with-local-generated-mouth-and-tears":
        raise ValueError("hunger art must preserve the accepted body using local expression frames")
    if payload.get("fixed_base_rgba_sha256") != hashlib.sha256(neutral.tobytes()).hexdigest():
        raise ValueError("hunger expression base differs from the actual accepted neutral")
    regions = payload.get("mutable_runtime_regions")
    if regions != [[138, 386, 224, 442], [128, 355, 166, 424], [211, 352, 254, 424]]:
        raise ValueError("hunger expression regions differ from the reviewed mouth/tear contract")
    allowed = Image.new("L", neutral.size, 0)
    for region in regions:
        ImageDraw.Draw(allowed).rectangle(tuple(region), fill=255)
    outside = ImageChops.invert(allowed)

    def validate_fixed_body(frame):
        validate_runtime_graphic_frame(frame, neutral.size)
        if frame.getchannel("A").tobytes() != neutral.getchannel("A").tobytes():
            raise ValueError("hunger expression changed the accepted silhouette alpha")
        for channel in ImageChops.difference(frame, neutral).split():
            if ImageChops.multiply(channel, outside).getbbox() is not None:
                raise ValueError("hunger expression changed pixels outside the mouth/tear regions")

    clips = {}
    for name in ("hungry", "severe"):
        sequence = library.sequences[name]
        frames = tuple(
            neutral if index in {0, len(sequence) - 1} else library._runtime_frame(item.image)
            for index, item in enumerate(sequence)
        )
        for frame in frames:
            validate_fixed_body(frame)
        timeline = AnimationSequence(
            tuple(FrameStep(index, item.duration_millis) for index, item in enumerate(sequence)),
            (320, 768),
        )
        clips[f"hunger.{name}"] = (frames, timeline)
    critical = library.sequences["critical"]
    critical_frames = tuple(library._runtime_frame(item.image) for item in critical)
    for frame in critical_frames:
        validate_fixed_body(frame)
    return HungerGraphicAssets(clips, critical_frames, tuple(item.duration_millis for item in critical))

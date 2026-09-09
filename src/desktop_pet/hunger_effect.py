"""Asset-backed hunger expression frames composed over the approved live pose."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from PIL import Image

from .hunger import HungerLevel
from .hunger_animation import HungerAnimationFrame, HungerVisual
from .paths import asset_path


@dataclass(frozen=True)
class HungerArtFrame:
    image: Image.Image
    duration_millis: int
    source: Path


class HungerFrameLibrary:
    """Validated local RGBA frames; no geometric substitute is permitted."""

    REQUIRED_SEQUENCES = ("hungry", "severe", "critical")

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or asset_path("assets", "hunger", "v1")
        manifest_path = self.root / "manifest.json"
        if not manifest_path.is_file():
            raise RuntimeError(
                "V2.1 hunger art is missing: assets/hunger/v1/manifest.json"
            )
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        canvas = payload.get("canvas")
        if (
            not isinstance(canvas, list)
            or len(canvas) != 2
            or any(type(value) is not int or value <= 0 for value in canvas)
        ):
            raise ValueError("hunger art manifest canvas is invalid")
        self.canvas = (canvas[0], canvas[1])
        sequences = payload.get("sequences")
        if not isinstance(sequences, dict):
            raise ValueError("hunger art manifest sequences are invalid")
        self.sequences = {
            name: self._load_sequence(name, sequences.get(name))
            for name in self.REQUIRED_SEQUENCES
        }
        for name in ("hungry", "severe"):
            if len(self.sequences[name]) < 5:
                raise ValueError(f"hunger art sequence needs at least five poses: {name}")
            if sum(frame.duration_millis for frame in self.sequences[name]) != 1_700:
                raise ValueError(f"hunger art sequence must total 1700ms: {name}")
        if len(self.sequences["critical"]) < 2:
            raise ValueError("critical hunger tears require at least two authored poses")

    def _load_sequence(
        self,
        name: str,
        entries: object,
    ) -> tuple[HungerArtFrame, ...]:
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"hunger art sequence is missing: {name}")
        frames: list[HungerArtFrame] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"hunger art frame entry is invalid: {name}")
            relative = entry.get("file")
            duration = entry.get("duration_ms")
            if (
                not isinstance(relative, str)
                or not relative.endswith(".png")
                or type(duration) is not int
                or duration <= 0
            ):
                raise ValueError(f"hunger art frame metadata is invalid: {name}")
            source = self.root / relative
            if not source.is_file():
                raise RuntimeError(f"hunger art frame is missing: {source}")
            with Image.open(source) as opened:
                image = opened.convert("RGBA")
            if image.size != self.canvas:
                raise ValueError(
                    f"hunger art frame {source} must use canvas {self.canvas}"
                )
            if image.getchannel("A").getbbox() is None:
                raise ValueError(f"hunger art frame is empty: {source}")
            frames.append(HungerArtFrame(image, duration, source))
        return tuple(frames)

    def overlay_for(self, frame: HungerAnimationFrame) -> Image.Image | None:
        if frame.visual is HungerVisual.SUSPENDED or frame.health is HungerLevel.NORMAL:
            return None
        name = {
            HungerLevel.HUNGRY: "hungry",
            HungerLevel.SEVERE_HUNGRY: "severe",
            HungerLevel.CRITICAL_HUNGRY: "critical",
        }[frame.health]
        sequence = self.sequences[name]
        total = sum(item.duration_millis for item in sequence)
        position = max(0, frame.phase_millis)
        if frame.health is HungerLevel.CRITICAL_HUNGRY:
            position %= total
        else:
            position = min(position, total - 1)
        for item in sequence:
            if position < item.duration_millis:
                return item.image
            position -= item.duration_millis
        return sequence[-1].image


def compose_hunger_effect(
    source: Image.Image,
    frame: HungerAnimationFrame,
    library: HungerFrameLibrary,
) -> Image.Image:
    """Composite an authored local frame over the current approved live pose."""
    base = source.convert("RGBA")
    if base.size != library.canvas:
        raise ValueError(
            f"live pose canvas {base.size} does not match hunger art {library.canvas}"
        )
    overlay = library.overlay_for(frame)
    return base.copy() if overlay is None else Image.alpha_composite(base, overlay)

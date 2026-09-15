"""Asset-backed hunger expression frames composed over the approved live pose."""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import io
import json
from pathlib import Path

from PIL import Image

from .hunger import HungerLevel
from .hunger_animation import HungerAnimationFrame, HungerVisual
from .paths import asset_path

CANONICAL_IDLE_SHA256 = "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"
AUTHORING_CANVAS = (512, 768)
RUNTIME_CANVAS = (640, 768)
RUNTIME_OFFSET = (64, 0)
TIMELINE_MILLIS = {"open": 350, "hold": 1_000, "close": 350}

@dataclass(frozen=True)
class HungerArtFrame:
    image: Image.Image
    duration_millis: int
    source: Path
    phase: str


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
        if payload.get("version") != 1 or payload.get("frame_type") != "full-frame":
            raise ValueError("hunger art manifest must describe V1 full frames")
        if payload.get("canonical_idle_sha256") != CANONICAL_IDLE_SHA256:
            raise ValueError("hunger art was not aligned to the approved canonical idle")
        self.encoding = payload.get("encoding")
        if self.encoding not in {"png", "base64-png"}:
            raise ValueError("hunger art encoding must be png or base64-png")
        canvas = payload.get("canvas")
        if (
            not isinstance(canvas, list)
            or len(canvas) != 2
            or any(type(value) is not int or value <= 0 for value in canvas)
        ):
            raise ValueError("hunger art manifest canvas is invalid")
        self.canvas = (canvas[0], canvas[1])
        if self.canvas != AUTHORING_CANVAS or payload.get("anchor") != [256, 768]:
            raise ValueError("hunger full frames must use canvas 512x768 and anchor [256,768]")
        if payload.get("runtime_canvas") != list(RUNTIME_CANVAS):
            raise ValueError("hunger runtime canvas must be 640x768")
        if payload.get("runtime_offset") != list(RUNTIME_OFFSET):
            raise ValueError("hunger runtime offset must be [64,0]")
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
            phase_totals = {phase: 0 for phase in TIMELINE_MILLIS}
            phases = []
            for frame in self.sequences[name]:
                phases.append(frame.phase)
                phase_totals[frame.phase] += frame.duration_millis
            if phases != sorted(
                phases,
                key=("open", "hold", "close").index,
            ):
                raise ValueError(f"hunger art phases are out of order: {name}")
            if phase_totals != TIMELINE_MILLIS:
                raise ValueError(f"hunger art phase durations are invalid: {name}")
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
            phase = entry.get("phase")
            expected_sha256 = entry.get("png_sha256")
            if (
                not isinstance(relative, str)
                or not relative.endswith(
                    ".png" if self.encoding == "png" else ".png.base64"
                )
                or type(duration) is not int
                or duration <= 0
                or duration % 10
                or phase not in ({"loop"} if name == "critical" else TIMELINE_MILLIS)
                or not isinstance(expected_sha256, str)
                or len(expected_sha256) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in expected_sha256
                )
            ):
                raise ValueError(f"hunger art frame metadata is invalid: {name}")
            source = self.root / relative
            if self.root.resolve() not in source.resolve().parents:
                raise ValueError(f"hunger art frame escapes asset root: {relative}")
            if not source.is_file():
                raise RuntimeError(f"hunger art frame is missing: {source}")
            raw = source.read_bytes()
            if self.encoding == "base64-png":
                try:
                    raw = base64.b64decode(b"".join(raw.split()), validate=True)
                except ValueError as error:
                    raise ValueError(f"hunger frame base64 is invalid: {source}") from error
            if hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise ValueError(f"hunger frame hash does not match manifest: {source}")
            with Image.open(io.BytesIO(raw)) as opened:
                if opened.format != "PNG":
                    raise ValueError(f"hunger art frame is not PNG: {source}")
                image = opened.convert("RGBA")
            if image.size != self.canvas:
                raise ValueError(
                    f"hunger art frame {source} must use canvas {self.canvas}"
                )
            if image.getchannel("A").getbbox() is None:
                raise ValueError(f"hunger art frame is empty: {source}")
            frames.append(HungerArtFrame(image, duration, source, phase))
        return tuple(frames)

    def overlay_for(self, frame: HungerAnimationFrame) -> Image.Image | None:
        if frame.visual in {HungerVisual.SUSPENDED, HungerVisual.NONE} or frame.health is HungerLevel.NORMAL:
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
                return self._runtime_frame(item.image)
            position -= item.duration_millis
        return self._runtime_frame(sequence[-1].image)

    @staticmethod
    def _runtime_frame(authored: Image.Image) -> Image.Image:
        """Apply the rig's declared 64px side padding without scaling artwork."""
        runtime = Image.new("RGBA", RUNTIME_CANVAS, (0, 0, 0, 0))
        runtime.alpha_composite(authored, RUNTIME_OFFSET)
        return runtime


def compose_hunger_effect(
    source: Image.Image,
    frame: HungerAnimationFrame,
    library: HungerFrameLibrary,
) -> Image.Image:
    """Select an authored full frame, avoiding old/new mouth overlap."""
    base = source.convert("RGBA")
    authored = library.overlay_for(frame)
    if authored is None:
        return base.copy()
    if base.size != RUNTIME_CANVAS:
        raise ValueError(
            f"live pose canvas {base.size} does not match runtime canvas {RUNTIME_CANVAS}"
        )
    return authored.copy()

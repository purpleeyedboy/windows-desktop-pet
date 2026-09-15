"""Validated loader and timing table for authored drag-expression frames."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from .paths import asset_path


@dataclass(frozen=True)
class DragExpressionFrame:
    frame_id: str
    image: Image.Image
    eye_scale: float
    duration_ms: int
    sha256: str


@dataclass(frozen=True)
class DragExpressionSequence:
    frames: tuple[DragExpressionFrame, ...]
    approved_default_sha256: str
    enter_duration_ms: int
    hold_duration_ms: int
    exit_duration_ms: int

    def for_phase(self, phase: int) -> DragExpressionFrame:
        if phase <= 0:
            return self.frames[0]
        if phase == 1:
            return self.frames[1]
        if phase == 2:
            return self.frames[2]
        return self.frames[3 + ((phase - 3) // 2) % 2]

    def for_exit(self, elapsed_ms: int) -> DragExpressionFrame:
        if elapsed_ms >= self.exit_duration_ms:
            return self.frames[0]
        slot = max(0, elapsed_ms // 50)
        return (self.frames[2], self.frames[1], self.frames[0])[min(2, slot)]


def load_drag_expression_sequence(root: Path | None = None) -> DragExpressionSequence:
    root = root or asset_path("assets", "drag-expectation", "v1")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    packed = json.loads((root / "frames.pack.json").read_text(encoding="ascii"))
    if packed.get("encoding") != "base85-png" or manifest.get("canvas") != [512, 768]:
        raise ValueError("unsupported drag-expression frame pack")
    frames = []
    for record in manifest["frames"]:
        png = base64.b85decode(packed["frames"][record["id"]].encode("ascii"))
        digest = hashlib.sha256(png).hexdigest()
        if digest != record["png_sha256"]:
            raise ValueError(f"drag-expression frame hash mismatch: {record['id']}")
        with Image.open(BytesIO(png)) as opened:
            if opened.mode != "RGBA" or opened.size != (512, 768):
                raise ValueError(f"invalid drag-expression frame: {record['id']}")
            image = opened.copy()
            image.load()
        frames.append(DragExpressionFrame(record["id"], image, float(record["eye_scale"]), int(record["duration_ms"]), digest))
    return DragExpressionSequence(
        tuple(frames), manifest["approved_default_sha256"],
        int(manifest["enter_duration_ms"]), int(manifest["hold_duration_ms"]),
        int(manifest["exit_duration_ms"]),
    )

"""Read the five baked, aligned expectation frames shipped in the EXE."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from PIL import Image
from .paths import asset_path


def load_expectation_frames(root: Path | None = None, *, expected_size=(640, 768)):
    root = root or asset_path("assets", "expectation", "runtime")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if tuple(manifest["canvas"]) != tuple(expected_size) or len(manifest["frames"]) != 5:
        raise ValueError("expectation runtime canvas or frame count mismatch")
    frames = []
    for index, record in enumerate(manifest["frames"]):
        if record["file"] != f"{index:02d}.png":
            raise ValueError("unexpected expectation frame path")
        with Image.open(root / record["file"]) as image:
            if image.mode != "RGBA" or image.size != tuple(expected_size):
                raise ValueError("expectation frame is not canonical RGBA")
            frame = image.copy()
        if frame.getchannel("A").getextrema() != (0, 255):
            raise ValueError("expectation frame lacks transparent background")
        if hashlib.sha256(frame.tobytes()).hexdigest() != record["rgba_sha256"]:
            raise ValueError("expectation frame pixel hash mismatch")
        frames.append(frame)
    return tuple(frames)

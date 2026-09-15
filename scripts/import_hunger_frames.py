#!/usr/bin/env python3
"""Validate generated hunger poses and import deterministic runtime resources."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
from typing import Any

from PIL import Image, ImageDraw


CANVAS = (512, 768)
ANCHOR = (256, 768)
RUNTIME_CANVAS = (640, 768)
RUNTIME_OFFSET = (64, 0)
CANONICAL_SHA256 = "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"
REQUIRED = ("hungry", "severe", "critical")
TIMELINE_MILLIS = {"open": 350, "hold": 1_000, "close": 350}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_recipe(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("import recipe must be an object with version=1")
    if value.get("canvas") != list(CANVAS) or value.get("anchor") != list(ANCHOR):
        raise ValueError("import recipe must target canvas 512x768 and anchor [256,768]")
    sequences = value.get("sequences")
    if not isinstance(sequences, dict) or set(sequences) != set(REQUIRED):
        raise ValueError("import recipe must contain exactly hungry, severe, critical")
    return value


def _load_frame(input_root: Path, entry: dict[str, Any]) -> Image.Image:
    source_name = entry.get("source")
    if not isinstance(source_name, str):
        raise ValueError("every imported frame requires a source path")
    source = input_root / source_name
    if input_root.resolve() not in source.resolve().parents:
        raise ValueError(f"generated frame escapes input directory: {source_name}")
    if not source.is_file():
        raise FileNotFoundError(source)
    with Image.open(source) as opened:
        if opened.mode != "RGBA":
            raise ValueError(f"generated frame must already be RGBA: {source}")
        image = opened.copy()
    crop = entry.get("crop_box")
    if image.size != CANVAS:
        if (
            not isinstance(crop, list)
            or len(crop) != 4
            or any(type(value) is not int for value in crop)
        ):
            raise ValueError(
                f"{source} is {image.size}; non-512 canvases require an explicit crop_box"
            )
        left, top, right, bottom = crop
        if (right - left, bottom - top) != CANVAS:
            raise ValueError(f"crop_box for {source} must produce exactly 512x768")
        if left < 0 or top < 0 or right > image.width or bottom > image.height:
            raise ValueError(f"crop_box exceeds source canvas: {source}")
        image = image.crop((left, top, right, bottom))
    elif crop is not None:
        raise ValueError(f"crop_box is forbidden for an already aligned frame: {source}")
    alpha = image.getchannel("A")
    if alpha.getbbox() is None or alpha.getextrema()[0] != 0:
        raise ValueError(f"frame needs non-empty art and transparent background: {source}")
    return image


def _png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _checkerboard(size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", size, "#eeeeee")
    draw = ImageDraw.Draw(image)
    tile = 16
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill="#cccccc")
    return image


def _preview_frame(frame: Image.Image, size: tuple[int, int]) -> Image.Image:
    backdrop = _checkerboard(CANVAS).convert("RGBA")
    backdrop.alpha_composite(frame)
    return backdrop.convert("RGB").resize(size, Image.Resampling.LANCZOS)


def import_frames(
    recipe_path: Path,
    input_root: Path,
    output_root: Path,
    qa_root: Path,
    *,
    encoding: str,
) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    canonical = repository_root / "assets/rig/v1/source/canonical-idle.png"
    if _sha256(canonical) != CANONICAL_SHA256:
        raise RuntimeError("approved canonical-idle.png hash does not match V2.1")
    recipe = _load_recipe(recipe_path)
    staged = output_root.with_name(output_root.name + ".importing")
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)
    runtime_sequences: dict[str, list[dict[str, Any]]] = {}
    loaded: dict[str, list[tuple[Image.Image, int, str]]] = {}
    try:
        for sequence_name in REQUIRED:
            entries = recipe["sequences"][sequence_name]
            if not isinstance(entries, list) or not entries:
                raise ValueError(f"sequence is empty: {sequence_name}")
            loaded[sequence_name] = []
            runtime_sequences[sequence_name] = []
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    raise ValueError(f"frame entry is invalid: {sequence_name}/{index}")
                duration = entry.get("duration_ms")
                phase = entry.get("phase")
                expected_phases = (
                    {"loop"}
                    if sequence_name == "critical"
                    else set(TIMELINE_MILLIS)
                )
                if phase not in expected_phases:
                    raise ValueError(f"phase is invalid: {sequence_name}/{index}")
                if type(duration) is not int or duration <= 0 or duration % 10:
                    raise ValueError(f"duration_ms is invalid: {sequence_name}/{index}")
                frame = _load_frame(input_root, entry)
                data = _png_bytes(frame)
                suffix = ".png" if encoding == "png" else ".png.base64"
                relative = f"{sequence_name}/{index:02d}{suffix}"
                target = staged / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data if encoding == "png" else base64.b64encode(data) + b"\n")
                runtime_sequences[sequence_name].append(
                    {
                        "file": relative,
                        "duration_ms": duration,
                        "phase": phase,
                        "png_sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
                loaded[sequence_name].append((frame, duration, relative))
        for name in ("hungry", "severe"):
            if len(loaded[name]) < 5 or sum(item[1] for item in loaded[name]) != 1_700:
                raise ValueError(f"{name} requires >=5 frames totaling exactly 1700ms")
            entries = recipe["sequences"][name]
            phases = [entry["phase"] for entry in entries]
            if phases != sorted(phases, key=("open", "hold", "close").index):
                raise ValueError(f"{name} phases must be ordered open, hold, close")
            for phase, expected in TIMELINE_MILLIS.items():
                actual = sum(
                    entry["duration_ms"]
                    for entry in entries
                    if entry["phase"] == phase
                )
                if actual != expected:
                    raise ValueError(f"{name} {phase} phase must total {expected}ms")
        if len(loaded["critical"]) < 2:
            raise ValueError("critical requires at least two authored frames")
        manifest = {
            "version": 1,
            "frame_type": "full-frame",
            "encoding": encoding,
            "canvas": list(CANVAS),
            "anchor": list(ANCHOR),
            "runtime_canvas": list(RUNTIME_CANVAS),
            "runtime_offset": list(RUNTIME_OFFSET),
            "canonical_idle_sha256": CANONICAL_SHA256,
            "sequences": runtime_sequences,
        }
        (staged / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output_root.exists():
            shutil.rmtree(output_root)
        staged.replace(output_root)
    finally:
        if staged.exists():
            shutil.rmtree(staged)

    qa_root.mkdir(parents=True, exist_ok=True)
    thumb = (192, 288)
    columns = max(len(items) for items in loaded.values())
    sheet = Image.new("RGB", (columns * thumb[0], len(REQUIRED) * (thumb[1] + 28)), "#20242a")
    draw = ImageDraw.Draw(sheet)
    for row, name in enumerate(REQUIRED):
        y = row * (thumb[1] + 28)
        for column, (frame, duration, _relative) in enumerate(loaded[name]):
            sheet.paste(_preview_frame(frame, thumb), (column * thumb[0], y + 20))
            draw.text((column * thumb[0] + 4, y + 4), f"{name} {column:02d} {duration}ms", fill="white")
    sheet.save(qa_root / "hunger-contact-sheet.png", compress_level=9)
    for name, items in loaded.items():
        gif_frames = [_preview_frame(frame, CANVAS) for frame, _duration, _relative in items]
        gif_frames[0].save(
            qa_root / f"hunger-{name}.gif",
            save_all=True,
            append_images=gif_frames[1:],
            duration=[duration for _frame, duration, _relative in items],
            loop=0 if name == "critical" else 1,
            disposal=2,
        )
    (qa_root / "hunger-frame-list.json").write_text(
        json.dumps(runtime_sequences, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("assets/hunger/v1"))
    parser.add_argument("--qa-dir", type=Path, required=True)
    parser.add_argument("--encoding", choices=("png", "base64-png"), default="base64-png")
    arguments = parser.parse_args()
    import_frames(
        arguments.recipe,
        arguments.input_dir,
        arguments.output_dir,
        arguments.qa_dir,
        encoding=arguments.encoding,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

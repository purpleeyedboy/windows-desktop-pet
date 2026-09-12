"""Build deterministic evidence for the wired real-graphic frame player."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from desktop_pet.assets import load_frames, load_playback_sequences, runtime_frame_root


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "qa" / "v21-frame-player"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    frames = load_frames()
    sequences = load_playback_sequences()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    thumb_size = (128, 192)
    sheet = Image.new("RGBA", (thumb_size[0] * 6, (thumb_size[1] + 28) * 3), (36, 36, 42, 255))
    draw = ImageDraw.Draw(sheet)
    preview: list[Image.Image] = []
    durations: list[int] = []
    report_clips: dict[str, object] = {}
    for row, action in enumerate(("jump", "squash", "shake")):
        sequence = sequences[action]
        clip_hashes = []
        for column, step in enumerate(sequence.steps):
            frame = frames[action][step.frame_index]
            thumb = frame.resize(thumb_size, Image.Resampling.LANCZOS)
            sheet.alpha_composite(thumb, (column * thumb_size[0], row * (thumb_size[1] + 28)))
            draw.text((column * thumb_size[0] + 4, row * (thumb_size[1] + 28) + thumb_size[1] + 4), f"{action} {step.frame_index:02d} {step.duration_ms}ms", fill="white")
            preview.append(thumb.convert("P", palette=Image.Palette.ADAPTIVE, colors=255))
            durations.append(step.duration_ms)
            clip_hashes.append(sha256(runtime_frame_root() / action / f"{step.frame_index:02d}.png"))
        report_clips[action] = {
            "anchor": sequence.anchor,
            "layer_mode": sequence.layer_mode,
            "frames": [{"index": step.frame_index, "duration_ms": step.duration_ms, "sha256": digest} for step, digest in zip(sequence.steps, clip_hashes, strict=True)],
        }
    sheet.save(OUTPUT / "contact-sheet.png", optimize=False)
    preview[0].save(OUTPUT / "existing-actions-preview.gif", save_all=True, append_images=preview[1:], duration=durations, loop=0, disposal=2, optimize=False)
    report = {
        "version": 1,
        "purpose": "real graphic frame player wiring evidence; not evidence for missing V2.1 feature art",
        "approved_default_sha256": sha256(ROOT / "assets/rig/v1/source/canonical-idle.png"),
        "clips": report_clips,
        "missing_feature_art": ["hand-licking", "ears", "forelimbs", "hunger-mouth", "feeding", "anticipation"],
        "outputs": ["contact-sheet.png", "existing-actions-preview.gif"],
    }
    (OUTPUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"frame-player evidence written to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

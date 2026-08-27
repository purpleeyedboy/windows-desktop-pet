from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

try:
    from tools.clean_colored_edges import contamination_mask
except ModuleNotFoundError:
    from clean_colored_edges import contamination_mask


ACTIONS = ("jump", "squash", "shake")
EXPECTED_SIZE = (512, 768)
FRAME_COUNT = 30
EXPECTED_NAMES = tuple(f"{index:02d}.png" for index in range(FRAME_COUNT))
EXPECTED_KEYFRAME_NAMES = tuple(f"{index:02d}.png" for index in range(6))
KEYFRAME_POSITIONS = (0, 6, 12, 17, 23, 29)


def transparent_rgb_is_zero(image: Image.Image) -> bool:
    return all(
        (red, green, blue) == (0, 0, 0)
        for red, green, blue, alpha in image.convert("RGBA").getdata()
        if alpha == 0
    )


def border_is_transparent(image: Image.Image) -> bool:
    alpha = image.getchannel("A")
    top = alpha.crop((0, 0, alpha.width, 1)).getbbox()
    bottom = alpha.crop((0, alpha.height - 1, alpha.width, alpha.height)).getbbox()
    left = alpha.crop((0, 0, 1, alpha.height)).getbbox()
    right = alpha.crop((alpha.width - 1, 0, alpha.width, alpha.height)).getbbox()
    return not any((top, bottom, left, right))


def visible_colored_edge_count(image: Image.Image, minimum_alpha: int = 32) -> int:
    rgba = image.convert("RGBA")
    contamination = contamination_mask(rgba)
    alpha = rgba.getchannel("A")
    return sum(
        1
        for marked, opacity in zip(contamination.getdata(), alpha.getdata())
        if marked and opacity >= minimum_alpha
    )


def validate_keyframe_hashes(
    root: Path,
    keyframe_root: Path,
    errors: list[str],
    keyframe_layout: str = "mapped",
) -> None:
    try:
        manifest = json.loads((keyframe_root / "manifest.json").read_text(encoding="utf-8"))
        manifest_actions = manifest["actions"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        errors.append("keyframe manifest: unable to read mapped SHA-256 values")
        return

    if not isinstance(manifest_actions, dict):
        errors.append("keyframe manifest: unable to read mapped SHA-256 values")
        return

    for action in ACTIONS:
        mappings = manifest_actions.get(action, {})
        if not isinstance(mappings, dict):
            errors.append(f"{action}: missing mapped SHA-256 values")
            continue
        for keyframe_index, keyframe_name in enumerate(EXPECTED_KEYFRAME_NAMES):
            mapping = mappings.get(keyframe_name)
            try:
                expected_hash = mapping["sha256"]
            except (KeyError, TypeError):
                errors.append(f"{action}/{keyframe_name}: missing mapped SHA-256 value")
                continue
            if keyframe_layout == "direct":
                final_name = keyframe_name
            else:
                try:
                    final_name = mapping["final_name"]
                except (KeyError, TypeError):
                    errors.append(
                        f"{action}/{keyframe_name}: missing mapped SHA-256 value"
                    )
                    continue
                expected_final_name = f"{KEYFRAME_POSITIONS[keyframe_index]:02d}.png"
                if final_name != expected_final_name:
                    errors.append(
                        f"{action}/{keyframe_name}: must map to {expected_final_name}"
                    )
                    continue
            path = root / action / final_name
            if not path.is_file():
                errors.append(f"{action}/{final_name}: missing mapped keyframe")
                continue
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                errors.append(
                    f"{action}/{final_name}: SHA-256 does not match keyframe manifest"
                )


def validate_assets(
    root: Path,
    keyframe_root: Path | None = None,
    frame_count: int = FRAME_COUNT,
    keyframe_layout: str = "mapped",
) -> dict[str, object]:
    errors: list[str] = []
    total_frames = 0
    expected_names = tuple(f"{index:02d}.png" for index in range(frame_count))
    for action in ACTIONS:
        action_dir = root / action
        paths = sorted(action_dir.glob("*.png"))
        total_frames += len(paths)
        if tuple(path.name for path in paths) != expected_names:
            errors.append(
                f"{action}: expected exactly 00.png through {frame_count - 1:02d}.png"
            )
            continue
        for path in paths:
            with Image.open(path) as image:
                if image.mode != "RGBA" or image.size != EXPECTED_SIZE:
                    errors.append(f"{path}: expected 512x768 RGBA")
                    continue
                minimum, maximum = image.getchannel("A").getextrema()
                if minimum != 0 or maximum != 255:
                    errors.append(f"{path}: expected transparent background and opaque subject")
                    continue
                if not transparent_rgb_is_zero(image):
                    errors.append(f"{path}: transparent RGB must be black")
                if not border_is_transparent(image):
                    errors.append(f"{path}: outer border must be transparent")
                contamination = visible_colored_edge_count(image)
                if contamination:
                    errors.append(
                        f"{path}: colored edge contamination ({contamination} pixels)"
                    )
    if keyframe_root is not None:
        validate_keyframe_hashes(root, keyframe_root, errors, keyframe_layout)
    return {"errors": errors, "actions": len(ACTIONS), "total_frames": total_frames}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--keyframes", "--keyframe-root", dest="keyframe_root", type=Path)
    parser.add_argument("--frame-count", type=int, default=FRAME_COUNT)
    parser.add_argument(
        "--keyframe-layout",
        choices=("mapped", "direct"),
        default="mapped",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_assets(
        args.root,
        args.keyframe_root,
        frame_count=args.frame_count,
        keyframe_layout=args.keyframe_layout,
    )
    if args.report is not None:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    errors = report["errors"]
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: 3 actions, {report['total_frames']} frames, 512x768 RGBA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

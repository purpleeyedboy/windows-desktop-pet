from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ACTIONS = ("jump", "squash", "shake")
EXPECTED_SIZE = (512, 768)


def validate_assets(root: Path) -> list[str]:
    errors: list[str] = []
    for action in ACTIONS:
        action_dir = root / action
        paths = sorted(action_dir.glob("*.png"))
        expected_names = [f"{index:02d}.png" for index in range(6)]
        if [path.name for path in paths] != expected_names:
            errors.append(f"{action}: expected exactly 00.png through 05.png")
            continue
        for path in paths:
            with Image.open(path) as image:
                if image.mode != "RGBA" or image.size != EXPECTED_SIZE:
                    errors.append(f"{path}: expected 512x768 RGBA")
                    continue
                minimum, maximum = image.getchannel("A").getextrema()
                if minimum != 0 or maximum != 255:
                    errors.append(f"{path}: expected transparent background and opaque subject")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    errors = validate_assets(args.root)
    if errors:
        print("\n".join(errors))
        return 1
    print("OK: 3 actions, 18 frames, 512x768 RGBA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

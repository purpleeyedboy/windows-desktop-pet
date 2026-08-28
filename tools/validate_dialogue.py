"""Validate the packaged desktop-pet dialogue library."""

from __future__ import annotations

import sys
from pathlib import Path
from statistics import median

from PIL import ImageFont


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.dialogue import (  # noqa: E402
    ACTIONS,
    DIALOGUE_FONT_SIZE,
    load_phrase_pools,
    validate_phrase_font_coverage,
    validate_phrase_pools,
)


def main() -> int:
    font_path = ROOT / "assets" / "fonts" / "ZCOOLKuaiLe-Regular.ttf"
    try:
        pools = load_phrase_pools(ROOT / "assets" / "dialogue" / "phrases.json")
        validate_phrase_pools(pools)
        minimum_width, maximum_width = validate_phrase_font_coverage(
            pools,
            font_path,
        )
        font = ImageFont.truetype(font_path, DIALOGUE_FONT_SIZE)
        widths = [
            float(font.getlength(phrase))
            for phrases in pools.values()
            for phrase in phrases
        ]
    except (OSError, ValueError) as exc:
        print(f"dialogue validation failed: {exc}", file=sys.stderr)
        return 1

    for action in ACTIONS:
        print(f"{action}: {len(pools[action])} phrases")
    print(
        "font width min/median/max: "
        f"{minimum_width:.1f}/{median(widths):.1f}/{maximum_width:.1f}px"
    )
    unique_count = len({phrase for phrases in pools.values() for phrase in phrases})
    print(f"dialogue validation passed: {unique_count} unique phrases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

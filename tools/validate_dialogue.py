"""Validate the packaged desktop-pet dialogue library."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.dialogue import (  # noqa: E402
    ACTIONS,
    is_kaomoji_phrase,
    load_phrase_pools,
    validate_phrase_rendering,
    validate_phrase_pools,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dialogue",
        type=Path,
        default=ROOT / "assets" / "dialogue" / "phrases.json",
        help="UTF-8 dialogue JSON to validate",
    )
    args = parser.parse_args(argv)
    try:
        pools = load_phrase_pools(args.dialogue)
        validate_phrase_pools(pools)
        stats = validate_phrase_rendering(pools)
    except (OSError, ValueError) as exc:
        print(f"dialogue validation failed: {exc}", file=sys.stderr)
        return 1

    for action in ACTIONS:
        kaomoji_count = sum(is_kaomoji_phrase(phrase) for phrase in pools[action])
        chinese_count = len(pools[action]) - kaomoji_count
        print(f"{action}: {chinese_count} Chinese + {kaomoji_count} kaomoji")
    print(
        "Chinese width min/median/max: "
        f"{stats.chinese.minimum:.1f}/{stats.chinese.median:.1f}/"
        f"{stats.chinese.maximum:.1f}px"
    )
    print(
        "Kaomoji width min/median/max: "
        f"{stats.kaomoji.minimum:.1f}/{stats.kaomoji.median:.1f}/"
        f"{stats.kaomoji.maximum:.1f}px"
    )
    unique_count = len({phrase for phrases in pools.values() for phrase in phrases})
    print(f"dialogue validation passed: {unique_count} unique phrases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Validate the packaged desktop-pet dialogue library."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.dialogue import ACTIONS, load_phrase_pools, validate_phrase_pools  # noqa: E402


def main() -> int:
    try:
        pools = load_phrase_pools(ROOT / "assets" / "dialogue" / "phrases.json")
        validate_phrase_pools(pools)
    except (OSError, ValueError) as exc:
        print(f"dialogue validation failed: {exc}", file=sys.stderr)
        return 1

    for action in ACTIONS:
        print(f"{action}: {len(pools[action])} phrases")
    unique_count = len({phrase for phrases in pools.values() for phrase in phrases})
    print(f"dialogue validation passed: {unique_count} unique phrases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

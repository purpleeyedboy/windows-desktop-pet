"""Apply the fixed, hash-audited 180+20 dialogue migration."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


SOURCE_SHA256 = "927C40426F43C8AAB13FDB3C67C9A551D10B76299C4B82DCC6EDF3109F36D3B2"
FINAL_SHA256 = "829179B422184A92FAA9D164F839D7B8AB0233B08F4E24904961B43EA4CE4CDB"

KAOMOJI = {
    "jump": (
        "₍^. .^₎⟆", r"\(^.^)/", "/(^.^)\\", r"\(^▽^)/",
        "/(^▽^)\\", r"\(^◇^)/", "/(^◇^)\\", r"\(^o^)/",
        "/(^o^)\\", "⌒(^.^)⌒", "⌒(^▽^)⌒", "⌒(^◇^)⌒",
        "o(^.^)o", "O(^.^)O", "o(^▽^)o", "O(^▽^)O",
        r"\(=^.^=)/", "/(=^.^=)\\", "⌒(=^.^=)⌒", "o(=^▽^=)o",
    ),
    "squash": (
        "(=^.^=)", "(=^..^=)", "(=^-.-^=)", "(=x.x=)",
        "(=o.o=)", "(=^_^=)", "(=>.<=)", "(=;.;=)",
        "(=~.~=)", "(=u.u=)", "(=-.-=)", "(=^o^=)",
        "(=^3^=)", "(=._.=)", "(=O.O=)", "₍^. .^₎",
        "₍- . -₎", "₍x . x₎", "₍o . o₎", "₍> . <₎",
    ),
    "shake": (
        "(^._.^)~", "~(^._.^)", "(=^.^=)~", "~(=^.^=)",
        "~(=^.^=)~", "((^.^))", "((=^.^=))", "(@_@;)",
        "(x_x;)", "(o_o;)", "(>_<;)", "(=;o;=)",
        "(=;_;=)", "(=x_x=)", "(^.^)~~", "~~(^.^)",
        "(=^.^=)>", "<(=^.^=)", ">(=x.x=)<", "~(=x.x=)~",
    ),
}


def migrate(pools: dict[str, list[str]]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for action in ("jump", "squash", "shake"):
        result: list[str] = []
        for block in range(5):
            start = block * 40
            result.extend(pools[action][start : start + 36])
            result.extend(KAOMOJI[action][block * 4 : block * 4 + 4])
        output[action] = result
    return output


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dialogue", type=Path, help="source phrases.json to migrate in place")
    args = parser.parse_args(argv)

    current_sha256 = _sha256(args.dialogue)
    if current_sha256 == FINAL_SHA256:
        print(f"dialogue already migrated: SHA-256 {FINAL_SHA256}")
        return 0
    if current_sha256 != SOURCE_SHA256:
        print(
            f"dialogue migration refused: expected SHA-256 {SOURCE_SHA256} or "
            f"{FINAL_SHA256}; found {current_sha256}",
            file=sys.stderr,
        )
        return 1

    pools = json.loads(args.dialogue.read_text(encoding="utf-8"))
    payload = (json.dumps(migrate(pools), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    predicted_sha256 = hashlib.sha256(payload).hexdigest().upper()
    if predicted_sha256 != FINAL_SHA256:
        print(
            f"dialogue migration refused: generated SHA-256 {predicted_sha256}; "
            f"expected {FINAL_SHA256}",
            file=sys.stderr,
        )
        return 1

    args.dialogue.write_bytes(payload)
    written_sha256 = _sha256(args.dialogue)
    if written_sha256 != FINAL_SHA256:
        print(
            f"dialogue migration failed after write: found SHA-256 {written_sha256}; "
            f"expected {FINAL_SHA256}",
            file=sys.stderr,
        )
        return 1
    print(f"dialogue migrated: SHA-256 {written_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

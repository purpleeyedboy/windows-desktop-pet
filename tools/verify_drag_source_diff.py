"""Fail when the V2.1-DRAG source diff contains binary entries or asset drift."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ASSET_COUNT = 158


class GateError(RuntimeError):
    pass


def git(*args: str, text: bool = False) -> bytes | str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=text)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise GateError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_text_diff(baseline: str) -> int:
    numstat = str(git("diff", "--numstat", baseline, "--", text=True))
    binary = []
    for line in numstat.splitlines():
        added, deleted, path = line.split("\t", 2)
        if added == "-" or deleted == "-":
            binary.append(path)
    if binary:
        raise GateError("binary diff entries are forbidden: " + ", ".join(binary))
    untracked = str(git("ls-files", "--others", "--exclude-standard", "-z", text=True)).split("\0")
    for relative in filter(None, untracked):
        data = (ROOT / relative).read_bytes()
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise GateError(f"untracked binary file is forbidden: {relative}") from error
        if b"\0" in data:
            raise GateError(f"untracked binary file is forbidden: {relative}")
    return len(binary)


def verify_assets(baseline: str) -> int:
    names = str(git("-c", "core.quotePath=false", "ls-tree", "-r", "--name-only", baseline, "--", "assets", text=True)).splitlines()
    if len(names) != EXPECTED_ASSET_COUNT:
        raise GateError(f"baseline approved asset count is {len(names)}; expected {EXPECTED_ASSET_COUNT}")
    current = [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "assets").rglob("*")) if path.is_file()]
    if current != names:
        raise GateError("approved asset path set differs from baseline")
    for name in names:
        if _sha256(git("show", f"{baseline}:{name}")) != _sha256((ROOT / name).read_bytes()):
            raise GateError(f"approved asset changed: {name}")
    return len(names)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    args = parser.parse_args(argv)
    try:
        binary_count = verify_text_diff(args.baseline)
        asset_count = verify_assets(args.baseline)
    except (GateError, OSError) as error:
        print(f"drag source diff gate failed: {error}", file=sys.stderr)
        return 1
    print(f"binary diff entries: {binary_count}")
    print(f"approved assets unchanged: {asset_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

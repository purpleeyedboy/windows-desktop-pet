"""Release gates for the text-only V2.1-PAWS change set."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class DiffReport:
    changed_paths: tuple[str, ...]
    binary_paths: tuple[str, ...]


def inspect_release_diff(root: Path, baseline: str) -> DiffReport:
    completed = subprocess.run(
        ["git", "diff", "--numstat", baseline, "--"], cwd=root,
        check=True, capture_output=True, text=True,
    )
    changed, binary = [], []
    for line in completed.stdout.splitlines():
        added, deleted, path = line.split("\t", 2)
        changed.append(path)
        if added == "-" or deleted == "-":
            binary.append(path)
    return DiffReport(tuple(changed), tuple(binary))


def verify_baseline_assets(manifest: Path, root: Path) -> int:
    entries = manifest.read_text(encoding="utf-8").splitlines()
    if len(entries) != 158:
        raise ValueError(f"expected 158 baseline assets, found {len(entries)}")
    seen = set()
    for entry in entries:
        digest, relative = entry.split("  ", 1)
        if relative in seen or not relative.startswith("assets/"):
            raise ValueError(f"invalid baseline asset entry: {relative}")
        seen.add(relative)
        path = root / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f"baseline asset SHA-256 mismatch: {relative}")
    return len(entries)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = inspect_release_diff(root, "c3b218d")
    if report.binary_paths:
        raise SystemExit("binary paths in V2.1-PAWS diff: " + ", ".join(report.binary_paths))
    count = verify_baseline_assets(root / "assets/v2.1-baseline.sha256", root)
    print(f"V2.1-PAWS gate passed: text-only diff; {count} baseline asset hashes unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify the V2.1-DRAG archive, including its immutable build metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

from tools.verify_eye_follow_candidate_archive import (
    VerificationError,
    normalized_archive_members,
    verify_archive,
)


ROOT = Path(__file__).resolve().parents[1]
METADATA = "DRAG_EXPECTATION_BUILD_INFO.json"


def verify_drag_archive(executable: Path) -> None:
    verify_archive(executable)
    archive = CArchiveReader(str(executable))
    members = normalized_archive_members(archive.toc)
    if METADATA not in members:
        raise VerificationError(f"required archive resource is missing: {METADATA}")
    actual = archive.extract(members[METADATA])
    expected = (ROOT / METADATA).read_bytes()
    if actual != expected:
        raise VerificationError(f"byte mismatch for archive resource: {METADATA}")
    print("Drag candidate metadata verification passed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args(argv)
    try:
        verify_drag_archive(args.executable)
    except (OSError, VerificationError) as error:
        print(f"drag archive verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

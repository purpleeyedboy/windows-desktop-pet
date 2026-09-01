"""Verify the PyInstaller archive inside the eye-follow candidate EXE."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


ROOT = Path(__file__).resolve().parents[1]
STABLE_RESOURCE_ROOTS = (
    "assets/keyframes",
    "assets/bubble",
    "assets/fonts",
    "assets/dialogue",
)
NOTICE = "THIRD_PARTY_NOTICES.txt"
EYE_SOURCE = "assets/rig/v1/source/eye-neutral-v1"
EYE_RUNTIME = "assets/rig/v1/runtime/eye-neutral-v1"
EYE_FILES = (
    "authoring.json",
    "body-backplate.png",
    "eye-left-mask.png",
    "eye-left.png",
    "eye-right-mask.png",
    "eye-right.png",
    "underlay.png",
)


class VerificationError(RuntimeError):
    """The candidate archive does not meet its resource contract."""


def archive_name(path: Path) -> str:
    return path.as_posix()


def stable_resources() -> dict[str, Path]:
    expected: dict[str, Path] = {}
    for root in STABLE_RESOURCE_ROOTS:
        source_root = ROOT / root
        if not source_root.is_dir():
            raise VerificationError(f"required stable resource directory is missing: {root}")
        for source_path in sorted(source_root.rglob("*")):
            if source_path.is_file():
                expected[archive_name(source_path.relative_to(ROOT))] = source_path

    notice_path = ROOT / NOTICE
    if not notice_path.is_file():
        raise VerificationError(f"required stable resource is missing: {NOTICE}")
    expected[NOTICE] = notice_path
    return expected


def expected_resources() -> tuple[dict[str, Path], dict[str, Path]]:
    stable = stable_resources()
    eyes: dict[str, Path] = {}
    for file_name in EYE_FILES:
        source_path = ROOT / EYE_SOURCE / file_name
        if not source_path.is_file():
            raise VerificationError(f"required neutral-eye source is missing: {EYE_SOURCE}/{file_name}")
        eyes[f"{EYE_RUNTIME}/{file_name}"] = source_path
    return stable, eyes


def validate_forbidden_paths(names: set[str]) -> None:
    for name in names:
        normalized = name.replace("\\", "/")
        if normalized.startswith("assets/rig/v1/source/"):
            raise VerificationError(f"forbidden rig source archive path: {normalized}")
        if normalized.startswith("qa/"):
            raise VerificationError(f"forbidden QA archive path: {normalized}")
        if normalized.lower().endswith(".gif") and not normalized.startswith("_tk_data/"):
            raise VerificationError(f"forbidden GIF archive path: {normalized}")


def normalized_archive_members(raw_names: Iterable[str]) -> dict[str, str]:
    members: dict[str, str] = {}
    for raw_name in raw_names:
        normalized = raw_name.replace("\\", "/")
        previous = members.get(normalized)
        if previous is not None and previous != raw_name:
            raise VerificationError(
                "normalized archive path collision: "
                f"{previous!r} and {raw_name!r} both map to {normalized!r}"
            )
        members[normalized] = raw_name
    return members


def verify_archive(executable: Path) -> None:
    if not executable.is_file():
        raise VerificationError(f"candidate executable is missing: {executable}")

    try:
        archive = CArchiveReader(str(executable))
    except Exception as error:  # PyInstaller raises several reader-specific exceptions.
        raise VerificationError(f"archive read error: {error}") from error

    members = normalized_archive_members(archive.toc)
    names = set(members)
    validate_forbidden_paths(names)
    stable, eyes = expected_resources()
    runtime_members = {
        name
        for name in names
        if name.startswith(f"{EYE_RUNTIME}/")
    }
    unexpected_runtime_members = runtime_members - set(eyes)
    if unexpected_runtime_members:
        unexpected = ", ".join(sorted(unexpected_runtime_members))
        raise VerificationError(f"unexpected neutral-eye runtime archive resource: {unexpected}")
    expected = stable | eyes
    for member_name, source_path in expected.items():
        if member_name not in names:
            raise VerificationError(f"required archive resource is missing: {member_name}")
        try:
            actual = archive.extract(members[member_name])
        except Exception as error:
            raise VerificationError(f"archive read error for {member_name}: {error}") from error
        try:
            source = source_path.read_bytes()
        except OSError as error:
            raise VerificationError(f"source read error for {member_name}: {error}") from error
        if actual != source:
            raise VerificationError(f"byte mismatch for archive resource: {member_name}")

    print(
        "Archive verification passed: "
        f"stable {len(stable)}, neutral-eye {len(eyes)}, total {len(expected)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args(argv)
    try:
        verify_archive(args.executable)
    except VerificationError as error:
        print(f"archive verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

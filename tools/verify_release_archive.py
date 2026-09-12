"""Verify that a PyInstaller one-file archive contains exact release assets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyInstaller.archive.readers import ArchiveReadError, CArchiveReader


ROOT = Path(__file__).resolve().parents[1]


def _release_resource_groups(
    project_root: Path, *, require_paws: bool = False
) -> dict[str, list[Path]]:
    groups = {
        "keyframes": sorted((project_root / "assets" / "keyframes").glob("*/*.png")),
        "bubbles": sorted((project_root / "assets" / "bubble").glob("*.png")),
        "fonts": sorted((project_root / "assets" / "fonts").glob("*.ttf")),
        "licenses": sorted(
            (project_root / "assets" / "fonts" / "licenses").glob("*.txt")
        ),
        "dialogue": [project_root / "assets" / "dialogue" / "phrases.json"],
        "notice": [project_root / "THIRD_PARTY_NOTICES.txt"],
    }
    if require_paws:
        groups["paws"] = sorted((project_root / "assets" / "paws").glob("v1/*"))
    return groups


def verify_archive(exe: Path, project_root: Path, *, require_paws: bool = False) -> None:
    archive = CArchiveReader(str(exe))
    normalized = {name.replace("\\", "/"): name for name in archive.toc}
    groups = _release_resource_groups(project_root, require_paws=require_paws)
    required_files = [source for files in groups.values() for source in files]
    for source in required_files:
        relative = source.relative_to(project_root).as_posix()
        archived_name = normalized.get(relative)
        if archived_name is None:
            raise ValueError(f"missing archive resource: {relative}")
        if archive.extract(archived_name) != source.read_bytes():
            raise ValueError(f"archive resource differs from source: {relative}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path, help="PyInstaller one-file executable")
    parser.add_argument("--require-paws", action="store_true")
    args = parser.parse_args(argv)
    try:
        verify_archive(args.exe, ROOT, require_paws=args.require_paws)
    except (ArchiveReadError, OSError, ValueError) as exc:
        print(f"release archive verification failed: {exc}", file=sys.stderr)
        return 1

    counts = {
        category: len(files)
        for category, files in _release_resource_groups(
            ROOT, require_paws=args.require_paws
        ).items()
    }
    print(
        "release archive verified: "
        f"keyframes {counts['keyframes']}, bubbles {counts['bubbles']}, "
        f"fonts {counts['fonts']}, licenses {counts['licenses']}, "
        f"dialogue {counts['dialogue']}, notice {counts['notice']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify that the frozen candidate contains the complete simulation transaction core."""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_MODULES = (
    "desktop_pet.feed_core.model",
    "desktop_pet.feed_core.validation",
    "desktop_pet.feed_core.journal",
    "desktop_pet.feed_core.coordinator",
    "desktop_pet.feed_core.adapters",
    "desktop_pet.feed_core.wiring",
    "desktop_pet.feed_core.windows_drop",
    "desktop_pet.feed_core.windows_recycle",
)


def missing_required_modules(names) -> list[str]:
    available = set(names)
    return [name for name in REQUIRED_MODULES if name not in available]


def archived_python_modules(executable: Path) -> set[str]:
    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(executable))
    names = set(archive.toc)
    pyz_entry = next((name for name in archive.toc if name.endswith("PYZ.pyz")), None)
    if pyz_entry is None:
        raise RuntimeError("frozen executable has no embedded PYZ archive")
    pyz = archive.open_embedded_archive(pyz_entry)
    names.update(pyz.toc)
    return names


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit("usage: verify_feed_core_archive.py <candidate.exe>")
    executable = Path(args[0])
    missing = missing_required_modules(archived_python_modules(executable))
    if missing:
        raise RuntimeError(f"candidate archive is missing feed_core modules: {missing}")
    print(f"verified {len(REQUIRED_MODULES)} feed_core modules in {executable.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

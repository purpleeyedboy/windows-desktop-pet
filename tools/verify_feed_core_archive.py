"""Verify that the frozen candidate contains the complete simulation transaction core."""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_MODULES = (
    "desktop_pet.feed_core.foundation_contract",
    "desktop_pet.feed_core.business",
    "desktop_pet.feed_core.progress_receipt",
    "desktop_pet.feed_core.confirmation",
    "desktop_pet.feed_core.recovery",
    "desktop_pet.feed_core.review",
    "desktop_pet.feed_core.windows_identity",
    "desktop_pet.feed_core.windows_recycle",
    "desktop_pet.feed_core.wiring",
    "desktop_pet.feed_core.windows_drop",
    "desktop_pet.feed_animation",
)

REQUIRED_RESOURCES = tuple(
    f"assets/feed/v1/frames/{index:02d}.png" for index in range(6)
)


def missing_required_modules(names) -> list[str]:
    available = set(names)
    return [name for name in REQUIRED_MODULES if name not in available]


def missing_required_resources(names) -> list[str]:
    normalized = {str(name).replace("\\", "/") for name in names}
    return sorted(name for name in REQUIRED_RESOURCES if name not in normalized)


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
    archived = archived_python_modules(executable)
    missing = missing_required_modules(archived)
    if missing:
        raise RuntimeError(f"candidate archive is missing feed_core modules: {missing}")
    missing_resources = missing_required_resources(archived)
    if missing_resources:
        raise RuntimeError(f"candidate archive is missing FEED frames: {missing_resources}")
    print(
        f"verified {len(REQUIRED_MODULES)} feed modules and "
        f"{len(REQUIRED_RESOURCES)} real FEED frames"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

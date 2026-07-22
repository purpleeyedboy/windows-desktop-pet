"""Archive the approved six-frame source poses for later interpolation."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ACTIONS = ("jump", "squash", "shake")
FINAL_POSITIONS = (0, 6, 12, 17, 23, 29)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_keyframes(source_root: Path, archive_root: Path) -> dict[str, object]:
    manifest: dict[str, object] = {
        "version": 1,
        "frame_size": [512, 768],
        "final_positions": list(FINAL_POSITIONS),
        "actions": {},
    }
    actions: dict[str, dict[str, dict[str, object]]] = manifest["actions"]  # type: ignore[assignment]

    for action in ACTIONS:
        entries: dict[str, dict[str, object]] = {}
        target_dir = archive_root / action
        target_dir.mkdir(parents=True, exist_ok=True)
        for index, final_index in enumerate(FINAL_POSITIONS):
            name = f"{index:02d}.png"
            source = source_root / action / name
            target = target_dir / name
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise RuntimeError(f"keyframe mismatch: {action}/{name}")
            if not target.exists():
                shutil.copy2(source, target)
            entries[name] = {
                "sha256": sha256_file(target),
                "size": target.stat().st_size,
                "final_name": f"{final_index:02d}.png",
            }
        actions[action] = entries

    (archive_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive immutable animation keyframes.")
    parser.add_argument("source_root", type=Path)
    parser.add_argument("archive_root", type=Path)
    arguments = parser.parse_args()
    archive_keyframes(arguments.source_root, arguments.archive_root)
    print("OK: archived 18 immutable keyframes")


if __name__ == "__main__":
    main()

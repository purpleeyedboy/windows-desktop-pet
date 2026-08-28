from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


CANVAS = (512, 768)
CANONICAL_SHA256 = "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"


def sha256_path(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _border_is_transparent(image: Image.Image) -> bool:
    alpha = image.getchannel("A")
    return not any((
        alpha.crop((0, 0, alpha.width, 1)).getbbox(),
        alpha.crop((0, alpha.height - 1, alpha.width, alpha.height)).getbbox(),
        alpha.crop((0, 0, 1, alpha.height)).getbbox(),
        alpha.crop((alpha.width - 1, 0, alpha.width, alpha.height)).getbbox(),
    ))


def validate_rgba(path: Path) -> list[str]:
    with Image.open(path) as opened:
        if opened.mode != "RGBA" or opened.size != CANVAS:
            return ["expected 512x768 RGBA"]
        image = opened.copy()
    errors: list[str] = []
    if any((r, g, b) != (0, 0, 0) for r, g, b, a in image.getdata() if a == 0):
        errors.append("Alpha-0 RGB must be zero")
    if not _border_is_transparent(image):
        errors.append("outer border must be transparent")
    return errors


def copy_canonical(source: Path, destination: Path) -> dict[str, object]:
    source = Path(source)
    destination = Path(destination)
    actual = sha256_path(source)
    if actual != CANONICAL_SHA256:
        raise RuntimeError(f"canonical SHA-256 mismatch: {actual}")
    errors = validate_rgba(source)
    if errors:
        raise RuntimeError("; ".join(errors))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_bytes() != source.read_bytes():
        raise RuntimeError("existing canonical copy differs")
    if not destination.exists():
        destination.write_bytes(source.read_bytes())
    return {"sha256": actual, "mode": "RGBA", "size": [512, 768]}

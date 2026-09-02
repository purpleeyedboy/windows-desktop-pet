"""Build runtime layers from the exact approved head and body PNGs."""

from __future__ import annotations

import hashlib
import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Final

from PIL import Image, ImageChops


HEAD_OFFSET: Final = (24, 204)
APPROVED_HEAD_SHA256: Final = (
    "6e57c1be03db1a97a484576f6f88be8639d8f01bbfe5b0d792c68e3d985864e6"
)
APPROVED_BODY_SHA256: Final = (
    "527eaad70a84c611f0839bc3898b5c00f41df383c191771c7e07a1af588e5ce8"
)
PREVIOUS_UNDERLAY_SHA256: Final = (
    "28bc087f2d45a9e2dc2774c96a0b853b55b65795726d0eecb374d90310c5aac9"
)
DERIVED_UNDERLAY_SHA256: Final = (
    "d83230b60fe753b7344ae0b349d0c1409b47dc2002df66c5689765fcb0ca2495"
)
EYE_LEFT_MASK_SHA256: Final = (
    "27bee30342e67cab45d77a14ad7eebb0125f72d4b19039b5c3c1bf506623a81c"
)
EYE_RIGHT_MASK_SHA256: Final = (
    "fba54f4eb10884d5a284ea6c16cd762d0786f61e09ddc5297e99d793c3a092e4"
)
APPROVED_HEAD_NAME: Final = "猫头-精准抠图.png"
APPROVED_BODY_NAME: Final = "猫身-原像素保留-仅补头部缺口.png"
CANVAS_SIZE: Final = (512, 768)
HEAD_SIZE: Final = (230, 241)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_exact(
    data: bytes, filename: str, mode: str, size: tuple[int, int]
) -> Image.Image:
    try:
        with Image.open(BytesIO(data)) as opened:
            opened.load()
            if opened.mode != mode or opened.size != size:
                raise ValueError(
                    f"invalid {filename}: expected {mode} {size[0]}x{size[1]}"
                )
            return opened.copy()
    except OSError as error:
        raise ValueError(f"invalid {filename}") from error


def _read_approved(
    path: Path, expected_hash: str, size: tuple[int, int]
) -> tuple[bytes, Image.Image]:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ValueError(f"invalid approved source {path.name}") from error
    if _sha256(data) != expected_hash:
        raise ValueError(f"approved source SHA mismatch for {path.name}")
    return data, _decode_exact(data, path.name, "RGBA", size)


def _read_runtime_image(
    runtime_source_dir: Path, filename: str, mode: str
) -> tuple[bytes, Image.Image]:
    try:
        data = (runtime_source_dir / filename).read_bytes()
    except OSError as error:
        raise ValueError(f"invalid {filename}") from error
    return data, _decode_exact(data, filename, mode, CANVAS_SIZE)


def _temporary_path(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp.png",
    )
    os.close(descriptor)
    return Path(name)


def _clear_transparent_rgb(image: Image.Image) -> Image.Image:
    visible = image.getchannel("A").point(lambda alpha: 255 if alpha else 0)
    return Image.composite(image, Image.new("RGBA", image.size), visible)


def build(
    approved_dir: Path, runtime_source_dir: Path
) -> dict[str, str]:
    """Validate approved inputs and atomically replace the two derived layers."""

    approved_dir = Path(approved_dir)
    runtime_source_dir = Path(runtime_source_dir)
    head_path = approved_dir / APPROVED_HEAD_NAME
    body_path = approved_dir / APPROVED_BODY_NAME
    body_bytes, body = _read_approved(
        body_path, APPROVED_BODY_SHA256, CANVAS_SIZE
    )
    _, head = _read_approved(head_path, APPROVED_HEAD_SHA256, HEAD_SIZE)
    previous_underlay_bytes, previous_underlay = _read_runtime_image(
        runtime_source_dir, "underlay.png", "RGBA"
    )
    left_mask_bytes, left_mask = _read_runtime_image(
        runtime_source_dir, "eye-left-mask.png", "L"
    )
    right_mask_bytes, right_mask = _read_runtime_image(
        runtime_source_dir, "eye-right-mask.png", "L"
    )
    if _sha256(left_mask_bytes) != EYE_LEFT_MASK_SHA256:
        raise ValueError("eye-left-mask.png SHA mismatch")
    if _sha256(right_mask_bytes) != EYE_RIGHT_MASK_SHA256:
        raise ValueError("eye-right-mask.png SHA mismatch")

    previous_underlay_hash = _sha256(previous_underlay_bytes)
    if previous_underlay_hash == DERIVED_UNDERLAY_SHA256:
        underlay = previous_underlay
    elif previous_underlay_hash == PREVIOUS_UNDERLAY_SHA256:
        approved_composite = body.copy()
        approved_composite.alpha_composite(head, HEAD_OFFSET)
        eye_union = ImageChops.lighter(left_mask, right_mask)
        underlay = Image.composite(
            previous_underlay, approved_composite, eye_union
        )
        underlay = _clear_transparent_rgb(underlay)
    else:
        raise ValueError("underlay.png SHA is neither previous nor derived")

    underlay_path = runtime_source_dir / "underlay.png"
    backplate_path = runtime_source_dir / "body-backplate.png"
    temporary_underlay = _temporary_path(underlay_path)
    temporary_backplate = _temporary_path(backplate_path)
    rollback_underlay = _temporary_path(underlay_path)
    try:
        underlay.save(temporary_underlay, format="PNG")
        temporary_backplate.write_bytes(body_bytes)
        rollback_underlay.write_bytes(previous_underlay_bytes)

        underlay_bytes = temporary_underlay.read_bytes()
        written_body_bytes = temporary_backplate.read_bytes()
        _decode_exact(
            underlay_bytes, underlay_path.name, "RGBA", CANVAS_SIZE
        )
        _decode_exact(
            written_body_bytes, backplate_path.name, "RGBA", CANVAS_SIZE
        )
        if written_body_bytes != body_bytes:
            raise ValueError("body-backplate.png bytes differ from approved body")
        if _sha256(underlay_bytes) != DERIVED_UNDERLAY_SHA256:
            raise ValueError("derived underlay.png SHA mismatch")

        os.replace(temporary_underlay, underlay_path)
        try:
            os.replace(temporary_backplate, backplate_path)
        except BaseException:
            os.replace(rollback_underlay, underlay_path)
            raise
    finally:
        temporary_underlay.unlink(missing_ok=True)
        temporary_backplate.unlink(missing_ok=True)
        rollback_underlay.unlink(missing_ok=True)

    return {
        "underlay.png": _sha256(underlay_bytes),
        "body-backplate.png": _sha256(written_body_bytes),
    }


if __name__ == "__main__":
    repository_root = Path(__file__).resolve().parents[1]
    hashes = build(
        repository_root / "assets/rig/v1/source/approved",
        repository_root / "assets/rig/v1/source/eye-neutral-v1",
    )
    for filename, digest in hashes.items():
        print(f"{filename}: {digest}")

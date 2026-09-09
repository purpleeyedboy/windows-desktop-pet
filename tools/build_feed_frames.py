"""Build six real FEED frames from local generated art and the accepted neutral."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import sys
from uuid import uuid4
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class BuiltFrame:
    name: str
    path: Path
    sha256: str


def build_local_face_assets(manifest_path: Path, manifest: dict, output_root: Path) -> list[BuiltFrame]:
    """Author real full frames over the exact accepted neutral head/body.

    Only generated muzzle/jaw and eyelid patches are allowed to change pixels.
    This is a build-time graphic composition, never a runtime geometry effect.
    """
    checkout = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(checkout / 'src'))
    from desktop_pet.assets import load_head_neck_compositor
    from desktop_pet.head_neck_deformation import HeadPose

    base = load_head_neck_compositor().compose(0, 0, HeadPose(0, 0))
    if hashlib.sha256(base.tobytes()).hexdigest() != manifest['canonical']['neutral_rgba_sha256']:
        raise RuntimeError('accepted neutral head/body pixel hash changed')
    if list(base.size) != manifest['canonical']['canvas']:
        raise RuntimeError('local face canvas differs from accepted neutral')
    bundle = json.loads((manifest_path.parent/'source'/manifest['source_bundle']).read_text(encoding='ascii'))
    if bundle.get('version') != 2 or set(bundle.get('patches', {})) != {'half', 'wide', 'upper', 'corner'}:
        raise RuntimeError('invalid local face source bundle')
    left, top, right, bottom = bundle['patch_box']
    patches = {}
    for name, record in bundle['patches'].items():
        data = base64.b64decode(''.join(record['png_base64']), validate=True)
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            raise RuntimeError(f'local face source hash mismatch: {name}')
        with Image.open(io.BytesIO(data)) as opened:
            if opened.size != (right-left, bottom-top) or opened.mode != 'RGB':
                raise RuntimeError(f'local face source dimensions/mode invalid: {name}')
            patches[name] = opened.copy()
    output_root.mkdir(parents=True, exist_ok=True)
    built = []
    face_left, face_top, face_right, face_bottom = manifest['canonical']['face_region']
    if (face_left, face_top, face_right, face_bottom) != (left+64, top, right+64, bottom):
        raise RuntimeError('face patch region must retain the fixed canonical translation')
    for index, name in enumerate(manifest['frame_patches']):
        frame = base.copy()
        if name is not None:
            mask = Image.new('L', patches[name].size)
            rules = manifest['face_patch_masks'][name]
            for y in range(top, bottom):
                for x in range(left, right):
                    if base.getpixel((x+64, y))[3] != 255:
                        continue
                    opacity = 0.0
                    for l, t, r, b in rules['ellipses']:
                        distance = math.hypot((x-(l+r)/2)/((r-l)/2), (y-(t+b)/2)/((b-t)/2))
                        weight = max(0.0, min(1.0, (1.0-distance)/0.25))
                        opacity = max(opacity, weight*weight*(3-2*weight))
                    if rules.get('lower_left_guard') and y > 414:
                        # Keep generated outside-head backgrounds out of the jaw seam.
                        safe_left = 75 + (y-414)*0.75
                        edge = max(0.0, min(1.0, (x-safe_left)/6))
                        opacity *= edge*edge*(3-2*edge)
                    mask.putpixel((x-left, y-top), round(opacity*255))
            frame.paste(patches[name], (face_left, face_top), mask)
            frame.putalpha(base.getchannel('A'))
        path = output_root/f'{index:02d}.png'
        encoded = io.BytesIO()
        frame.save(encoded, format='PNG', compress_level=9)
        temporary = path.with_name(f'.{path.name}.{uuid4().hex}.tmp')
        try:
            temporary.write_bytes(encoded.getvalue())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        built.append(BuiltFrame(path.name, path, hashlib.sha256(path.read_bytes()).hexdigest()))
    return built


def _foreground(pixel: tuple[int, ...] | int) -> bool:
    values = (pixel,) if isinstance(pixel, int) else pixel
    return max(values[:3]) >= 128


def decode_source_bundle(bundle_path: Path) -> dict[str, bytes]:
    """Strictly decode the one line-wrapped text bundle used for code review."""
    payload = json.loads(Path(bundle_path).read_text(encoding="ascii"))
    if payload.get("version") != 1 or set(payload) != {"version", "color", "mask"}:
        raise RuntimeError("invalid FEED source bundle structure")
    decoded = {}
    for name in ("color", "mask"):
        lines = payload[name]
        if not isinstance(lines, list) or not lines or any(
            not isinstance(line, str) or len(line) > 112 for line in lines
        ):
            raise RuntimeError(f"invalid {name} base64 lines")
        try:
            decoded[name] = base64.b64decode("".join(lines), validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise RuntimeError(f"invalid {name} base64 payload") from error
    return decoded


def locate_subjects(mask_source: Path | Image.Image) -> list[tuple[int, int, int, int]]:
    """Locate the six large connected subjects; no equal-grid crop is used."""
    if isinstance(mask_source, Image.Image):
        mask = mask_source.convert("RGB")
    else:
        with Image.open(mask_source) as opened:
            mask = opened.convert("RGB")
    factor = 4
    probe = mask.resize(
        (mask.width // factor, mask.height // factor), Image.Resampling.NEAREST
    )
    width, height = probe.size
    foreground = bytearray(
        1 if _foreground(pixel) else 0 for pixel in probe.getdata()
    )
    components: list[tuple[int, int, int, int, int]] = []
    for start in range(width * height):
        if not foreground[start]:
            continue
        foreground[start] = 0
        stack = [start]
        left = right = start % width
        top = bottom = start // width
        count = 0
        while stack:
            point = stack.pop()
            x, y = point % width, point // width
            count += 1
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)
            for neighbor in (point - 1, point + 1, point - width, point + width):
                if (
                    0 <= neighbor < width * height
                    and foreground[neighbor]
                    and (neighbor // width == y or neighbor % width == x)
                ):
                    foreground[neighbor] = 0
                    stack.append(neighbor)
        if count >= 1000:
            components.append((count, left, top, right + 1, bottom + 1))
    if len(components) != 6:
        raise RuntimeError(f"mask must contain six large connected subjects; found {len(components)}")

    boxes: list[tuple[int, int, int, int]] = []
    pixels = mask.load()
    for _, left, top, right, bottom in components:
        rough = (
            max(0, left * factor - factor),
            max(0, top * factor - factor),
            min(mask.width, right * factor + factor),
            min(mask.height, bottom * factor + factor),
        )
        points = [
            (x, y)
            for y in range(rough[1], rough[3])
            for x in range(rough[0], rough[2])
            if _foreground(pixels[x, y])
        ]
        boxes.append(
            (
                min(x for x, _ in points),
                min(y for _, y in points),
                max(x for x, _ in points) + 1,
                max(y for _, y in points) + 1,
            )
        )
    return sorted(boxes, key=lambda box: (box[1], box[0]))


def _open_verified_source(
    name: str, data: bytes, expected_sha: str, expected_size: tuple[int, int]
) -> Image.Image:
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise RuntimeError(f"source SHA-256 mismatch: {name}")
    with Image.open(io.BytesIO(data)) as image:
        if image.size != expected_size:
            raise RuntimeError(f"source size mismatch: {name}")
        result = image.convert("RGB")
        result.load()
    return result


def _isolated_alpha(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """Keep only the largest connected subject plus its anti-aliased edge."""
    cropped = mask.crop(box).convert("RGB")
    width, height = cropped.size
    values = [max(pixel) for pixel in cropped.getdata()]
    remaining = bytearray(1 if value >= 128 else 0 for value in values)
    largest: list[int] = []
    for start in range(width * height):
        if not remaining[start]:
            continue
        remaining[start] = 0
        stack = [start]
        component: list[int] = []
        while stack:
            point = stack.pop()
            component.append(point)
            x, y = point % width, point // width
            for neighbor in (point - 1, point + 1, point - width, point + width):
                if (
                    0 <= neighbor < width * height
                    and remaining[neighbor]
                    and (neighbor // width == y or neighbor % width == x)
                ):
                    remaining[neighbor] = 0
                    stack.append(neighbor)
        if len(component) > len(largest):
            largest = component
    selected = bytearray(width * height)
    for point in largest:
        x, y = point % width, point // width
        for edge_y in range(max(0, y - 1), min(height, y + 2)):
            for edge_x in range(max(0, x - 1), min(width, x + 2)):
                edge = edge_y * width + edge_x
                selected[edge] = max(selected[edge], values[edge])
    alpha = Image.new("L", cropped.size)
    alpha.putdata(selected)
    return alpha


def build_feed_assets(manifest_path: Path, output_root: Path) -> list[BuiltFrame]:
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get('version') == 2 and manifest.get('composite_mode') == 'canonical_local_face':
        return build_local_face_assets(manifest_path, manifest, output_root)
    source_root = manifest_path.parent / "source"
    expected_size = tuple(manifest["source_size"])
    sources = manifest["sources"]
    decoded = decode_source_bundle(source_root / manifest["source_bundle"])
    color = _open_verified_source(
        "color", decoded["color"], sources["color"]["sha256"], expected_size
    )
    mask = _open_verified_source(
        "mask", decoded["mask"], sources["mask"]["sha256"], expected_size
    )
    boxes = locate_subjects(mask)
    canonical = manifest["canonical"]
    canvas_size = tuple(canonical["canvas"])
    target_height = int(canonical["subject_height"])
    feet_y = int(canonical["feet_y"])
    center_x = int(canonical["center_x"])
    output_root.mkdir(parents=True, exist_ok=True)

    built: list[BuiltFrame] = []
    for index, box in enumerate(boxes):
        subject = color.crop(box).convert("RGBA")
        subject.putalpha(_isolated_alpha(mask, box))
        width = max(1, round(subject.width * target_height / subject.height))
        subject = subject.resize((width, target_height), Image.Resampling.LANCZOS)
        frame = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        frame.alpha_composite(subject, (center_x - width // 2, feet_y - target_height))
        path = output_root / f"{index:02d}.png"
        frame.save(path, format="PNG", optimize=False, compress_level=9)
        built.append(BuiltFrame(path.name, path, hashlib.sha256(path.read_bytes()).hexdigest()))
    return built


def write_contact_sheets(frames: list[BuiltFrame], output_root: Path) -> None:
    """Write untracked black/white/checker evidence from the actual RGBA frames."""
    output_root.mkdir(parents=True, exist_ok=True)
    thumb_size = (320, 384)
    for background in ("black", "white", "checker"):
        sheet = Image.new("RGB", (thumb_size[0] * 3, thumb_size[1] * 2))
        for index, built in enumerate(frames):
            with Image.open(built.path) as opened:
                frame = opened.convert("RGBA").resize(thumb_size, Image.Resampling.LANCZOS)
            if background == "checker":
                tile = 16
                base = Image.new("RGB", thumb_size)
                pixels = base.load()
                for y in range(thumb_size[1]):
                    for x in range(thumb_size[0]):
                        shade = 224 if (x // tile + y // tile) % 2 == 0 else 160
                        pixels[x, y] = (shade, shade, shade)
            else:
                base = Image.new("RGB", thumb_size, background)
            base.paste(frame, mask=frame.getchannel("A"))
            sheet.paste(base, ((index % 3) * thumb_size[0], (index // 3) * thumb_size[1]))
        sheet.save(output_root / f"feed-contact-{background}.png", compress_level=9)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("assets/feed/v1/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("assets/generated/work/feed/v1"))
    parser.add_argument(
        "--preview-output",
        type=Path,
        default=Path("assets/generated/work/feed/qa"),
    )
    args = parser.parse_args()
    frames = build_feed_assets(args.manifest, args.output)
    write_contact_sheets(frames, args.preview_output)
    for frame in frames:
        print(f"{frame.sha256}  {frame.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

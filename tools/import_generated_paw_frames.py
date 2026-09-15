"""Import generated anatomy into fixed local replacement patches.

The approved body/head files are read-only. Generated patch pixels include the
newly exposed belly; the compositor replaces the old limb before displaying it.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import zlib
from collections import deque
from PIL import Image, ImageDraw, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from desktop_pet.assets import HEAD_TILT_BACKPLATE_SHA256, load_head_neck_compositor
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.paw_compositor import disjoint_paw_masks, load_rle_masks


def chroma_cutout(image):
    """Convert the requested solid magenta transport background into Alpha."""
    output = Image.new("RGBA", image.size)
    rows = []
    for red, green, blue in image.convert("RGB").getdata():
        coverage = max(0.0, min(1.0, (255 - min(red, blue) + green) / 255))
        if coverage < .05:
            rows.append((0, 0, 0, 0))
        else:
            color = tuple(max(0, min(255, round((value - (1 - coverage) * matte) / coverage)))
                          for value, matte in zip((red, green, blue), (255, 0, 255)))
            rows.append((*color, round(coverage * 255)))
    output.putdata(rows)
    # Keep only the cat's high-confidence component plus its immediate AA edge.
    # This rejects background color noise without painting or moving art pixels.
    width, height = output.size
    confidence = bytearray(1 if pixel[3] >= 192 else 0 for pixel in rows)
    largest = []
    for start in range(width * height):
        if not confidence[start]:
            continue
        component, pending = [], deque([start])
        confidence[start] = 0
        while pending:
            position = pending.popleft()
            component.append(position)
            x, y = position % width, position // width
            for neighbor in (position - 1 if x else -1, position + 1 if x + 1 < width else -1,
                             position - width if y else -1, position + width if y + 1 < height else -1):
                if neighbor >= 0 and confidence[neighbor]:
                    confidence[neighbor] = 0
                    pending.append(neighbor)
        if len(component) > len(largest):
            largest = component
    retained = bytearray(width * height)
    for position in largest:
        retained[position] = 255
    edge = Image.frombytes("L", output.size, bytes(retained)).filter(ImageFilter.MaxFilter(5))
    output.putdata([pixel if keep else (0, 0, 0, 0) for pixel, keep in zip(rows, edge.getdata())])
    return output


def import_sheet(manifest_path: Path, output: Path, preview: Path):
    manifest = json.loads(manifest_path.read_text())
    base = load_head_neck_compositor().compose(0, 0, HeadPose(0, 0))
    original = base.crop((64, 0, 576, 768))
    default_masks = dict(zip(("left", "right"), disjoint_paw_masks(*load_rle_masks(ROOT / "assets/paws/v1/authoring.json"))))
    limb_regions = {}
    for side, points in {
        "left": [(261, 541), (319, 545), (310, 625), (283, 736), (205, 740), (214, 673), (234, 613)],
        "right": [(132, 573), (171, 571), (204, 624), (212, 687), (197, 734), (129, 733), (131, 691), (145, 629)],
    }.items():
        region = Image.new("L", (512, 768))
        ImageDraw.Draw(region).polygon(points, fill=255)
        limb_regions[side] = ImageChops.multiply(region, original.getchannel("A").point(lambda value: 255 if value else 0))
    coverage = {}
    for side, points in {
        "left": [(180, 445), (350, 445), (350, 620), (328, 748), (188, 748), (180, 600)],
        "right": [(118, 535), (220, 535), (230, 684), (223, 740), (80, 740), (80, 575)],
    }.items():
        mask = Image.new("L", (512, 768))
        ImageDraw.Draw(mask).polygon(points, fill=255)
        coverage[side] = mask
    payload = {"version": 2, "encoding": "generated-local-replacement-zlib-base85-v1",
               "source_size": [512, 768], "source_sha256": HEAD_TILT_BACKPLATE_SHA256,
               "frame_map": [None, 0, 1, 1, 1, 0, 2, 2, 2, 2, 0, 0, 0, None, None],
               "sides": {}}
    preview.mkdir(parents=True, exist_ok=True)
    for row, side in enumerate(("left", "right")):
        boundary = coverage[side]
        feather = boundary.filter(ImageFilter.MinFilter(25)).filter(ImageFilter.GaussianBlur(5))
        box = boundary.getbbox()
        patches = []
        for column, (image_path, shift_x, shift_y) in enumerate(manifest[side]):
            image_path = Path(image_path)
            cell = Image.open(image_path).convert("RGB")
            cutout = chroma_cutout(cell).resize((640, 768), Image.Resampling.LANCZOS)
            full = Image.new("RGBA", (640, 768))
            full.alpha_composite(cutout, (shift_x, shift_y))
            registered = full.crop((64, 0, 576, 768))
            mask = feather.copy()
            other = default_masks["right" if side == "left" else "left"]
            other_region = limb_regions["right" if side == "left" else "left"]
            for y in range(box[1], box[3]):
                for x in range(box[0], box[2]):
                    other_pixel = other_region.getpixel((x, y)) or (other.getpixel((x, y)) and (
                        (side == "left" and x <= 208) or (side == "right" and x >= 216)
                    ))
                    moving_pixel = limb_regions[side].getpixel((x, y)) or ((default_masks[side].getpixel((x, y)) or other.getpixel((x, y))) and (
                        (side == "left" and x >= 209) or (side == "right" and x <= 215)
                    ))
                    if other_pixel:
                        mask.putpixel((x, y), 0)
                    elif moving_pixel:
                        mask.putpixel((x, y), 255)
                    elif boundary.getpixel((x, y)) and original.getpixel((x, y))[3] == 0 and registered.getpixel((x, y))[3] > 0:
                        mask.putpixel((x, y), 255)
            patch = registered.crop(box)
            raw = patch.tobytes()
            raw_mask = mask.crop(box).tobytes()
            patches.append({"rgba_sha256": hashlib.sha256(raw).hexdigest(),
                            "rgba_zlib_base85": base64.b85encode(zlib.compress(raw, 9)).decode("ascii"),
                            "mask_sha256": hashlib.sha256(raw_mask).hexdigest(),
                            "mask_zlib_base85": base64.b85encode(zlib.compress(raw_mask, 9)).decode("ascii"),
                            "generated_source_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                            "registration": [shift_x, shift_y]})
            displayed = base.copy()
            aligned = Image.new("RGBA", displayed.size)
            aligned.alpha_composite(registered, (64, 0))
            aligned_mask = Image.new("L", displayed.size)
            aligned_mask.paste(mask, (64, 0))
            displayed.paste(aligned, mask=aligned_mask)
            displayed.save(preview / f"{side}-{column}.png")
        payload["sides"][side] = {"bbox": list(box), "patches": patches}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sheet", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("preview", type=Path)
    args = parser.parse_args()
    import_sheet(args.sheet, args.output, args.preview)

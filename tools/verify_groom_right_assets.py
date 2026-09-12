"""Verify right grooming's actual pixels, neutral anchors and replacement gaps."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from PIL import Image, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from desktop_pet.assets import load_head_neck_compositor
from desktop_pet.groom_import import import_groom_frames, right_replacement_masks
from desktop_pet.head_neck_deformation import HeadPose

NEUTRAL_RGBA = "e02f052cb970d2ebed4946ad0f09038adbce4d41da3a730e09e56783054e5eb0"


def verify(frames: tuple[Image.Image, ...]) -> dict:
    neutral = load_head_neck_compositor().compose(0, 0, HeadPose(0, 0))
    assert hashlib.sha256(neutral.tobytes()).hexdigest() == NEUTRAL_RGBA
    assert len(frames) == 12
    assert all(frame.size == (640, 768) and frame.mode == "RGBA" for frame in frames)
    assert frames[0].tobytes() == frames[11].tobytes() == neutral.tobytes()
    hashes = [hashlib.sha256(frame.tobytes()).hexdigest() for frame in frames]
    assert len(set(hashes)) == 11, "every intermediate gesture must have actual new pixels"
    action, body, _ = right_replacement_masks()
    local = ImageChops.lighter(action, body).point(lambda a: 255 if a else 0)
    outside = ImageChops.invert(local)
    for index, frame in enumerate(frames):
        diff = ImageChops.difference(frame, neutral)
        assert all(ImageChops.multiply(channel, outside).getbbox() is None for channel in diff.split()), (
            f"frame {index}: head, ears, back or fixed body changed outside the reviewed local area"
        )
        if index in (0, 11):
            continue
        # The lifted right forepaw must leave empty space; a second generated
        # foot at this location caused the earlier three-foot defect.
        if index < 10:
            assert frame.getpixel((350, 720))[3] == 0, f"frame {index}: old/extra foot remains"
        assert frame.getpixel((154, 433)) == neutral.getpixel((154, 433)), "stray lower mouth/bell"
        alpha = frame.getchannel("A")
        assert alpha.getextrema() == (0, 255)
        band = alpha.point(lambda a: 255 if a <= 16 else 0).filter(ImageFilter.MaxFilter(25))
        for y in range(560, 768):
            for x in range(230, 425):
                if not local.getpixel((x, y)) or not band.getpixel((x, y)):
                    continue
                r, g, b, a = frame.getpixel((x, y))
                assert not (a and r > g + 8 and b > g + 8), f"frame {index}: magenta edge at {(x, y)}"
    return {"frames": 12, "distinct_rgba": 11, "canvas": [640, 768],
            "neutral_rgba_sha256": NEUTRAL_RGBA, "fixed_pixels_outside_local_region": True,
            "extra_foot_and_bell_absent": True, "new_lower_edges_without_magenta": True,
            "frame_rgba_sha256": hashes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=Path)
    args = parser.parse_args()
    if args.frames:
        frames = tuple(Image.open(args.frames / f"{i:02}.png").convert("RGBA") for i in range(12))
        result = verify(frames)
    else:
        with tempfile.TemporaryDirectory(prefix="groom-right-verify-") as temporary:
            result = verify(import_groom_frames(ROOT / "assets/groom/v2.1/manifest-right.json", Path(temporary)))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

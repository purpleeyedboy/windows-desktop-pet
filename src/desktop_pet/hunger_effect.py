"""Program-drawn mouth interior, tongue and tear layers over approved frames."""
from __future__ import annotations
from collections.abc import Sequence
from PIL import Image, ImageDraw, ImageFilter
from .hunger_animation import HungerAnimationFrame, HungerVisual

EyeBox = tuple[int, int, int, int]


def _mouth_layer(size: tuple[int, int], center: tuple[int, int], width: int,
                 height: int) -> Image.Image:
    """Build a feathered, shaded mouth cavity and tongue rather than a flat glyph."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    left, top = center[0] - width // 2, center[1] - height // 3
    right, bottom = center[0] + width // 2, center[1] + height
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((left, top, right, bottom), fill=245)
    mask = mask.filter(ImageFilter.GaussianBlur(max(0.6, width / 35)))
    cavity = Image.new("RGBA", size, (0, 0, 0, 0))
    pixels = cavity.load()
    for y in range(max(0, top), min(size[1], bottom + 1)):
        depth = (y - top) / max(1, bottom - top)
        color = (
            round(55 - 23 * depth),
            round(25 - 12 * depth),
            round(25 - 10 * depth),
            255,
        )
        for x in range(max(0, left), min(size[0], right + 1)):
            pixels[x, y] = color
    cavity.putalpha(mask)
    layer.alpha_composite(cavity)

    tongue_mask = Image.new("L", size, 0)
    tongue_top = top + (bottom - top) * 3 // 5
    ImageDraw.Draw(tongue_mask).ellipse(
        (center[0] - width // 3, tongue_top,
         center[0] + width // 3, bottom + 1),
        fill=235,
    )
    tongue_mask = tongue_mask.filter(ImageFilter.GaussianBlur(max(0.5, width / 45)))
    tongue = Image.new("RGBA", size, (187, 76, 91, 0))
    tongue.putalpha(tongue_mask)
    layer.alpha_composite(tongue)
    highlight = ImageDraw.Draw(layer, "RGBA")
    highlight.arc(
        (center[0] - width // 4, tongue_top,
         center[0] + width // 4, bottom),
        205,
        335,
        fill=(235, 139, 145, 150),
        width=max(1, width // 16),
    )
    return layer

def compose_hunger_effect(source: Image.Image, frame: HungerAnimationFrame,
                          eye_boxes: Sequence[EyeBox]) -> Image.Image:
    """Compose independent local layers; approved source bytes remain untouched."""
    base = source.convert("RGBA")
    if frame.visual is HungerVisual.SUSPENDED or len(eye_boxes) < 2:
        return base.copy()
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    boxes = tuple(eye_boxes)[:2]
    eye_centers = [((l + r) // 2, (t + b) // 2) for l, t, r, b in boxes]
    eye_distance = max(12, abs(eye_centers[1][0] - eye_centers[0][0]))
    face_x = sum(p[0] for p in eye_centers) // 2
    eye_y = sum(p[1] for p in eye_centers) // 2
    mouth_y = eye_y + eye_distance * 7 // 10
    openness = max(0.0, min(1.0, frame.mouth_open))
    if openness > 0:
        mouth_w = max(7, eye_distance * 18 // 100)
        mouth_h = max(2, round(eye_distance * .38 * openness))
        # The cavity uses feathered Alpha, vertical depth shading and a
        # separately shaded tongue. It is regenerated from current-pose
        # anchors, rather than pasted as a fixed circle or stored bitmap.
        overlay.alpha_composite(
            _mouth_layer(base.size, (face_x, mouth_y), mouth_w, mouth_h)
        )
    if frame.tears_visible:
        fall = round((base.height * .025) * max(.2, frame.tear_intensity))
        tear_w = max(2, base.width // 100)
        tear_h = max(8, base.height // 25)
        for left, _top, right, bottom in boxes:
            center = (left + right) // 2
            top = bottom + max(1, base.height // 250) + (frame.phase_millis // 50 % max(1, fall))
            draw.polygon(((center, top), (center-tear_w, top+tear_h*2//3),
                          (center, top+tear_h), (center+tear_w, top+tear_h*2//3)),
                         fill=(105, 190, 245, round(230*frame.tear_intensity)))
            draw.ellipse((center-tear_w, top+tear_h//2, center+tear_w, top+tear_h),
                         fill=(105, 190, 245, round(230*frame.tear_intensity)))
    return Image.alpha_composite(base, overlay)

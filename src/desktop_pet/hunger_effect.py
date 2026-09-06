"""Program-drawn mouth interior, tongue and tear layers over approved frames."""
from __future__ import annotations
from collections.abc import Sequence
from PIL import Image, ImageDraw
from .hunger_animation import HungerAnimationFrame, HungerVisual

EyeBox = tuple[int, int, int, int]

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
        mouth_w = max(8, eye_distance * 28 // 100)
        mouth_h = max(2, round(eye_distance * .30 * openness))
        # Interior covers the original closed-mouth pixels; tongue is a separate
        # lower local layer, both recomputed from the current head pose frame.
        draw.ellipse((face_x-mouth_w//2, mouth_y-mouth_h//3,
                      face_x+mouth_w//2, mouth_y+mouth_h),
                     fill=(45, 20, 19, 245))
        tongue_h = max(1, mouth_h // 3)
        draw.ellipse((face_x-mouth_w//3, mouth_y+mouth_h-tongue_h,
                      face_x+mouth_w//3, mouth_y+mouth_h+1),
                     fill=(196, 91, 103, 245))
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

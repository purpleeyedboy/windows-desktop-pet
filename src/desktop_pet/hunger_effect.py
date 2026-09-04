"""Deterministic, program-drawn hunger effects over approved runtime frames."""

from __future__ import annotations

import math
from collections.abc import Sequence

from PIL import Image, ImageDraw

from .hunger_animation import HungerAnimationFrame, HungerVisual


EyeBox = tuple[int, int, int, int]


def _scaled(value: int, numerator: int, denominator: int) -> int:
    return value * numerator // denominator


def compose_hunger_effect(
    source: Image.Image,
    frame: HungerAnimationFrame,
    eye_boxes: Sequence[EyeBox],
) -> Image.Image:
    """Return a composed copy; never mutate or resample approved source pixels."""
    base = source.convert("RGBA")
    if frame.visual is HungerVisual.SUSPENDED:
        return base.copy()

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    width, height = base.size
    angle = 2.0 * math.pi * frame.phase_millis / max(1, frame.cycle_millis)
    pulse = (1.0 + math.sin(angle)) / 2.0

    # Small breathing/pang marks stay close to the body and do not alter the
    # underlying approved image or its deformation topology.
    center_x = width // 2
    belly_y = _scaled(height, 7, 10)
    spread = _scaled(width, 7 + round(3 * pulse), 100)
    rise = _scaled(height, 2 + round(2 * pulse), 100)
    alpha = {
        HungerVisual.NORMAL_HUNGRY: 105,
        HungerVisual.SEVERE_HUNGRY: 165,
        HungerVisual.EXTREME_HUNGRY: 215,
    }[frame.visual]
    color = (89, 154, 210, alpha)
    stroke = max(1, width // 170)
    for direction in (-1, 1):
        x = center_x + direction * spread
        box = (x - spread // 2, belly_y - rise, x + spread // 2, belly_y + rise)
        draw.arc(box, 195 if direction < 0 else 345, 345 if direction < 0 else 495, fill=color, width=stroke)

    if frame.tears_visible:
        fall = round((_scaled(height, 5, 100)) * pulse)
        tear_width = max(3, _scaled(width, 2, 100))
        tear_height = max(7, _scaled(height, 4, 100))
        for left, _top, right, bottom in tuple(eye_boxes)[:2]:
            center = (left + right) // 2
            top = bottom + max(1, height // 200) + fall
            points = (
                (center, top),
                (center - tear_width, top + tear_height * 2 // 3),
                (center, top + tear_height),
                (center + tear_width, top + tear_height * 2 // 3),
            )
            draw.polygon(points, fill=(105, 190, 245, 220))
            draw.ellipse(
                (center - tear_width, top + tear_height // 2,
                 center + tear_width, top + tear_height),
                fill=(105, 190, 245, 220),
            )
    return Image.alpha_composite(base, overlay)

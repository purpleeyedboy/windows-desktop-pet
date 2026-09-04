"""Deterministic programmatic RGBA overlay for visible hand licking."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

from .idle_lick import LickPose


_REFERENCE_SIZE = (512, 768)
_FUR = (205, 167, 112, 255)
_FUR_LIGHT = (239, 222, 188, 255)
_FUR_SHADOW = (139, 101, 62, 220)
_TONGUE = (229, 105, 123, 245)
_TONGUE_SHADOW = (164, 61, 82, 230)


def compose_lick(frame: Image.Image, pose: LickPose) -> Image.Image:
    """Composite a raised paw and tongue without changing the source frame.

    Neutral returns the literal source object so established center-frame and
    Alpha identity contracts remain untouched.  Active poses are rendered at
    double resolution and downsampled for deterministic anti-aliased edges.
    """

    if not isinstance(frame, Image.Image) or frame.mode != "RGBA":
        raise TypeError("lick compositor requires an RGBA Pillow image")
    if not isinstance(pose, LickPose):
        raise TypeError("lick pose must be a LickPose")
    if pose == LickPose():
        return frame
    if pose.side not in ("left", "right") or pose.phase == "neutral":
        raise ValueError("active lick pose requires a side and phase")
    arm = _unit(pose.arm, "arm")
    tongue = _unit(pose.tongue, "tongue")
    if arm == 0.0 and tongue == 0.0:
        return frame

    scale = frame.height / _REFERENCE_SIZE[1]
    padding_x = (frame.width - _REFERENCE_SIZE[0] * scale) / 2.0
    supersample = 2
    overlay = Image.new(
        "RGBA", (frame.width * supersample, frame.height * supersample), (0, 0, 0, 0)
    )
    draw = ImageDraw.Draw(overlay)

    def point(x: float, y: float) -> tuple[int, int]:
        return (
            round((padding_x + x * scale) * supersample),
            round(y * scale * supersample),
        )

    side_sign = -1.0 if pose.side == "left" else 1.0
    shoulder_x = 172.0 if pose.side == "left" else 250.0
    paw_rest_x = 165.0 if pose.side == "left" else 250.0
    paw_target_x = 91.0 if pose.side == "left" else 139.0
    paw_x = paw_rest_x + (paw_target_x - paw_rest_x) * arm
    paw_y = 632.0 + (450.0 - 632.0) * arm
    if pose.phase == "lick":
        paw_y -= 5.0
    elif pose.phase == "retract":
        paw_y += 7.0

    width = max(2, round(34 * scale * supersample))
    shadow_width = width + max(2, round(5 * scale * supersample))
    shoulder = point(shoulder_x, 570.0)
    paw = point(paw_x, paw_y)
    draw.line((shoulder, paw), fill=_FUR_SHADOW, width=shadow_width)
    draw.line((shoulder, paw), fill=_FUR, width=width)
    radius_x = 24.0
    radius_y = 19.0
    paw_box = (
        *point(paw_x - radius_x, paw_y - radius_y),
        *point(paw_x + radius_x, paw_y + radius_y),
    )
    draw.ellipse(paw_box, fill=_FUR, outline=_FUR_LIGHT, width=max(1, round(3 * scale * supersample)))
    for claw_offset in (-9.0, 0.0, 9.0):
        start = point(paw_x + claw_offset, paw_y - 2.0)
        end = point(paw_x + claw_offset + side_sign * 2.0, paw_y + 8.0)
        draw.line((start, end), fill=_FUR_SHADOW, width=max(1, round(scale * supersample)))

    if tongue > 0.0:
        mouth_x = 109.0
        mouth_y = 397.0
        tongue_length = 35.0 * tongue
        tongue_width = 11.0 + 5.0 * tongue
        tongue_end = point(
            mouth_x + side_sign * tongue_length * 0.45,
            mouth_y + tongue_length,
        )
        draw.line(
            (point(mouth_x, mouth_y), tongue_end),
            fill=_TONGUE_SHADOW,
            width=max(2, round((tongue_width + 3) * scale * supersample)),
        )
        draw.line(
            (point(mouth_x, mouth_y), tongue_end),
            fill=_TONGUE,
            width=max(2, round(tongue_width * scale * supersample)),
        )
        radius = max(2, round(tongue_width * scale * supersample / 2))
        draw.ellipse(
            (tongue_end[0] - radius, tongue_end[1] - radius,
             tongue_end[0] + radius, tongue_end[1] + radius),
            fill=_TONGUE,
        )

    overlay = overlay.resize(frame.size, Image.Resampling.LANCZOS)
    return Image.alpha_composite(frame, overlay)


def _unit(value: object, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"lick {name} must be finite") from error
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"lick {name} must be within 0..1")
    return result

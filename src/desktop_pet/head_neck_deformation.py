"""Continuous Pillow-only inverse deformation for the cat head and neck."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Protocol

from PIL import Image, ImageChops, ImageMath


_CANVAS_SIZE = (512, 768)
_HEAD_ROI = (0, 160, 320, 432)
_ROI_BOTTOM = _HEAD_ROI[1] + _HEAD_ROI[3]
_DYNAMIC_MAX_X = 264
_DYNAMIC_MAX_Y = 555
_RESAMPLING_PADDING = 4
_RUNTIME_WARP_BOX = (
    _HEAD_ROI[0],
    _HEAD_ROI[1],
    _DYNAMIC_MAX_X + _RESAMPLING_PADDING,
    _DYNAMIC_MAX_Y + _RESAMPLING_PADDING,
)
_RUNTIME_WARP_SIZE = (
    _RUNTIME_WARP_BOX[2] - _RUNTIME_WARP_BOX[0],
    _RUNTIME_WARP_BOX[3] - _RUNTIME_WARP_BOX[1],
)
_X_VERTICES = (
    0,
    24,
    36,
    48,
    60,
    72,
    82,
    93,
    108,
    118,
    128,
    139,
    151,
    163,
    176,
    184,
    194,
    205,
    218,
    230,
    242,
    249,
    256,
    264,
    320,
)
_Y_VERTICES = (
    160,
    186,
    202,
    223,
    250,
    275,
    300,
    320,
    335,
    351,
    370,
    397,
    425,
    454,
    485,
    520,
    555,
    565,
    592,
)
_DYNAMIC_POLYGON = (
    (24.0, 202.0),
    (246.0, 202.0),
    (263.0, 370.0),
    (242.0, 455.0),
    (221.0, 564.0),
    (105.0, 564.0),
    (80.0, 470.0),
    (32.0, 430.0),
)
_EYE_LIMITS = (3.0, 2.0)
_BOUNDARY_RAMP = 20.0
_DEFORMATION_GAIN = 2.0
_AREA_RATIO_LIMITS = (0.60, 1.40)


class _BaseCompositor(Protocol):
    source_size: tuple[int, int]
    eye_midpoint: tuple[float, float]

    def compose(self, eye_x: float, eye_y: float) -> Image.Image: ...


def _finite_real(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


@dataclass(frozen=True)
class HeadPose:
    """One arbitrary continuous head target inside the normalized unit disk."""

    x: float
    y: float

    def __post_init__(self) -> None:
        x = _finite_real(self.x, "head x")
        y = _finite_real(self.y, "head y")
        if math.hypot(x, y) > 1.0:
            raise ValueError("head pose must be inside the unit disk")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _strictly_inside_polygon(x: float, y: float) -> bool:
    inside = False
    previous_x, previous_y = _DYNAMIC_POLYGON[-1]
    for current_x, current_y in _DYNAMIC_POLYGON:
        cross = (x - previous_x) * (current_y - previous_y) - (
            y - previous_y
        ) * (current_x - previous_x)
        if abs(cross) < 1e-12 and (
            min(previous_x, current_x) <= x <= max(previous_x, current_x)
            and min(previous_y, current_y) <= y <= max(previous_y, current_y)
        ):
            return False
        if (current_y > y) != (previous_y > y):
            intersection = (
                (previous_x - current_x)
                * (y - current_y)
                / (previous_y - current_y)
                + current_x
            )
            if x < intersection:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _segment_distance(
    x: float,
    y: float,
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    ax, ay = first
    bx, by = second
    dx = bx - ax
    dy = by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0.0:
        return math.hypot(x - ax, y - ay)
    fraction = min(
        1.0,
        max(0.0, ((x - ax) * dx + (y - ay) * dy) / length_squared),
    )
    nearest_x = ax + fraction * dx
    nearest_y = ay + fraction * dy
    return math.hypot(x - nearest_x, y - nearest_y)


def _support_weight(x: float, y: float) -> float:
    if (
        x >= _DYNAMIC_MAX_X
        or y >= _DYNAMIC_MAX_Y
        or not _strictly_inside_polygon(x, y)
    ):
        return 0.0
    distance = min(
        _segment_distance(x, y, first, second)
        for first, second in zip(
            _DYNAMIC_POLYGON,
            _DYNAMIC_POLYGON[1:] + _DYNAMIC_POLYGON[:1],
        )
    )
    polygon_ramp = _smoothstep(distance / _BOUNDARY_RAMP)
    if x <= 230.0:
        return polygon_ramp
    protected_body_ramp = _smoothstep((_DYNAMIC_MAX_X - x) / 34.0)
    return polygon_ramp * protected_body_ramp


def _gaussian(
    x: float,
    y: float,
    *,
    center_x: float,
    center_y: float,
    sigma_x: float,
    sigma_y: float,
) -> float:
    dx = (x - center_x) / sigma_x
    dy = (y - center_y) / sigma_y
    return math.exp(-0.5 * (dx * dx + dy * dy))


def _horizontal_amplitude(x: float, y: float) -> float:
    if y <= 250.0:
        base = 2.45
    elif y <= 425.0:
        base = 2.5
    elif y <= 454.0:
        base = 2.5 - 0.7 * (y - 425.0) / 29.0
    elif y <= 520.0:
        base = 1.8 - 0.6 * (y - 454.0) / 66.0
    else:
        base = 1.2 * (555.0 - y) / 35.0
    nose = 0.9 * _gaussian(
        x,
        y,
        center_x=118.0,
        center_y=397.0,
        sigma_x=35.0,
        sigma_y=45.0,
    )
    ear = 0.5 * (
        _gaussian(
            x,
            y,
            center_x=36.0,
            center_y=223.0,
            sigma_x=30.0,
            sigma_y=40.0,
        )
        + _gaussian(
            x,
            y,
            center_x=223.0,
            center_y=213.0,
            sigma_x=30.0,
            sigma_y=40.0,
        )
    )
    return base + nose + ear


def _vertical_amplitude(x: float, y: float) -> float:
    if y <= 250.0:
        base = 1.25
    elif y <= 425.0:
        base = 1.6
    elif y <= 520.0:
        base = 1.6 * (520.0 - y) / 95.0
    else:
        base = 0.0
    nose = 0.9 * _gaussian(
        x,
        y,
        center_x=118.0,
        center_y=397.0,
        sigma_x=32.0,
        sigma_y=36.0,
    )
    return base + nose


def _sampling_offset(x: float, y: float, pose: HeadPose) -> tuple[float, float]:
    support = _support_weight(x, y)
    if support == 0.0:
        return 0.0, 0.0
    return (
        -pose.x * support * _horizontal_amplitude(x, y) * _DEFORMATION_GAIN,
        -pose.y * support * _vertical_amplitude(x, y) * _DEFORMATION_GAIN,
    )


def _vertex_field() -> dict[tuple[int, int], tuple[float, float]]:
    field = {}
    for x in _X_VERTICES:
        for y in _Y_VERTICES:
            support = _support_weight(float(x), float(y))
            field[(x, y)] = (
                support * _horizontal_amplitude(float(x), float(y)) * _DEFORMATION_GAIN,
                support * _vertical_amplitude(float(x), float(y)) * _DEFORMATION_GAIN,
            )
    return field


_VERTEX_FIELD = _vertex_field()


def _source_vertex(x: int, y: int, pose: HeadPose) -> tuple[float, float]:
    horizontal, vertical = _VERTEX_FIELD[(x, y)]
    return (
        float(x) - pose.x * horizontal,
        float(y - _HEAD_ROI[1]) - pose.y * vertical,
    )


def _signed_area(points: tuple[tuple[float, float], ...]) -> float:
    return 0.5 * sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1])
    )


def _validate_quad(
    bbox: tuple[int, int, int, int],
    points: tuple[tuple[float, float], ...],
) -> None:
    if not all(math.isfinite(value) for point in points for value in point):
        raise ValueError("head mesh contains a non-finite source coordinate")
    width, height = _HEAD_ROI[2:]
    if not all(0.0 <= x <= width and 0.0 <= y <= height for x, y in points):
        raise ValueError("head mesh source coordinate is outside the ROI")
    crosses = []
    for index in range(4):
        first = points[index]
        second = points[(index + 1) % 4]
        third = points[(index + 2) % 4]
        crosses.append(
            (second[0] - first[0]) * (third[1] - second[1])
            - (second[1] - first[1]) * (third[0] - second[0])
        )
    if not all(value < 0.0 for value in crosses):
        raise ValueError("head mesh contains a non-convex or flipped quad")
    output_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    area_ratio = abs(_signed_area(points)) / output_area
    if not _AREA_RATIO_LIMITS[0] <= area_ratio <= _AREA_RATIO_LIMITS[1]:
        raise ValueError("head mesh source/output area ratio is outside limits")


def _dynamic_pixel_mask() -> Image.Image:
    width, height = _HEAD_ROI[2:]
    values = []
    for local_y in range(height):
        global_y = local_y + _HEAD_ROI[1]
        for x in range(width):
            dynamic = (
                x < _DYNAMIC_MAX_X
                and global_y < _DYNAMIC_MAX_Y
                and _strictly_inside_polygon(x + 0.5, global_y + 0.5)
            )
            values.append(255 if dynamic else 0)
    mask = Image.new("L", (width, height))
    mask.putdata(values)
    return mask


_DYNAMIC_PIXEL_MASK = _dynamic_pixel_mask()
_RUNTIME_PIXEL_MASK = _DYNAMIC_PIXEL_MASK.crop(
    (0, 0, _RUNTIME_WARP_SIZE[0], _RUNTIME_WARP_SIZE[1])
)


def _premultiply(image: Image.Image) -> Image.Image:
    red, green, blue, alpha = image.split()
    return Image.merge(
        "RGBA",
        (
            ImageChops.multiply(red, alpha),
            ImageChops.multiply(green, alpha),
            ImageChops.multiply(blue, alpha),
            alpha,
        ),
    )


def _unpremultiply(image: Image.Image) -> Image.Image:
    red, green, blue, alpha = image.split()
    channels = []
    for channel in (red, green, blue):
        channels.append(
            ImageMath.unsafe_eval(
                'convert(c * 255 / max(a, 1), "L")',
                c=channel,
                a=alpha,
            )
        )
    transparent = alpha.point(lambda value: 255 if value == 0 else 0)
    for channel in channels:
        channel.paste(0, mask=transparent)
    return Image.merge("RGBA", (*channels, alpha))


def _normalize_near_opaque_alpha(image: Image.Image) -> Image.Image:
    """Collapse interpolation-only near-opaque values without changing RGB."""

    normalized = image.copy()
    normalized.putalpha(
        image.getchannel("A").point(
            lambda value: 255 if value >= 252 else value
        )
    )
    return normalized


class ContinuousHeadNeckCompositor:
    """Apply a continuous non-rigid inverse mesh after accepted eye motion."""

    deformation_gain = _DEFORMATION_GAIN

    def __init__(self, base_compositor: _BaseCompositor) -> None:
        try:
            source_size = tuple(base_compositor.source_size)
            midpoint = tuple(base_compositor.eye_midpoint)
            compose = base_compositor.compose
        except (AttributeError, TypeError) as error:
            raise TypeError("base compositor does not expose the required interface") from error
        if source_size != _CANVAS_SIZE:
            raise ValueError("base compositor source size must be 512x768")
        if len(midpoint) != 2:
            raise ValueError("base compositor eye midpoint must contain two values")
        self.eye_midpoint = (
            _finite_real(midpoint[0], "eye midpoint x"),
            _finite_real(midpoint[1], "eye midpoint y"),
        )
        self.source_size = _CANVAS_SIZE
        self.head_roi = _HEAD_ROI
        self._compose_base = compose
        compose_blink = getattr(base_compositor, "compose_blink", None)
        self._compose_blink = compose_blink if callable(compose_blink) else None

    def sampling_offset_at(
        self,
        point: tuple[float, float],
        pose: HeadPose,
    ) -> tuple[float, float]:
        if not isinstance(pose, HeadPose):
            raise TypeError("pose must be a HeadPose")
        if not isinstance(point, tuple) or len(point) != 2:
            raise TypeError("point must be an x/y tuple")
        x = _finite_real(point[0], "point x")
        y = _finite_real(point[1], "point y")
        if not 0.0 <= x <= 320.0 or not 160.0 <= y <= 592.0:
            raise ValueError("point is outside the head ROI")
        return _sampling_offset(x, y, pose)

    def mesh_for(
        self, pose: HeadPose
    ) -> tuple[tuple[tuple[int, int, int, int], tuple[float, ...]], ...]:
        if not isinstance(pose, HeadPose):
            raise TypeError("pose must be a HeadPose")
        mesh = []
        for row in range(len(_Y_VERTICES) - 1):
            global_y0 = _Y_VERTICES[row]
            global_y1 = _Y_VERTICES[row + 1]
            y0 = global_y0 - _HEAD_ROI[1]
            y1 = global_y1 - _HEAD_ROI[1]
            for column in range(len(_X_VERTICES) - 1):
                x0 = _X_VERTICES[column]
                x1 = _X_VERTICES[column + 1]
                bbox = (x0, y0, x1, y1)
                points = (
                    _source_vertex(x0, global_y0, pose),
                    _source_vertex(x0, global_y1, pose),
                    _source_vertex(x1, global_y1, pose),
                    _source_vertex(x1, global_y0, pose),
                )
                _validate_quad(bbox, points)
                mesh.append(
                    (bbox, tuple(value for point in points for value in point))
                )
        return tuple(mesh)

    @staticmethod
    def _runtime_mesh_for(
        pose: HeadPose,
    ) -> tuple[tuple[tuple[int, int, int, int], tuple[float, ...]], ...]:
        """Build the already-proven safe subset that can affect visible pixels."""
        mesh = []
        for row in range(len(_Y_VERTICES) - 1):
            global_y0 = _Y_VERTICES[row]
            global_y1 = _Y_VERTICES[row + 1]
            if global_y1 > _DYNAMIC_MAX_Y:
                break
            y0 = global_y0 - _HEAD_ROI[1]
            y1 = global_y1 - _HEAD_ROI[1]
            for column in range(len(_X_VERTICES) - 1):
                x0 = _X_VERTICES[column]
                x1 = _X_VERTICES[column + 1]
                if x1 > _DYNAMIC_MAX_X:
                    break
                points = (
                    _source_vertex(x0, global_y0, pose),
                    _source_vertex(x0, global_y1, pose),
                    _source_vertex(x1, global_y1, pose),
                    _source_vertex(x1, global_y0, pose),
                )
                mesh.append(
                    (
                        (x0, y0, x1, y1),
                        tuple(value for point in points for value in point),
                    )
                )
        return tuple(mesh)

    def compose(
        self,
        eye_x: float,
        eye_y: float,
        pose: HeadPose,
    ) -> Image.Image:
        return self._compose_with_source(
            eye_x,
            eye_y,
            pose,
            lambda dx, dy: self._compose_base(dx, dy),
        )

    def compose_head(
        self,
        eye_x: float,
        eye_y: float,
        pose: HeadPose,
    ) -> Image.Image:
        """Runtime-named form of the established eye-plus-head composition."""

        return self.compose(eye_x, eye_y, pose)

    def compose_head_blink(
        self,
        eye_x: float,
        eye_y: float,
        pose: HeadPose,
        closure: float,
    ) -> Image.Image:
        if self._compose_blink is None:
            if float(closure) != 0.0:
                raise RuntimeError("base compositor does not support blinking")
            return self.compose(eye_x, eye_y, pose)
        return self._compose_with_source(
            eye_x,
            eye_y,
            pose,
            lambda dx, dy: self._compose_blink(dx, dy, closure),
        )

    def _compose_with_source(
        self,
        eye_x: float,
        eye_y: float,
        pose: HeadPose,
        source_factory,
    ) -> Image.Image:
        dx = _finite_real(eye_x, "eye x")
        dy = _finite_real(eye_y, "eye y")
        if abs(dx) > _EYE_LIMITS[0] or abs(dy) > _EYE_LIMITS[1]:
            raise ValueError("eye offsets are outside the accepted envelope")
        if not isinstance(pose, HeadPose):
            raise TypeError("pose must be a HeadPose")
        source = source_factory(dx, dy)
        if not isinstance(source, Image.Image):
            raise TypeError("base compositor must return a Pillow image")
        if source.mode != "RGBA":
            raise ValueError("base compositor frame must use RGBA mode")
        if source.size != _CANVAS_SIZE:
            raise ValueError("base compositor frame must be 512x768")
        if pose.x == 0.0 and pose.y == 0.0:
            return source

        left, top, right, bottom = _RUNTIME_WARP_BOX
        roi = source.crop((left, top, right, bottom))
        warped = _premultiply(roi).transform(
            roi.size,
            Image.Transform.MESH,
            self._runtime_mesh_for(pose),
            Image.Resampling.BICUBIC,
        )
        straight = _normalize_near_opaque_alpha(_unpremultiply(warped))
        restored = Image.composite(straight, roi, _RUNTIME_PIXEL_MASK)
        result = source.copy()
        result.paste(restored, (left, top))
        return result


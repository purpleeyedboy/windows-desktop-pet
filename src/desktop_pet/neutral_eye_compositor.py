"""Cached Pillow compositor for the approved neutral-eye source layers."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final

from PIL import Image, ImageChops, ImageDraw, ImageFilter


CANONICAL_SHA256: Final = (
    "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"
)
CANVAS_SIZE: Final = (512, 768)
MOTION_LIMITS: Final = {"x": 3.0, "y": 2.0}
EYES: Final = ("left", "right")
OUTPUTS: Final = {
    "underlay.png": "RGBA",
    "eye-left.png": "RGBA",
    "eye-right.png": "RGBA",
    "eye-left-mask.png": "L",
    "eye-right-mask.png": "L",
}
OUTPUT_SHA256: Final = {
    "underlay.png": "d83230b60fe753b7344ae0b349d0c1409b47dc2002df66c5689765fcb0ca2495",
    "eye-left.png": "6140a3a4085d8514795ea2c17ee2173964553c604f0d096a120a508fa9f7308c",
    "eye-right.png": "9528b5f3c985b8366003fd77d413ff564b50ae547c705e5e6aee85fc86542906",
    "eye-left-mask.png": "27bee30342e67cab45d77a14ad7eebb0125f72d4b19039b5c3c1bf506623a81c",
    "eye-right-mask.png": "fba54f4eb10884d5a284ea6c16cd762d0786f61e09ddc5297e99d793c3a092e4",
}
MOTION_RESAMPLING: Final = (
    "premultiplied-alpha bilinear aperture-relative inverse warp"
)
WARP_FALLOFF: Final = "smoothstep normalized distance-to-boundary"


@dataclass(frozen=True)
class _EyeCache:
    crop_box: tuple[int, int, int, int]
    size: tuple[int, int]
    support: Image.Image
    source_rgb: tuple[tuple[int, int, int], ...]
    source_alpha: tuple[int, ...]
    premultiplied_rgb: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]
    output_alpha: tuple[int, ...]
    boundary: tuple[bool, ...]
    displacement_weights: tuple[float, ...]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_checked(data: bytes, filename: str, mode: str) -> Image.Image:
    try:
        with Image.open(BytesIO(data)) as opened:
            image = opened.copy()
    except OSError as error:
        raise ValueError(f"invalid {filename}") from error
    if image.mode != mode or image.size != CANVAS_SIZE:
        raise ValueError(f"invalid {filename}: expected {mode} {CANVAS_SIZE}")
    return image


def _binary_support(mask: Image.Image) -> Image.Image:
    return mask.point(lambda value: 255 if value else 0)


def _support_boundary(support: Image.Image) -> list[tuple[int, int]]:
    boundary = ImageChops.subtract(
        support, support.filter(ImageFilter.MinFilter(3))
    )
    bbox = boundary.getbbox()
    if bbox is None:
        return []
    return [
        (x, y)
        for y in range(bbox[1], bbox[3])
        for x in range(bbox[0], bbox[2])
        if boundary.getpixel((x, y))
    ]


def _validate_authoring(authoring: object) -> dict:
    if not isinstance(authoring, dict):
        raise ValueError("authoring metadata must be an object")
    canonical = authoring.get("canonical")
    if not isinstance(canonical, dict) or (
        canonical.get("mode") != "RGBA"
        or canonical.get("size") != list(CANVAS_SIZE)
        or canonical.get("sha256") != CANONICAL_SHA256
    ):
        raise ValueError("authoring canonical metadata is invalid")
    if authoring.get("motion_limits") != MOTION_LIMITS:
        raise ValueError("authoring motion limits are invalid")
    if authoring.get("motion_resampling") != MOTION_RESAMPLING:
        raise ValueError("authoring motion resampling is invalid")
    warp = authoring.get("warp")
    if not isinstance(warp, dict) or (
        warp.get("boundary_displacement") != 0.0
        or warp.get("falloff") != WARP_FALLOFF
        or warp.get("shared_field_shape") is not True
    ):
        raise ValueError("authoring warp metadata is invalid")
    eyes = authoring.get("eyes")
    if not isinstance(eyes, dict) or set(eyes) != set(EYES):
        raise ValueError("authoring eye metadata is invalid")
    outputs = authoring.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != set(OUTPUTS):
        raise ValueError("authoring outputs are invalid")
    for filename, expected_mode in OUTPUTS.items():
        recorded = outputs.get(filename)
        if not isinstance(recorded, dict) or (
            recorded.get("mode") != expected_mode
            or recorded.get("size") != list(CANVAS_SIZE)
        ):
            raise ValueError(f"authoring output metadata is invalid for {filename}")
        if recorded.get("sha256") != OUTPUT_SHA256[filename]:
            raise ValueError(f"approved output SHA mismatch for {filename}")
    return authoring


def _movement_anchor(eye_metadata: object, eye: str) -> tuple[float, float]:
    if not isinstance(eye_metadata, dict):
        raise ValueError(f"authoring metadata is invalid for {eye} eye")
    raw_anchor = eye_metadata.get("movement_anchor")
    if not isinstance(raw_anchor, list) or len(raw_anchor) != 2:
        raise ValueError(f"movement anchor is invalid for {eye} eye")
    try:
        anchor = (float(raw_anchor[0]), float(raw_anchor[1]))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"movement anchor is invalid for {eye} eye") from error
    if not all(math.isfinite(value) for value in anchor):
        raise ValueError(f"movement anchor must be finite for {eye} eye")
    if not (
        0.0 <= anchor[0] < CANVAS_SIZE[0]
        and 0.0 <= anchor[1] < CANVAS_SIZE[1]
    ):
        raise ValueError(f"movement anchor is outside the canvas for {eye} eye")
    return anchor


def _build_eye_cache(
    surface: Image.Image,
    aperture: Image.Image,
    anchor: tuple[float, float],
    eye: str,
) -> _EyeCache:
    support = _binary_support(aperture)
    bbox = support.getbbox()
    if bbox is None:
        raise ValueError(f"support is empty for {eye} eye")
    boundary_points = _support_boundary(support)
    if not boundary_points:
        raise ValueError(f"support boundary is empty for {eye} eye")
    boundary_distances = {
        (x, y): min(math.hypot(x - bx, y - by) for bx, by in boundary_points)
        for y in range(bbox[1], bbox[3])
        for x in range(bbox[0], bbox[2])
        if support.getpixel((x, y))
    }
    if not any(distance > 0.0 for distance in boundary_distances.values()):
        raise ValueError(f"support has no positive boundary distance for {eye} eye")
    anchor_point = (int(math.floor(anchor[0])), int(math.floor(anchor[1])))
    if support.getpixel(anchor_point) == 0:
        raise ValueError(f"movement anchor is outside support for {eye} eye")
    eroded_support = support.filter(ImageFilter.MinFilter(3))
    if eroded_support.getpixel(anchor_point) == 0:
        raise ValueError(f"movement anchor is not strictly inside support for {eye} eye")
    anchor_distance = min(
        math.hypot(anchor[0] - x, anchor[1] - y) for x, y in boundary_points
    )
    if anchor_distance <= 0.0:
        raise ValueError(f"movement anchor is not strictly inside support for {eye} eye")

    padding = 10
    crop_box = (
        max(0, bbox[0] - padding),
        max(0, bbox[1] - padding),
        min(CANVAS_SIZE[0], bbox[2] + padding),
        min(CANVAS_SIZE[1], bbox[3] + padding),
    )
    cropped = surface.crop(crop_box)
    cropped_alpha = cropped.getchannel("A")
    aperture_crop = aperture.crop(crop_box)
    if ImageChops.difference(cropped_alpha, aperture_crop).getbbox() is not None:
        raise ValueError(f"surface Alpha does not match aperture for {eye} eye")
    source_rgb_image = cropped.convert("RGB")
    premultiplied = tuple(
        tuple(ImageChops.multiply(channel, cropped_alpha).getdata())
        for channel in source_rgb_image.split()
    )
    boundary_set = set(boundary_points)
    boundary_flags: list[bool] = []
    weights: list[float] = []
    for local_y in range(cropped.height):
        for local_x in range(cropped.width):
            global_point = (local_x + crop_box[0], local_y + crop_box[1])
            pinned = global_point in boundary_set
            boundary_flags.append(pinned)
            if aperture_crop.getpixel((local_x, local_y)) == 0 or pinned:
                weights.append(0.0)
                continue
            distance = boundary_distances[global_point]
            normalized = min(1.0, distance / anchor_distance)
            weights.append(normalized * normalized * (3.0 - 2.0 * normalized))

    return _EyeCache(
        crop_box=crop_box,
        size=cropped.size,
        support=_binary_support(aperture_crop),
        source_rgb=tuple(source_rgb_image.getdata()),
        source_alpha=tuple(cropped_alpha.getdata()),
        premultiplied_rgb=premultiplied,  # type: ignore[arg-type]
        output_alpha=tuple(aperture_crop.getdata()),
        boundary=tuple(boundary_flags),
        displacement_weights=tuple(weights),
    )


class ValidatedNeutralEyeSnapshot:
    """One-read, fixed-hash snapshot shared by preview and composition."""

    def __init__(
        self,
        authoring: dict,
        images: dict[str, Image.Image],
        authoring_sha256: str,
    ) -> None:
        self._authoring = authoring
        self._images = images
        self.authoring_sha256 = authoring_sha256

    @classmethod
    def load(cls, asset_dir: Path) -> ValidatedNeutralEyeSnapshot:
        asset_dir = Path(asset_dir)
        authoring_path = asset_dir / "authoring.json"
        try:
            authoring_bytes = authoring_path.read_bytes()
            authoring = json.loads(authoring_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid authoring.json") from error
        authoring = _validate_authoring(authoring)

        images: dict[str, Image.Image] = {}
        for filename, expected_mode in OUTPUTS.items():
            try:
                data = (asset_dir / filename).read_bytes()
            except OSError as error:
                raise ValueError(f"invalid {filename}") from error
            if _sha256(data) != OUTPUT_SHA256[filename]:
                raise ValueError(f"approved output SHA mismatch for {filename}")
            images[filename] = _decode_checked(data, filename, expected_mode)
        return cls(authoring, images, _sha256(authoring_bytes))

    def authoring(self) -> dict:
        return deepcopy(self._authoring)

    def images(self) -> dict[str, Image.Image]:
        return {filename: image.copy() for filename, image in self._images.items()}

    def output_hashes(self) -> dict[str, str]:
        return dict(OUTPUT_SHA256)


class NeutralEyeCompositor:
    """Immutable construction-time caches with independent RGBA results."""

    def __init__(
        self,
        base_rgb: Image.Image,
        source_alpha: Image.Image,
        center: Image.Image,
        eye_caches: tuple[_EyeCache, ...],
        eye_midpoint: tuple[float, float],
    ) -> None:
        self.source_size = CANVAS_SIZE
        self.eye_midpoint = eye_midpoint
        interaction_padding = 12
        self.eye_interaction_boxes = tuple(
            (
                max(0, cache.crop_box[0] - interaction_padding),
                max(0, cache.crop_box[1] - interaction_padding),
                min(CANVAS_SIZE[0], cache.crop_box[2] + interaction_padding),
                min(CANVAS_SIZE[1], cache.crop_box[3] + interaction_padding),
            )
            for cache in eye_caches
        )
        self._base_rgb = base_rgb
        self._source_alpha = source_alpha
        self._center = center
        self._eye_caches = eye_caches

    @classmethod
    def load(cls, asset_dir: Path) -> NeutralEyeCompositor:
        return cls.from_snapshot(ValidatedNeutralEyeSnapshot.load(asset_dir))

    @classmethod
    def from_snapshot(
        cls, snapshot: ValidatedNeutralEyeSnapshot
    ) -> NeutralEyeCompositor:
        if not isinstance(snapshot, ValidatedNeutralEyeSnapshot):
            raise TypeError("snapshot must be a ValidatedNeutralEyeSnapshot")
        return cls._from_images(snapshot.authoring(), snapshot.images())

    @classmethod
    def _from_images(
        cls, authoring: dict, images: dict[str, Image.Image]
    ) -> NeutralEyeCompositor:
        authoring = _validate_authoring(authoring)
        if set(images) != set(OUTPUTS):
            raise ValueError("validated images are incomplete")
        for filename, expected_mode in OUTPUTS.items():
            image = images[filename]
            if image.mode != expected_mode or image.size != CANVAS_SIZE:
                raise ValueError(
                    f"invalid {filename}: expected {expected_mode} {CANVAS_SIZE}"
                )

        anchors = tuple(
            _movement_anchor(authoring["eyes"][eye], eye) for eye in EYES
        )
        caches = tuple(
            _build_eye_cache(
                images[f"eye-{eye}.png"],
                images[f"eye-{eye}-mask.png"],
                anchor,
                eye,
            )
            for eye, anchor in zip(EYES, anchors, strict=True)
        )
        underlay = images["underlay.png"]
        base_rgb = underlay.convert("RGB")
        source_alpha = underlay.getchannel("A")
        center_rgb = base_rgb.copy()
        for cache in caches:
            center_crop = Image.new("RGB", cache.size)
            center_crop.putdata(cache.source_rgb)
            center_rgb.paste(center_crop, cache.crop_box[:2], cache.support)
        center = center_rgb.convert("RGBA")
        center.putalpha(source_alpha)
        midpoint = (
            sum(anchor[0] for anchor in anchors) / len(anchors),
            sum(anchor[1] for anchor in anchors) / len(anchors),
        )
        return cls(base_rgb, source_alpha, center, caches, midpoint)

    def compose(self, eye_x: float, eye_y: float) -> Image.Image:
        return self.compose_blink(eye_x, eye_y, 0.0)

    def compose_blink(
        self,
        eye_x: float,
        eye_y: float,
        closure: float,
    ) -> Image.Image:
        try:
            dx = float(eye_x)
            dy = float(eye_y)
            amount = float(closure)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(
                "eye offsets must be finite and within motion limits; blink closure must be finite and within 0..1"
            ) from error
        if (
            not math.isfinite(dx)
            or not math.isfinite(dy)
            or not math.isfinite(amount)
            or abs(dx) > MOTION_LIMITS["x"]
            or abs(dy) > MOTION_LIMITS["y"]
            or not 0.0 <= amount <= 1.0
        ):
            raise ValueError(
                "eye offsets must be finite and within motion limits; blink closure must be finite and within 0..1"
            )
        if dx == 0.0 and dy == 0.0 and amount == 0.0:
            return self._center.copy()

        composed_rgb = self._base_rgb.copy()
        for cache in self._eye_caches:
            warped_crop = Image.new("RGB", cache.size)
            if dx == 0.0 and dy == 0.0:
                warped_crop.putdata(cache.source_rgb)
            else:
                warped_crop.putdata(self._warped_rgb(cache, dx, dy))
            composed_rgb.paste(warped_crop, cache.crop_box[:2], cache.support)
            if amount > 0.0:
                lid_rgb, lid_mask = self._eyelid_layer(cache, amount)
                composed_rgb.paste(lid_rgb, cache.crop_box[:2], lid_mask)

        composed = composed_rgb.convert("RGBA")
        composed.putalpha(self._source_alpha)
        if amount > 0.72:
            composed = self._draw_closed_eye_creases(composed, amount)
            composed.putalpha(self._source_alpha)
        return composed

    def _eyelid_layer(
        self,
        cache: _EyeCache,
        closure: float,
    ) -> tuple[Image.Image, Image.Image]:
        width, height = cache.size
        crop_left, crop_top = cache.crop_box[:2]
        support = self._expanded_lid_support(cache)
        lid_rgb = Image.new("RGB", cache.size)
        lid_mask = Image.new("L", cache.size)
        rgb_values: list[tuple[int, int, int]] = []
        alpha_values: list[int] = []
        column_bounds: list[tuple[int, int] | None] = []
        for x in range(width):
            supported = [
                y for y in range(height) if support.getpixel((x, y)) != 0
            ]
            column_bounds.append(
                (min(supported), max(supported)) if supported else None
            )

        for y in range(height):
            for x in range(width):
                bounds = column_bounds[x]
                support_alpha = support.getpixel((x, y))
                if bounds is None or support_alpha == 0:
                    rgb_values.append((0, 0, 0))
                    alpha_values.append(0)
                    continue
                top, bottom = bounds
                span = max(1.0, float(bottom - top))
                normalized_x = x / max(1.0, width - 1.0)
                sag = 1.35 * math.sin(math.pi * normalized_x)
                seam = top + span * 0.60 + sag
                upper_edge = top + (seam - top) * closure
                lower_edge = bottom - (bottom - seam) * closure
                upper_coverage = min(1.0, max(0.0, upper_edge - y + 0.5))
                lower_coverage = min(1.0, max(0.0, y - lower_edge + 0.5))
                coverage = max(upper_coverage, lower_coverage)
                if coverage == 0.0:
                    rgb_values.append((0, 0, 0))
                    alpha_values.append(0)
                    continue

                if y <= seam:
                    fraction = min(
                        1.0,
                        max(0.0, (seam - y) / max(1.0, seam - top)),
                    )
                    sample_y = crop_top + top - 2 - round(fraction * 7.0)
                else:
                    fraction = min(
                        1.0,
                        max(0.0, (y - seam) / max(1.0, bottom - seam)),
                    )
                    sample_y = crop_top + bottom + 2 + round(fraction * 5.0)
                sample_x = crop_left + x
                sample_x = min(CANVAS_SIZE[0] - 1, max(0, sample_x))
                sample_y = min(CANVAS_SIZE[1] - 1, max(0, sample_y))
                rgb_values.append(self._base_rgb.getpixel((sample_x, sample_y)))
                alpha_values.append(round(support_alpha * coverage))

        lid_rgb.putdata(rgb_values)
        lid_rgb = lid_rgb.filter(ImageFilter.GaussianBlur(0.7))
        lid_mask.putdata(alpha_values)
        return lid_rgb, lid_mask

    @staticmethod
    def _expanded_lid_support(cache: _EyeCache) -> Image.Image:
        bbox = cache.support.getbbox()
        support = Image.new("L", cache.size)
        if bbox is None:
            return support
        expansion_x = 7
        expansion_y = 5
        expanded = (
            max(0, bbox[0] - expansion_x),
            max(0, bbox[1] - expansion_y),
            min(cache.size[0] - 1, bbox[2] - 1 + expansion_x),
            min(cache.size[1] - 1, bbox[3] - 1 + expansion_y),
        )
        ImageDraw.Draw(support).ellipse(expanded, fill=255)
        return support.filter(ImageFilter.GaussianBlur(0.6))

    def _draw_closed_eye_creases(
        self,
        composed: Image.Image,
        closure: float,
    ) -> Image.Image:
        strength = min(1.0, max(0.0, (closure - 0.65) / 0.35))
        strength = strength * strength * (3.0 - 2.0 * strength)
        overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for cache in self._eye_caches:
            crop_left, crop_top = cache.crop_box[:2]
            points: list[tuple[int, int]] = []
            seam_support = self._expanded_lid_support(cache)
            for x in range(cache.size[0]):
                supported = [
                    y
                    for y in range(cache.size[1])
                    if seam_support.getpixel((x, y)) != 0
                ]
                if not supported:
                    continue
                top, bottom = min(supported), max(supported)
                span = max(1.0, float(bottom - top))
                normalized_x = x / max(1.0, cache.size[0] - 1.0)
                sag = 1.35 * math.sin(math.pi * normalized_x)
                seam = round(top + span * 0.60 + sag)
                points.append((crop_left + x, crop_top + seam))
            if len(points) < 2:
                continue
            middle_x, middle_y = points[len(points) // 2]
            sample_y = max(0, middle_y - 8)
            sample = self._base_rgb.getpixel((middle_x, sample_y))
            color = tuple(max(10, round(channel * 0.36)) for channel in sample)
            alpha = round(168.0 * strength)
            draw.line(points, fill=(*color, alpha), width=1, joint="curve")
        return Image.alpha_composite(composed, overlay)

    @staticmethod
    def _warped_rgb(
        cache: _EyeCache, dx: float, dy: float
    ) -> list[tuple[int, int, int]]:
        width, height = cache.size
        maximum_x = width - 1.0
        maximum_y = height - 1.0
        output: list[tuple[int, int, int]] = []
        for index, output_alpha in enumerate(cache.output_alpha):
            if output_alpha == 0:
                output.append((0, 0, 0))
                continue
            if cache.boundary[index]:
                output.append(cache.source_rgb[index])
                continue
            local_x = index % width
            local_y = index // width
            weight = cache.displacement_weights[index]
            source_x = min(max(local_x - dx * weight, 0.0), maximum_x)
            source_y = min(max(local_y - dy * weight, 0.0), maximum_y)
            x0 = int(math.floor(source_x))
            y0 = int(math.floor(source_y))
            x1 = min(x0 + 1, width - 1)
            y1 = min(y0 + 1, height - 1)
            tx = source_x - x0
            ty = source_y - y0
            one_minus_tx = 1.0 - tx
            one_minus_ty = 1.0 - ty
            top_left = y0 * width + x0
            top_right = y0 * width + x1
            bottom_left = y1 * width + x0
            bottom_right = y1 * width + x1

            def sample(values: tuple[int, ...]) -> float:
                top = (
                    values[top_left] * one_minus_tx
                    + values[top_right] * tx
                )
                bottom = (
                    values[bottom_left] * one_minus_tx
                    + values[bottom_right] * tx
                )
                return top * one_minus_ty + bottom * ty

            sampled_alpha = sample(cache.source_alpha)
            if sampled_alpha <= 0.0:
                output.append((0, 0, 0))
                continue
            output.append(
                tuple(
                    min(
                        255,
                        max(
                            0,
                            round(
                                sample(values) * 255.0 / sampled_alpha
                            ),
                        ),
                    )
                    for values in cache.premultiplied_rgb
                )
            )
        return output


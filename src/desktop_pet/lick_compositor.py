"""Asset-driven grooming composition; contains no substitute geometry art."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Mapping

from PIL import Image

from .idle_lick import LickPose


Point = tuple[float, float]
HeadAnchorMap = Callable[[Point], Point]


class GroomAssetsUnavailable(RuntimeError):
    """Raised instead of substituting geometric placeholder art."""


@dataclass(frozen=True)
class GroomSideLayers:
    """Validated original-texture layers supplied by the grooming asset pack."""

    paw: Image.Image
    paw_mask: Image.Image
    vacancy_fill: Image.Image
    mouth: Image.Image
    tongue: Image.Image
    paw_rest_anchor: Point
    paw_contact_anchor: Point
    mouth_anchor: Point


@dataclass(frozen=True)
class GroomAssetBundle:
    canvas_size: tuple[int, int]
    sides: Mapping[str, GroomSideLayers]

    def __post_init__(self) -> None:
        if set(self.sides) != {"left", "right"}:
            raise ValueError("groom assets require cat-left and cat-right layers")
        for side, layers in self.sides.items():
            for name in ("paw", "vacancy_fill", "mouth", "tongue"):
                image = getattr(layers, name)
                if image.mode != "RGBA" or image.size != self.canvas_size:
                    raise ValueError(f"{side} {name} must be canvas-sized RGBA")
            if layers.paw_mask.mode != "L" or layers.paw_mask.size != self.canvas_size:
                raise ValueError(f"{side} paw mask must be canvas-sized L")


def compose_lick(
    frame: Image.Image,
    pose: LickPose,
    assets: GroomAssetBundle,
    map_head_anchor: HeadAnchorMap,
) -> Image.Image:
    """Move an original paw layer and align real mouth/tongue local layers."""

    if pose == LickPose():
        return frame
    if frame.mode != "RGBA" or frame.size != assets.canvas_size:
        raise ValueError("groom frame does not match asset canvas")
    if pose.side not in assets.sides:
        raise ValueError("groom pose side is unavailable")
    layers = assets.sides[pose.side]
    arm = _unit(pose.arm)
    tongue = _unit(pose.tongue)
    result = Image.composite(layers.vacancy_fill, frame, layers.paw_mask)

    contact = map_head_anchor(layers.paw_contact_anchor)
    paw_x = layers.paw_rest_anchor[0] + (
        contact[0] - layers.paw_rest_anchor[0]
    ) * arm
    paw_y = layers.paw_rest_anchor[1] + (
        contact[1] - layers.paw_rest_anchor[1]
    ) * arm
    moved_paw = _translate(
        layers.paw,
        paw_x - layers.paw_rest_anchor[0],
        paw_y - layers.paw_rest_anchor[1],
    )
    result = Image.alpha_composite(result, moved_paw)

    mouth = _translate_to_anchor(
        layers.mouth,
        layers.mouth_anchor,
        map_head_anchor(layers.mouth_anchor),
    )
    result = Image.alpha_composite(result, mouth)
    if tongue > 0.0:
        tongue_target = (
            contact[0] + (map_head_anchor(layers.mouth_anchor)[0] - contact[0]) * (1.0 - tongue),
            contact[1] + (map_head_anchor(layers.mouth_anchor)[1] - contact[1]) * (1.0 - tongue),
        )
        tongue_layer = _translate_to_anchor(
            layers.tongue,
            layers.paw_contact_anchor,
            tongue_target,
        )
        result = Image.alpha_composite(result, tongue_layer)
    return result


def load_groom_assets(root: Path) -> GroomAssetBundle:
    """Load the future reviewed local-layer pack according to its manifest."""

    root = Path(root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise GroomAssetsUnavailable(f"missing grooming manifest: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    canvas = tuple(data["canvas_size"])
    sides = {}
    for side in ("left", "right"):
        entry = data["sides"][side]
        images = {}
        for name in ("paw", "vacancy_fill", "mouth", "tongue"):
            images[name] = Image.open(root / entry[name]).convert("RGBA")
        mask = Image.open(root / entry["paw_mask"]).convert("L")
        sides[side] = GroomSideLayers(
            images["paw"], mask, images["vacancy_fill"], images["mouth"],
            images["tongue"], tuple(entry["paw_rest_anchor"]),
            tuple(entry["paw_contact_anchor"]), tuple(entry["mouth_anchor"]),
        )
    return GroomAssetBundle(canvas, sides)


def _translate_to_anchor(
    image: Image.Image, source: Point, target: Point
) -> Image.Image:
    return _translate(image, target[0] - source[0], target[1] - source[1])


def _translate(image: Image.Image, dx: float, dy: float) -> Image.Image:
    return image.transform(
        image.size,
        Image.Transform.AFFINE,
        (1.0, 0.0, -dx, 0.0, 1.0, -dy),
        Image.Resampling.BICUBIC,
    )


def _unit(value: float) -> float:
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ValueError("groom channel must be within 0..1")
    return result

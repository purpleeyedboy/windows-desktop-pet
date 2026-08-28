from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fontTools.ttLib import TTFont
from PIL import ImageDraw, ImageFont

from .paths import asset_path


class MissingGlyphError(ValueError):
    pass


@dataclass(frozen=True)
class FontFace:
    key: str
    path: Path
    font: ImageFont.FreeTypeFont
    codepoints: frozenset[int]


@dataclass(frozen=True)
class FontRun:
    font_key: str
    text: str
    font: ImageFont.FreeTypeFont
    x_advance: float
    advance: float
    ink_bbox: tuple[int, int, int, int]


@dataclass(frozen=True)
class TextLayout:
    runs: tuple[FontRun, ...]
    total_advance: float
    ink_bbox: tuple[int, int, int, int]


def _cmap(path: Path) -> frozenset[int]:
    with TTFont(path, lazy=True, fontNumber=0) as source:
        return frozenset(
            codepoint
            for table in source["cmap"].tables
            if table.isUnicode()
            for codepoint in table.cmap
        )


def _face(
    key: str,
    path: Path,
    size: int,
    axes: list[float] | None = None,
) -> FontFace:
    font = ImageFont.truetype(path, size)
    if axes is not None:
        font.set_variation_by_axes(axes)
    return FontFace(key, path, font, _cmap(path))


class FontRunResolver:
    def __init__(self, faces: Iterable[FontFace]):
        self.faces = tuple(faces)
        if not self.faces:
            raise ValueError("font resolver needs at least one bundled face")

    @classmethod
    def for_chinese(cls, size: int) -> "FontRunResolver":
        path = asset_path("assets", "fonts", "ZCOOLKuaiLe-Regular.ttf")
        return cls((_face("zcool", path, size),))

    @classmethod
    def for_kaomoji(cls, size: int) -> "FontRunResolver":
        sans = asset_path("assets", "fonts", "NotoSans-Variable.ttf")
        math = asset_path("assets", "fonts", "NotoSansMath-Regular.ttf")
        return cls(
            (
                _face("noto_sans", sans, size, [400.0, 100.0]),
                _face("noto_math", math, size),
            )
        )

    def layout(self, text: str, context: str = "") -> TextLayout:
        selected: list[tuple[FontFace, str]] = []
        for character in text:
            face = next(
                (item for item in self.faces if ord(character) in item.codepoints),
                None,
            )
            if face is None:
                prefix = f"{context}: " if context else ""
                raise MissingGlyphError(
                    f"{prefix}missing bundled glyph U+{ord(character):04X} in {text!r}"
                )
            if selected and selected[-1][0].key == face.key:
                selected[-1] = (face, selected[-1][1] + character)
            else:
                selected.append((face, character))

        runs: list[FontRun] = []
        cursor = 0.0
        union: tuple[int, int, int, int] | None = None
        for face, run_text in selected:
            mask, offset = face.font.getmask2(run_text, anchor="ls")
            mask_bbox = mask.getbbox()
            if mask_bbox is None:
                positioned = (
                    int(round(cursor)),
                    0,
                    int(round(cursor)),
                    0,
                )
            else:
                positioned = (
                    int(round(cursor + offset[0] + mask_bbox[0])),
                    offset[1] + mask_bbox[1],
                    int(round(cursor + offset[0] + mask_bbox[2])),
                    offset[1] + mask_bbox[3],
                )
                union = (
                    positioned
                    if union is None
                    else (
                        min(union[0], positioned[0]),
                        min(union[1], positioned[1]),
                        max(union[2], positioned[2]),
                        max(union[3], positioned[3]),
                    )
                )
            advance = float(face.font.getlength(run_text))
            runs.append(
                FontRun(
                    face.key,
                    run_text,
                    face.font,
                    cursor,
                    advance,
                    positioned,
                )
            )
            cursor += advance
        return TextLayout(tuple(runs), cursor, union or (0, 0, 0, 0))


def draw_layout(
    draw: ImageDraw.ImageDraw,
    layout: TextLayout,
    safe_rect: tuple[int, int, int, int],
    fill: int | tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    left, top, right, bottom = safe_rect
    x0 = (left + right - layout.total_advance) / 2
    baseline = (top + bottom - layout.ink_bbox[1] - layout.ink_bbox[3]) / 2
    for run in layout.runs:
        draw.text(
            (x0 + run.x_advance, baseline),
            run.text,
            font=run.font,
            fill=fill,
            anchor="ls",
        )
    return (
        int(round(x0 + layout.ink_bbox[0])),
        int(round(baseline + layout.ink_bbox[1])),
        int(round(x0 + layout.ink_bbox[2])),
        int(round(baseline + layout.ink_bbox[3])),
    )

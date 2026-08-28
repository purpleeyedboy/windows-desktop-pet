"""Action-specific dialogue loading, validation, and random selection."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Mapping, Protocol, Sequence

from PIL import Image, ImageDraw

from desktop_pet.bubble_layout import (
    BUBBLE_BODY_SIZE,
    BUBBLE_FONT_SIZE,
    BUBBLE_TEXT_SAFE_RECT,
)
from desktop_pet.font_runs import FontRunResolver, TextLayout, draw_layout
from desktop_pet.paths import asset_path


ACTIONS = ("jump", "squash", "shake")
PHRASES_PER_ACTION = 200
CAT_FIRST_PERSON_MARKERS = ("我", "本喵", "本猫", "猫猫")
DIALOGUE_FONT_SIZE = BUBBLE_FONT_SIZE
MIN_PHRASE_WIDTH = 120
MAX_PHRASE_WIDTH = BUBBLE_TEXT_SAFE_RECT[2] - BUBBLE_TEXT_SAFE_RECT[0]
KAOMOJI_PER_ACTION = 20
CHINESE_PER_ACTION = 180
CHINESE_WIDTH_RANGE = (120, 230)
KAOMOJI_WIDTH_RANGE = (60, 230)
KAOMOJI_ALLOWED = frozenset("₍₎⟆()^._ -\\/▽◇oOx=<>;~u3@⌒")


@dataclass(frozen=True)
class WidthStats:
    minimum: float
    median: float
    maximum: float


@dataclass(frozen=True)
class DialogueRenderStats:
    chinese_count: int
    kaomoji_count: int
    chinese: WidthStats
    kaomoji: WidthStats


class _ChoiceRng(Protocol):
    def choice(self, values: Sequence[str]) -> str: ...


def is_kaomoji_phrase(text: str) -> bool:
    if not isinstance(text, str) or text != text.strip() or not 6 <= len(text) <= 10:
        return False
    if not set(text) <= KAOMOJI_ALLOWED:
        return False
    if any(unicodedata.category(ch).startswith("C") or unicodedata.combining(ch) for ch in text):
        return False
    if re.search(r"[A-Za-z]{2}", text):
        return False
    return (("(" in text and ")" in text) or ("₍" in text and "₎" in text)) and any(
        eye in text for eye in ("^", "x", "o", "O", "@", ">", "<", ";", "-", "~", "u", "_")
    )


def validate_phrase_pools(pools: Mapping[str, Sequence[str]]) -> None:
    """Raise ``ValueError`` when dialogue data violates the packaged contract."""
    actual_keys = set(pools)
    expected_keys = set(ACTIONS)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ValueError(f"dialogue keys must be exactly {list(ACTIONS)}; missing={missing}, extra={extra}")

    seen: dict[str, str] = {}
    visual_length_count = 0
    first_visual_outlier: tuple[str, str] | None = None

    for action in ACTIONS:
        phrases = pools[action]
        if isinstance(phrases, (str, bytes)) or not isinstance(phrases, Sequence):
            raise ValueError(f"action {action!r} phrases must be a sequence")
        if len(phrases) != PHRASES_PER_ACTION:
            raise ValueError(
                f"action {action!r} must contain exactly {PHRASES_PER_ACTION} phrases; "
                f"found {len(phrases)}"
            )

        kaomoji_count = 0
        chinese_count = 0
        for phrase in phrases:
            if not isinstance(phrase, str):
                raise ValueError(f"action {action!r} has non-string phrase {phrase!r}")
            if not phrase or phrase != phrase.strip():
                raise ValueError(f"action {action!r} has untrimmed or empty phrase {phrase!r}")
            if not 6 <= len(phrase) <= 10:
                raise ValueError(
                    f"action {action!r} phrase {phrase!r} has length {len(phrase)}; expected 6-10"
                )
            if is_kaomoji_phrase(phrase):
                kaomoji_count += 1
            elif not any(marker in phrase for marker in CAT_FIRST_PERSON_MARKERS):
                raise ValueError(
                    f"action {action!r} phrase {phrase!r} lacks an explicit cat first-person marker; "
                    f"expected one of {CAT_FIRST_PERSON_MARKERS}"
                )
            else:
                chinese_count += 1
            if phrase in seen:
                raise ValueError(
                    f"action {action!r} phrase {phrase!r} duplicates action {seen[phrase]!r}"
                )
            seen[phrase] = action
            if 7 <= len(phrase) <= 9:
                visual_length_count += 1
            elif first_visual_outlier is None:
                first_visual_outlier = (action, phrase)

        if kaomoji_count != KAOMOJI_PER_ACTION or chinese_count != CHINESE_PER_ACTION:
            raise ValueError(
                f"action {action!r} must contain exactly {CHINESE_PER_ACTION} Chinese and "
                f"{KAOMOJI_PER_ACTION} kaomoji phrases; found {chinese_count} Chinese and "
                f"{kaomoji_count} kaomoji"
            )

    required = (len(seen) * 9 + 9) // 10
    if visual_length_count < required:
        action, phrase = first_visual_outlier or ("unknown", "")
        raise ValueError(
            f"at least 90% of phrases must have length 7-9; found {visual_length_count}/{len(seen)}; "
            f"first outlier action {action!r} phrase {phrase!r}"
        )


def load_phrase_pools(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Load UTF-8 dialogue JSON, validate it, and return immutable phrase pools."""
    source = path or asset_path("assets", "dialogue", "phrases.json")
    with Path(source).open("r", encoding="utf-8") as stream:
        raw = json.load(stream)
    if not isinstance(raw, dict):
        raise ValueError(f"dialogue root in {source} must be an object")
    pools: dict[str, tuple[str, ...]] = {}
    for action, values in raw.items():
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise ValueError(f"action {action!r} phrases must be a sequence")
        pools[action] = tuple(values)
    validate_phrase_pools(pools)
    return pools


def _width_stats(widths: Sequence[float], label: str) -> WidthStats:
    if not widths:
        raise ValueError(f"render validation requires at least one {label} phrase")
    return WidthStats(min(widths), float(median(widths)), max(widths))


def _validate_layout(
    action: str,
    phrase: str,
    layout: TextLayout,
    width_range: tuple[int, int],
) -> float:
    if layout.ink_bbox == (0, 0, 0, 0):
        raise ValueError(f"action {action!r} phrase {phrase!r} rendered an empty ink bbox")
    minimum, maximum = width_range
    if not minimum <= layout.total_advance <= maximum:
        raise ValueError(
            f"action {action!r} phrase {phrase!r} has rendered width "
            f"{layout.total_advance:.1f}px; expected {minimum}-{maximum}px"
        )
    ink_height = layout.ink_bbox[3] - layout.ink_bbox[1]
    safe_height = BUBBLE_TEXT_SAFE_RECT[3] - BUBBLE_TEXT_SAFE_RECT[1]
    if ink_height > safe_height:
        raise ValueError(
            f"action {action!r} phrase {phrase!r} has ink height {ink_height}px; "
            f"expected at most {safe_height}px"
        )
    image = Image.new("L", BUBBLE_BODY_SIZE, 0)
    positioned_bbox = draw_layout(
        ImageDraw.Draw(image),
        layout,
        BUBBLE_TEXT_SAFE_RECT,
        255,
    )
    if image.getbbox() is None:
        raise ValueError(f"action {action!r} phrase {phrase!r} rendered an empty glyph mask")
    left, top, right, bottom = BUBBLE_TEXT_SAFE_RECT
    if not (
        left <= positioned_bbox[0]
        and top <= positioned_bbox[1]
        and positioned_bbox[2] <= right
        and positioned_bbox[3] <= bottom
    ):
        raise ValueError(
            f"action {action!r} phrase {phrase!r} has ink bbox {positioned_bbox}; "
            f"expected inside {BUBBLE_TEXT_SAFE_RECT}"
        )
    return layout.total_advance


def validate_phrase_rendering(
    pools: Mapping[str, Sequence[str]],
) -> DialogueRenderStats:
    """Validate bundled font runs, widths, and 48px safe-area ink bounds."""
    chinese_resolver = FontRunResolver.for_chinese(28)
    kaomoji_resolver = FontRunResolver.for_kaomoji(40)
    chinese_widths: list[float] = []
    kaomoji_widths: list[float] = []

    for action, phrases in pools.items():
        for phrase in phrases:
            kaomoji = is_kaomoji_phrase(phrase)
            resolver = kaomoji_resolver if kaomoji else chinese_resolver
            width_range = KAOMOJI_WIDTH_RANGE if kaomoji else CHINESE_WIDTH_RANGE
            layout = resolver.layout(phrase, context=f"action {action!r} phrase {phrase!r}")
            width = _validate_layout(action, phrase, layout, width_range)
            (kaomoji_widths if kaomoji else chinese_widths).append(width)

    return DialogueRenderStats(
        chinese_count=len(chinese_widths),
        kaomoji_count=len(kaomoji_widths),
        chinese=_width_stats(chinese_widths, "Chinese"),
        kaomoji=_width_stats(kaomoji_widths, "kaomoji"),
    )


class DialogueChooser:
    """Choose from one action pool while remembering its immediately prior phrase."""

    def __init__(self, pools: Mapping[str, Sequence[str]], rng: _ChoiceRng):
        self._pools = {action: tuple(values) for action, values in pools.items()}
        if any(not values for values in self._pools.values()):
            raise ValueError("dialogue pools must be non-empty")
        self._rng = rng
        self._last: dict[str, str] = {}

    def choose(self, action: str) -> str:
        pool = self._pools[action]
        last = self._last.get(action)
        choices = pool if last is None or len(pool) == 1 else tuple(phrase for phrase in pool if phrase != last)
        phrase = self._rng.choice(choices)
        self._last[action] = phrase
        return phrase

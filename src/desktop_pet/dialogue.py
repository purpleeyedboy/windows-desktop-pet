"""Action-specific dialogue loading, validation, and random selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from desktop_pet.paths import asset_path


ACTIONS = ("jump", "squash", "shake")
PHRASES_PER_ACTION = 200


class _ChoiceRng(Protocol):
    def choice(self, values: Sequence[str]) -> str: ...


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

        for phrase in phrases:
            if not isinstance(phrase, str):
                raise ValueError(f"action {action!r} has non-string phrase {phrase!r}")
            if not phrase or phrase != phrase.strip():
                raise ValueError(f"action {action!r} has untrimmed or empty phrase {phrase!r}")
            if not 6 <= len(phrase) <= 10:
                raise ValueError(
                    f"action {action!r} phrase {phrase!r} has length {len(phrase)}; expected 6-10"
                )
            if phrase in seen:
                raise ValueError(
                    f"action {action!r} phrase {phrase!r} duplicates action {seen[phrase]!r}"
                )
            seen[phrase] = action
            if 7 <= len(phrase) <= 9:
                visual_length_count += 1
            elif first_visual_outlier is None:
                first_visual_outlier = (action, phrase)

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
    pools = {action: tuple(values) for action, values in raw.items()}
    validate_phrase_pools(pools)
    return pools


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

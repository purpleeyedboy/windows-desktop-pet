"""Persistent hunger domain model.

This module is the sole owner of hunger state.  Values and elapsed decay use
integers so GUI frame cadence cannot introduce cumulative floating-point error.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import os
from pathlib import Path
import shutil
from typing import Callable


class HungerLevel(Enum):
    NORMAL = "normal"
    SEVERE = "severe"
    EXTREME = "extreme"


@dataclass(frozen=True)
class HungerConfig:
    max_units: int = 10_000
    safe_default_units: int = 8_000
    decay_units: int = 1
    decay_period_s: int = 60
    severe_below: int = 4_000
    extreme_below: int = 2_000
    hysteresis_units: int = 200
    max_utc_s: int = 253_402_300_799  # 9999-12-31T23:59:59Z
    max_reward_ids: int = 256

    def __post_init__(self) -> None:
        if not (0 < self.extreme_below < self.severe_below < self.max_units):
            raise ValueError("hunger thresholds must be strictly ordered")
        if self.decay_units <= 0 or self.decay_period_s <= 0:
            raise ValueError("decay must use positive integer units and period")
        if not (0 <= self.safe_default_units <= self.max_units):
            raise ValueError("safe default must be within hunger bounds")
        if self.hysteresis_units < 0 or self.max_reward_ids <= 0:
            raise ValueError("hysteresis and reward history limits are invalid")


class MutableUtcClock:
    """Deterministic UTC clock intended for tests and explicit debug tooling."""

    def __init__(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("clock datetime must be timezone-aware")
        self._value = value.astimezone(timezone.utc)

    def utc_seconds(self) -> int:
        return int(self._value.timestamp())

    def advance(self, seconds: int) -> None:
        self._value += timedelta(seconds=int(seconds))


def system_utc_seconds() -> int:
    return int(datetime.now(timezone.utc).timestamp())


class HungerSystem:
    def __init__(
        self,
        *,
        config: HungerConfig | None = None,
        value_units: int | None = None,
        anchor_utc_s: int = 0,
        remainder_unit_seconds: int = 0,
        reward_ids: tuple[str, ...] = (),
        level: HungerLevel | None = None,
    ) -> None:
        self.config = config or HungerConfig()
        self.value_units = self._clamp_value(
            self.config.safe_default_units if value_units is None else value_units
        )
        self.anchor_utc_s = self._clamp_time(anchor_utc_s)
        self.remainder_unit_seconds = max(
            0, min(int(remainder_unit_seconds), self.config.decay_period_s - 1)
        )
        self._reward_ids = list(dict.fromkeys(str(item) for item in reward_ids))[
            -self.config.max_reward_ids :
        ]
        self.level = level or self._raw_level(self.value_units)

    def _clamp_value(self, value: int) -> int:
        return max(0, min(int(value), self.config.max_units))

    def _clamp_time(self, value: int) -> int:
        return max(0, min(int(value), self.config.max_utc_s))

    def _raw_level(self, value: int) -> HungerLevel:
        if value <= self.config.extreme_below:
            return HungerLevel.EXTREME
        if value <= self.config.severe_below:
            return HungerLevel.SEVERE
        return HungerLevel.NORMAL

    def _refresh_level(self) -> None:
        value = self.value_units
        if value <= self.config.extreme_below:
            self.level = HungerLevel.EXTREME
        elif self.level is HungerLevel.EXTREME and value < (
            self.config.extreme_below + self.config.hysteresis_units
        ):
            return
        elif value <= self.config.severe_below:
            self.level = HungerLevel.SEVERE
        elif self.level is HungerLevel.SEVERE and value < (
            self.config.severe_below + self.config.hysteresis_units
        ):
            return
        else:
            self.level = HungerLevel.NORMAL

    def set_value(self, value: int) -> None:
        self.value_units = self._clamp_value(value)
        self._refresh_level()

    def adjust(self, delta_units: int) -> None:
        self.set_value(self.value_units + int(delta_units))

    def advance_to(self, now_utc_s: int) -> None:
        now = self._clamp_time(now_utc_s)
        if now <= self.anchor_utc_s:
            # Re-anchor on rollback/future data: never grant hunger and do not
            # remain frozen until a bad future timestamp is reached.
            self.anchor_utc_s = now
            return
        elapsed = now - self.anchor_utc_s
        numerator = elapsed * self.config.decay_units + self.remainder_unit_seconds
        decrease, self.remainder_unit_seconds = divmod(
            numerator, self.config.decay_period_s
        )
        self.anchor_utc_s = now
        self.set_value(self.value_units - decrease)

    def apply_reward(self, event_id: str, units: int) -> bool:
        """Apply a narrow positive reward once; no file semantics are accepted."""
        event_id = str(event_id).strip()
        if not event_id or int(units) <= 0:
            raise ValueError("reward requires a non-empty id and positive units")
        if event_id in self._reward_ids:
            return False
        self.adjust(int(units))
        self._reward_ids.append(event_id)
        del self._reward_ids[: -self.config.max_reward_ids]
        return True

    def payload(self) -> dict[str, object]:
        return {
            "version": 1,
            "value_units": self.value_units,
            "anchor_utc_s": self.anchor_utc_s,
            "remainder_unit_seconds": self.remainder_unit_seconds,
            "level": self.level.value,
            "reward_ids": list(self._reward_ids),
        }


class HungerStore:
    def __init__(self, path: Path, config: HungerConfig | None = None) -> None:
        self.path = Path(path)
        self.config = config or HungerConfig()
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        self.temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")

    def _decode(self, path: Path) -> HungerSystem:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("unsupported hunger state schema")
        required = ("value_units", "anchor_utc_s", "remainder_unit_seconds")
        if any(type(payload.get(key)) is not int for key in required):
            raise ValueError("invalid hunger state fields")
        reward_ids = payload.get("reward_ids", [])
        if not isinstance(reward_ids, list) or not all(
            isinstance(item, str) for item in reward_ids
        ):
            raise ValueError("invalid reward history")
        level = HungerLevel(str(payload.get("level")))
        return HungerSystem(
            config=self.config,
            value_units=payload["value_units"],
            anchor_utc_s=payload["anchor_utc_s"],
            remainder_unit_seconds=payload["remainder_unit_seconds"],
            reward_ids=tuple(reward_ids),
            level=level,
        )

    def load(self, *, now_utc_s: int) -> HungerSystem:
        for candidate in (self.path, self.backup_path):
            try:
                state = self._decode(candidate)
                state.advance_to(now_utc_s)
                return state
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return HungerSystem(
            config=self.config,
            value_units=self.config.safe_default_units,
            anchor_utc_s=now_utc_s,
        )

    def save(self, state: HungerSystem) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(state.payload(), ensure_ascii=False, sort_keys=True)
        with self.temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if self.path.is_file():
            shutil.copyfile(self.path, self.backup_path)
        os.replace(self.temporary_path, self.path)
        try:
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

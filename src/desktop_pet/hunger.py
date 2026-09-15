"""V2.1 hunger service and unified atomic state persistence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from copy import deepcopy
from typing import Callable


class HungerLevel(Enum):
    NORMAL = "Normal"
    HUNGRY = "Hungry"
    SEVERE_HUNGRY = "SevereHungry"
    CRITICAL_HUNGRY = "CriticalHungry"
    # Source compatibility only; canonical state names above are persisted.
    SEVERE = "SevereHungry"
    EXTREME = "CriticalHungry"


@dataclass(frozen=True)
class HungerConfig:
    max_units: int = 100_000
    empty_after_seconds: int = 120 * 60
    hungry_below: int = 20_000
    severe_below: int = 10_000
    critical_below: int = 1_000
    schema_version: int = 2
    max_operation_ids: int = 32

    def __post_init__(self) -> None:
        if self.max_units != 100_000 or self.empty_after_seconds != 7_200:
            raise ValueError("V2.1 hunger scale and duration are fixed")
        if (self.critical_below, self.severe_below, self.hungry_below) != (1_000, 10_000, 20_000):
            raise ValueError("V2.1 hunger thresholds are fixed")


def system_utc_seconds() -> int:
    return int(datetime.now(timezone.utc).timestamp())


class OffsetUtcClock:
    """Real UTC plus a debug-only process-local offset; never changes Windows time."""
    def __init__(self, base_clock: Callable[[], int] = system_utc_seconds) -> None:
        self._base_clock = base_clock
        self._offset_seconds = 0

    def utc_seconds(self) -> int:
        return max(0, int(self._base_clock()) + self._offset_seconds)

    def advance(self, seconds: int) -> None:
        if int(seconds) < 0:
            raise ValueError("debug UTC offset cannot move backwards")
        self._offset_seconds += int(seconds)


# Old import name remains an alias, but unlike the rejected implementation it
# always advances with real UTC unless an injected base clock says otherwise.
MutableUtcClock = OffsetUtcClock


@dataclass(frozen=True)
class HungerSnapshot:
    units: int
    level: HungerLevel
    anchor_units: int
    anchor_utc: int
    first_launch_utc: int
    last_feed_utc: int | None
    recovery: str

    @property
    def display_percent(self) -> str:
        if 0 < self.units < 100:
            return "低于0.1%"
        return f"{self.units // 1_000}.{(self.units % 1_000) // 100}%"


class HungerStatePort:
    """PR5 StateStore adapter. commit_hunger must be temp-write/fsync/atomic-replace."""
    def load_hunger(self, now_utc: int) -> tuple[dict[str, object], str]:
        raise NotImplementedError

    def commit_hunger(self, state: dict[str, object]) -> None:
        raise NotImplementedError


def default_hunger_state(now_utc: int) -> dict[str, object]:
    now = max(0, int(now_utc))
    return {
        "StateVersion": 2,
        "HungerAnchorUnits": 100_000,
        "HungerAnchorUtc": now,
        # Numerator remainder for exact 100000 / 7200 decay.  Keeping this in
        # the same atomic record means repeated shutdown checkpoints cannot
        # make a full-to-empty interval longer through integer truncation.
        "HungerDecayRemainder": 0,
        "FirstLaunchUtc": now,
        "LastFeedUtc": None,
        "AppliedOperationIds": [],
    }


def migrate_v1_hunger(old: dict[str, object], now_utc: int) -> dict[str, object]:
    """Pure migration passed to PR5 StateStore; original payload is retained."""
    state = default_hunger_state(now_utc)
    state["HungerAnchorUnits"] = max(0, min(100_000, int(old["value_units"]) * 10))
    state["HungerAnchorUtc"] = max(0, int(old["anchor_utc_s"]))
    state["Migration"] = {"Version": 1, "Original": old.copy()}
    return state


class HungerService:
    """The sole hunger owner. Reads are derived; business mutations re-anchor atomically."""
    def __init__(self, store: HungerStatePort, utc_clock: Callable[[], int] = system_utc_seconds) -> None:
        self.config = HungerConfig()
        self.store = store
        self.utc_clock = utc_clock
        self._state, self.recovery = store.load_hunger(utc_clock())
        self._validate_state()
        if self.recovery in {"first-launch", "damaged-reset", "backup"}:
            self.store.commit_hunger(self._state)

    def _validate_state(self) -> None:
        units = int(self._state["HungerAnchorUnits"])
        anchor = int(self._state["HungerAnchorUtc"])
        first = int(self._state["FirstLaunchUtc"])
        self._state["HungerAnchorUnits"] = max(0, min(100_000, units))
        self._state["HungerAnchorUtc"] = max(0, anchor)
        self._state["FirstLaunchUtc"] = max(0, first)
        remainder = int(self._state.get("HungerDecayRemainder", 0))
        self._state["HungerDecayRemainder"] = max(
            0, min(self.config.empty_after_seconds - 1, remainder)
        )
        operations = self._state.get("AppliedOperationIds", [])
        if not isinstance(operations, list) or not all(isinstance(v, str) for v in operations):
            raise ValueError("AppliedOperationIds must be strings")

    @staticmethod
    def level_for(units: int) -> HungerLevel:
        value = max(0, min(100_000, int(units)))
        if value < 1_000:
            return HungerLevel.CRITICAL_HUNGRY
        if value < 10_000:
            return HungerLevel.SEVERE_HUNGRY
        if value < 20_000:
            return HungerLevel.HUNGRY
        return HungerLevel.NORMAL

    def snapshot(self, now_utc: int | None = None) -> HungerSnapshot:
        now = self.utc_clock() if now_utc is None else max(0, int(now_utc))
        anchor_utc = int(self._state["HungerAnchorUtc"])
        anchor_units = int(self._state["HungerAnchorUnits"])
        elapsed = max(0, now - anchor_utc)  # rollback consumes zero and never rewrites anchor
        numerator = (
            elapsed * self.config.max_units
            + int(self._state.get("HungerDecayRemainder", 0))
        )
        consumed = min(anchor_units, numerator // self.config.empty_after_seconds)
        units = max(0, anchor_units - consumed)
        return HungerSnapshot(
            units, self.level_for(units), anchor_units, anchor_utc,
            int(self._state["FirstLaunchUtc"]),
            None if self._state.get("LastFeedUtc") is None else int(self._state["LastFeedUtc"]),
            self.recovery,
        )

    def set_units(self, units: int, *, now_utc: int | None = None) -> HungerSnapshot:
        now = self.utc_clock() if now_utc is None else max(0, int(now_utc))
        staged = deepcopy(self._state)
        staged["HungerAnchorUnits"] = max(0, min(100_000, int(units)))
        staged["HungerAnchorUtc"] = now
        staged["HungerDecayRemainder"] = 0
        self.store.commit_hunger(staged)
        self._state = staged
        return self.snapshot(now)

    def apply_reward(self, operation_id: str, units: int, *, now_utc: int | None = None) -> tuple[HungerSnapshot, bool]:
        operation = str(operation_id).strip()
        if not operation or int(units) <= 0:
            raise ValueError("reward requires operation id and positive units")
        applied = list(self._state["AppliedOperationIds"])
        if operation in applied:
            return self.snapshot(now_utc), False
        now = self.utc_clock() if now_utc is None else max(0, int(now_utc))
        current = self.snapshot(now)
        staged = deepcopy(self._state)
        staged["HungerAnchorUnits"] = min(100_000, current.units + int(units))
        staged["HungerAnchorUtc"] = now
        staged["HungerDecayRemainder"] = 0
        staged["LastFeedUtc"] = now
        applied.append(operation)
        staged["AppliedOperationIds"] = applied[-self.config.max_operation_ids:]
        # Do not publish staged state in memory until the single atomic store
        # transaction succeeds.  A failed write can therefore be retried with
        # the same operation id without either losing or duplicating reward.
        self.store.commit_hunger(staged)
        self._state = staged
        return self.snapshot(now), True

    def close(self) -> None:
        now = self.utc_clock()
        current = self.snapshot(now)
        # A shutdown is a necessary business checkpoint; rollback never writes an older anchor.
        if now >= current.anchor_utc:
            elapsed = now - current.anchor_utc
            numerator = (
                elapsed * self.config.max_units
                + int(self._state.get("HungerDecayRemainder", 0))
            )
            staged = deepcopy(self._state)
            staged["HungerAnchorUnits"] = current.units
            staged["HungerAnchorUtc"] = now
            staged["HungerDecayRemainder"] = (
                0 if current.units == 0 else numerator % self.config.empty_after_seconds
            )
            self.store.commit_hunger(staged)
            self._state = staged

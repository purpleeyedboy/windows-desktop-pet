"""Narrow hunger adapters over the authoritative V2.1 foundation services."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .foundation.persistence import AtomicJsonStore
from .hunger import HungerStatePort, default_hunger_state


class SharedHungerStatePort(HungerStatePort):
    """Project hunger fields into the one shared state envelope/store.

    The caller-owned ``shared_state`` dictionary is updated in place only after
    ``AtomicJsonStore.save`` succeeds.  This also keeps the state later supplied
    to ``ApplicationServices.close`` current, avoiding an old startup snapshot
    overwriting a successful hunger transaction.
    """

    def __init__(
        self,
        store: AtomicJsonStore,
        shared_state: dict[str, Any],
    ) -> None:
        self.store = store
        self.shared_state = shared_state

    def load_hunger(self, now_utc: int) -> tuple[dict[str, object], str]:
        if "HungerAnchorUnits" not in self.shared_state:
            return default_hunger_state(now_utc), "first-launch"
        state = {
            "StateVersion": self.shared_state.get("HungerStateVersion", 2),
            "HungerAnchorUnits": self.shared_state["HungerAnchorUnits"],
            "HungerAnchorUtc": self.shared_state.get(
                "HungerAnchorUtc",
                self.shared_state.get("hunger_anchor_utc_seconds", now_utc),
            ),
            "HungerDecayRemainder": self.shared_state.get("HungerDecayRemainder", 0),
            "FirstLaunchUtc": self.shared_state.get("FirstLaunchUtc", now_utc),
            "LastFeedUtc": self.shared_state.get("LastFeedUtc"),
            "AppliedOperationIds": list(
                self.shared_state.get("recent_operation_ids", ())
            ),
        }
        return state, "ok"

    def commit_hunger(self, state: dict[str, object]) -> None:
        staged = deepcopy(self.shared_state)
        staged.update(
            {
                "HungerStateVersion": int(state["StateVersion"]),
                "HungerAnchorUnits": int(state["HungerAnchorUnits"]),
                "HungerAnchorUtc": int(state["HungerAnchorUtc"]),
                "hunger_anchor_utc_seconds": int(state["HungerAnchorUtc"]),
                "HungerDecayRemainder": int(state.get("HungerDecayRemainder", 0)),
                "FirstLaunchUtc": int(state["FirstLaunchUtc"]),
                "LastFeedUtc": state.get("LastFeedUtc"),
                "recent_operation_ids": list(state.get("AppliedOperationIds", ())),
            }
        )
        self.store.save(staged, durable=True)
        self.shared_state.clear()
        self.shared_state.update(staged)

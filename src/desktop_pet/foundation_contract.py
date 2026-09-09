"""Hunger adapters over the one injected V2.1 ApplicationServices instance."""
from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from .foundation.runtime import Activity, ActivityToken, Health
from .foundation.services import ApplicationServices
from .hunger import HungerLevel, HungerStatePort, default_hunger_state


class ActivityCoordinatorPort(Protocol):
    def publish_health(self, health: HungerLevel, units: int) -> int: ...
    def begin(self, activity: str, priority: str, animation_id: int,
              state_version: int) -> object | None: ...
    def is_current(self, activity: str, animation_id: int, state_version: int,
                   token: object) -> bool: ...
    def complete(self, activity: str, animation_id: int, state_version: int,
                 token: object) -> bool: ...
    def cancel(self, token: object, recovery_anchor: str) -> None: ...
    def input_allowed(self, operation: str, health: HungerLevel) -> bool: ...
    def status_text(self) -> str: ...


HEALTH = {
    HungerLevel.NORMAL: Health.NORMAL,
    HungerLevel.HUNGRY: Health.HUNGRY,
    HungerLevel.SEVERE_HUNGRY: Health.SEVERE,
    HungerLevel.CRITICAL_HUNGRY: Health.CRITICAL,
}
ACTIVITY = {
    "NormalHungerAnimation": Activity.NORMAL_HUNGER_ANIMATION,
    "SevereHungerAnimation": Activity.SEVERE_HUNGER_ANIMATION,
}


class SharedHungerState(HungerStatePort):
    """Adapt one hunger record; preserve the latest transaction/window fields."""

    def __init__(self, services: ApplicationServices) -> None:
        self.services = services

    def load_hunger(self, now_utc: int) -> tuple[dict[str, object], str]:
        current = self.services.state_snapshot()
        record = current.get("hunger")
        if record is None:
            return default_hunger_state(now_utc), "first-launch"
        if not isinstance(record, dict):
            raise ValueError("Persisted hunger record is invalid; refusing to replace it")
        recovery = "backup" if self.services.store.last_source == "backup" else "primary"
        return deepcopy(record), recovery

    def commit_hunger(self, record: dict[str, object]) -> None:
        candidate = deepcopy(record)
        def mutate(state: dict) -> None:
            state["hunger"] = candidate
            state["hunger_anchor_utc_seconds"] = int(candidate["HungerAnchorUtc"])
            recent = list(state.get("recent_operation_ids", []))
            for operation in candidate["AppliedOperationIds"]:
                if operation not in recent:
                    recent.append(operation)
            state["recent_operation_ids"] = recent[-32:]
        self.services.update_state(mutate, durable=True)


class SharedActivityAdapter:
    """Translate feature names into real coordinator tokens, never shadow state."""

    def __init__(self, services: ApplicationServices) -> None:
        self.services = services

    @property
    def coordinator(self):
        return self.services.runtime.coordinator

    def publish_health(self, health: HungerLevel, units: int) -> int:
        del units
        runtime = self.services.runtime
        if runtime.snapshot().health is not HEALTH[health]:
            runtime.set_health(HEALTH[health], source="hunger")
        runtime.drain()
        return runtime.snapshot().activity_version

    def begin(self, activity: str, priority: str, animation_id: int,
              state_version: int) -> ActivityToken | None:
        del priority, state_version
        return self.coordinator.request_activity(
            ACTIVITY[activity], animation_id=f"hunger:{animation_id}", timeout_seconds=4.0,
        )

    def is_current(self, activity: str, animation_id: int, state_version: int,
                   token: object) -> bool:
        del state_version
        return (
            isinstance(token, ActivityToken)
            and token == self.coordinator.current_token
            and token.activity is ACTIVITY[activity]
            and token.animation_id == f"hunger:{animation_id}"
        )

    def complete(self, activity: str, animation_id: int, state_version: int,
                 token: object) -> bool:
        if not self.is_current(activity, animation_id, state_version, token):
            return False
        return self.coordinator.complete(token, animation_id=token.animation_id)

    def cancel(self, token: object, recovery_anchor: str) -> None:
        del recovery_anchor
        if isinstance(token, ActivityToken):
            self.coordinator.cancel_and_recover(token)

    def input_allowed(self, operation: str, health: HungerLevel) -> bool:
        if operation in {"feed", "exit", "context-menu", "debug"}:
            return self.services.runtime.snapshot().activity is not Activity.SHUTTING_DOWN
        return health is not HungerLevel.CRITICAL_HUNGRY

    def status_text(self) -> str:
        state = self.services.runtime.snapshot()
        return f"{state.activity.value}; Version={state.activity_version}"

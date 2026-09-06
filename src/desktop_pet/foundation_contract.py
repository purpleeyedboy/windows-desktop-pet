"""Adapter boundary required from PR5; this feature never owns shared activity state."""
from __future__ import annotations
import importlib
from typing import Protocol
from .hunger import HungerLevel, HungerStatePort

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


class UtcClockPort(Protocol):
    def utc_seconds(self) -> int: ...


class FoundationServicesPort(Protocol):
    activity: ActivityCoordinatorPort
    utc_clock: UtcClockPort
    state_store: HungerStatePort
    foundation_commit: str

def load_foundation_services(root: object) -> FoundationServicesPort:
    """Load the one PR5 coordinator. Missing foundation is a visible startup error."""
    try:
        module = importlib.import_module("desktop_pet.foundation")
        factory = getattr(module, "create_foundation_services")
        services = factory(root)
    except (ImportError, AttributeError, TypeError) as error:
        raise RuntimeError(
            "V2.1-HUNGER requires PR5 foundation API: "
            "desktop_pet.foundation.create_foundation_services(root)"
        ) from error
    required = ("publish_health", "begin", "is_current", "complete", "cancel", "input_allowed", "status_text")
    for name in required:
        if not callable(getattr(services.activity, name, None)):
            raise RuntimeError(f"PR5 ActivityCoordinator is missing {name}()")
    if not callable(getattr(services.utc_clock, "utc_seconds", None)):
        raise RuntimeError("PR5 foundation UTC clock is missing utc_seconds()")
    if not callable(getattr(services.state_store, "load_hunger", None)) or not callable(
        getattr(services.state_store, "commit_hunger", None)
    ):
        raise RuntimeError("PR5 StateStore hunger adapter is missing")
    normalized_path = str(getattr(services.state_store, "path", "")).replace("\\", "/").lower()
    if not normalized_path.endswith("/desktoppet/state.json"):
        raise RuntimeError("PR5 StateStore must own %LOCALAPPDATA%/DesktopPet/state.json")
    if getattr(services.state_store, "atomic_commits", False) is not True:
        raise RuntimeError("PR5 StateStore must guarantee atomic commits")
    return services

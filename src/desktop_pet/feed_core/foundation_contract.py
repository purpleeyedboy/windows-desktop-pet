"""FEED adapter boundary for the shared V2.1 foundation owned by PR5.

This module intentionally defines protocols only.  It does not implement a second
state store, clock, event queue, activity state machine, or hunger service.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class FeedDragPreviewSnapshot:
    screen_x: int
    screen_y: int


@dataclass(frozen=True)
class FeedDropSnapshot:
    paths: tuple[str, ...]
    screen_x: int
    screen_y: int
    received_utc: str
    requested_effect: str = "copy"


class InteractionRegionService(Protocol):
    def hit_test_alpha_region(self, name: str, screen_x: int, screen_y: int) -> bool: ...


class InputRouter(Protocol):
    def submit(self, event_name: str, payload: object) -> bool: ...


class ActivityCoordinator(Protocol):
    def current_version(self) -> int: ...


class HungerService(Protocol):
    @property
    def value_units(self) -> int: ...


class StateStore(Protocol):
    def flush(self) -> None: ...


class ClockService(Protocol):
    def utc_iso(self) -> str: ...


class CapabilityService(Protocol):
    def supports(self, name: str) -> bool: ...


class FeedFoundationServices(Protocol):
    capabilities: CapabilityService
    interaction_regions: InteractionRegionService
    input_router: InputRouter
    activities: ActivityCoordinator
    hunger: HungerService
    state_store: StateStore
    clock: ClockService


REQUIRED_FEED_CAPABILITIES = (
    "feed.activity_pipeline.v2_1",
    "feed.ifileoperation_progress_sink.v1",
    "feed.hunger_fixed_point.v1",
    "feed.expectation_adapter.v1",
)


def foundation_feed_ready(services) -> bool:
    """Fail closed until PR5 exposes all trusted FEED handler capabilities."""
    if services is None:
        return False
    capabilities = getattr(services, "capabilities", None)
    input_router = getattr(services, "input_router", None)
    if capabilities is None or input_router is None:
        return False
    supports = getattr(capabilities, "supports", None)
    has_handler = getattr(input_router, "has_handler", None)
    if not callable(supports) or not callable(has_handler):
        return False
    return all(bool(supports(name)) for name in REQUIRED_FEED_CAPABILITIES) and bool(
        has_handler("FeedDrop", "V2.1-FEED-CORE")
    )

def load_foundation_services():
    """Load PR5's public API when that exact shared foundation is present."""
    try:
        from desktop_pet.foundation.api import get_services
    except ImportError:
        return None
    return get_services()


class FoundationFeedInputAdapter:
    """Copies OLE input into an immutable event and submits it to the one router."""

    def __init__(self, services: FeedFoundationServices):
        self.services = services
        self._preview_active = False

    def drag_enter(self, paths: Sequence[str], screen_x: int, screen_y: int) -> str:
        if len(paths) != 1:
            return "none"
        if not self.services.interaction_regions.hit_test_alpha_region(
            "head_feed", screen_x, screen_y
        ):
            return "none"
        if not self._preview_active:
            self._preview_active = bool(
                self.services.input_router.submit(
                    "FeedDragPreview",
                    FeedDragPreviewSnapshot(int(screen_x), int(screen_y)),
                )
            )
        return "copy" if self._preview_active else "none"

    def drag_leave(self) -> None:
        self._preview_active = False
        self.services.input_router.submit("FeedDragLeave", None)

    def submit_drop(self, paths: Sequence[str], screen_x: int, screen_y: int) -> bool:
        if self.drag_enter(paths, screen_x, screen_y) != "copy":
            return False
        snapshot = FeedDropSnapshot(
            paths=tuple(str(path) for path in paths),
            screen_x=int(screen_x),
            screen_y=int(screen_y),
            received_utc=self.services.clock.utc_iso(),
        )
        self._preview_active = False
        return bool(self.services.input_router.submit("FeedDrop", snapshot))

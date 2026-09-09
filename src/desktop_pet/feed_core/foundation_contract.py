"""OLE input snapshots routed through the injected shared runtime."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
from desktop_pet.foundation.platform import Point
from desktop_pet.foundation.runtime import RuntimeContext
from desktop_pet.foundation.services import ApplicationServices

@dataclass(frozen=True)
class FeedDropSnapshot:
    paths: tuple[str, ...]
    screen_x: int
    screen_y: int
    received_utc: str
    requested_effect: str = "copy"

def foundation_feed_ready(runtime) -> bool:
    """Check the installed feature, not nonexistent capabilities."""
    return bool(runtime is not None and runtime.ready and
                isinstance(runtime.services, ApplicationServices) and
                runtime.services.runtime is runtime.runtime)

def load_runtime_context_type():
    return RuntimeContext

class FoundationFeedInputAdapter:
    def __init__(self, feed):
        self.feed = feed
        self.services = feed.services
        self._preview_active = False

    def drag_enter(self, paths: Sequence[str], screen_x: int, screen_y: int) -> str:
        if len(paths) != 1 or not self.feed.accepting_input:
            self.drag_leave()
            return "none"
        hit = self.services.regions.hit_test(Point(int(screen_x), int(screen_y)), "click")
        if hit is None:
            self.drag_leave()
            return "none"
        if not self._preview_active:
            self.services.runtime.post("feed.preview", source="ole")
            self._preview_active = True
        return "copy" if hit.part == "head" else "none"

    def drag_leave(self) -> None:
        if self._preview_active:
            self.services.runtime.post("feed.leave", source="ole")
            self._preview_active = False

    def submit_drop(self, paths: Sequence[str], screen_x: int, screen_y: int) -> bool:
        if self.drag_enter(paths, screen_x, screen_y) != "copy":
            self.drag_leave()
            return False
        snapshot = FeedDropSnapshot(tuple(str(path) for path in paths),
            int(screen_x), int(screen_y), self.services.runtime.clock.utc_now().isoformat())
        self._preview_active = False
        self.services.runtime.post("feed.drop", source="ole", drop=snapshot)
        return True

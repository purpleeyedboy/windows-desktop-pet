"""One native drop owner joining expectation to the unchanged safe feed chain."""
from __future__ import annotations

from .drag_runtime import ExpectationDragDropService
from .expectation_window import ExpectationWindow
from .feed_core.foundation_contract import FeedDropSnapshot
from .foundation.platform import Point
from .hunger_window import HungerWindow


class IntegratedDropService(ExpectationDragDropService):
    def __init__(self, feed):
        super().__init__()
        self.feed = feed

    def _head(self, point):
        hit = self.feed.services.regions.hit_test(Point(*point), 'click')
        return hit is not None and hit.part == 'head'

    def enter(self, candidate, point, effects):
        if not self.feed.accepting_input:
            self.leave('feed-blocked')
            return 0
        # Metadata is validated asynchronously by the original expectation owner.
        result = super().enter(candidate, point, effects)
        return 1 if result == 1 and self._head(point) else 0

    def over(self, point, effects):
        if not self.feed.accepting_input:
            self.leave('feed-blocked')
            return 0
        result = super().over(point, effects)
        return 1 if result == 1 and effects & 1 and self._head(point) else 0

    def drop(self, candidate, point, effects):
        handler = self.handler
        if handler is None:
            return 0
        version = handler._version
        valid = (
            self.feed.accepting_input and effects & 1 and candidate.count == 1
            and candidate == handler._candidate and handler._validation is not None
            and handler._validation.valid and handler._debug_until is None
            and handler._tail_until is None and self._head(point)
        )
        if not valid:
            handler.leave('rejected-drop')
            return 0
        # over() can drain health events. Recheck the session afterwards so a
        # replacement drag can never inherit an old drop's validation.
        reconciled = handler.over(point, effects)
        if version != handler._version:
            return 0  # This callback must not cancel its replacement drag.
        if (reconciled != 1 or candidate != handler._candidate
                or not self.feed.accepting_input):
            handler.leave('stale-drop')
            return 0
        runtime = self.feed.services.runtime
        snapshot = FeedDropSnapshot((str(candidate.path),), int(point[0]), int(point[1]),
                                    runtime.clock.utc_now().isoformat())
        handler.leave('drop')
        if (handler._version != version + 1 or handler._candidate is not None
                or not self.feed.accepting_input):
            return 0
        # Only copied data enters the shared queue. FeedBusinessHandler retains
        # final identity checks, owned confirmation, Prepared durability, STA
        # recycle receipts and idempotent hunger rewards; no debug path calls it.
        runtime.post('feed.drop', source='integrated-ole', drop=snapshot)
        return 1

    def close(self):
        try:
            self.feed.close()
        finally:
            super().close()


class IntegratedWindow(ExpectationWindow, HungerWindow):
    """Cooperative presentation layers over one PetWindow and one eye timer."""
    def __init__(self, *args, feed_runtime, **kwargs):
        self.feed_runtime = feed_runtime
        super().__init__(*args, **kwargs)
        self.root.title('桌面宠物 V2.1-ALL | '
                        f'{self.services.build_info.product_version} | '
                        f'git:{self.services.build_info.git_short_hash}')

    def close(self):
        if self._closed:
            return
        try:
            self.feed_runtime.close()
        finally:
            try:
                if self.expectation is not None:
                    self.expectation.close()
            finally:
                # HungerWindow owns the sole hunger checkpoint; do not also
                # invoke ExpectationWindow.close(), which owns it in isolation.
                if self.hunger_runtime is None:
                    self._hunger.close()
                HungerWindow.close(self)

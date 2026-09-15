"""Focused runtime checks; use only in-memory drag values and isolated state."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image
from desktop_pet.foundation.config import BuildInfo, FeatureConfig
from desktop_pet.foundation.platform import Point, Rect
from desktop_pet.foundation.runtime import Activity, Health
from desktop_pet.foundation.services import create_application_services
from desktop_pet.foundation_contract import SharedHungerState
from desktop_pet.hunger import HungerService
from desktop_pet.drag_foundation_adapter import DragCandidate


class DeferredWorker:
    def __init__(self, runtime):
        self.runtime, self.calls = runtime, []
    def submit(self, correlation, operation):
        self.calls.append((correlation, operation))
    def finish(self, index=-1):
        correlation, operation = self.calls[index]
        try:
            result = operation()
        except Exception:
            self.runtime.post("file.result", source="verification", correlation_id=correlation, ok=False)
        else:
            self.runtime.post("file.result", source="verification", correlation_id=correlation, ok=True, result=result)
        self.runtime.drain()
    def close(self):
        pass


def main():
    import importlib.util
    assert importlib.util.find_spec("desktop_pet.drag_runtime") is not None, "missing real shared drag runtime"
    from desktop_pet.drag_runtime import DragExpectationRuntime
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        info = BuildInfo("2.1-drag", date(2026, 9, 9), "verify", "6af8446", FeatureConfig(test_build=True))
        services = create_application_services(info, state_root=root / "state", legacy_root=root / "legacy")
        services.load_state()
        services.file_worker.close()
        services.file_worker = worker = DeferredWorker(services.runtime)
        hunger = HungerService(SharedHungerState(services), utc_clock=lambda: 1_000)
        hunger.set_units(50_000)
        services.regions.update_pose(window=Rect(100, 100, 240, 288), source_size=(640, 768), alpha=Image.new("L", (240, 288), 255))
        shown, restored, handoffs, scheduled = [], [], [], {}
        def schedule(delay, callback):
            key = object()
            scheduled[key] = callback
            return key
        runtime = DragExpectationRuntime(
            services, hunger=hunger,
            frames=tuple(Image.new("RGBA", (640, 768), (i, i, i, 255)) for i in range(5)),
            show_frame=lambda frame: shown.append(frame), restore=lambda: restored.append(True),
            schedule=schedule, cancel=lambda key: scheduled.pop(key, None),
            inspector=SimpleNamespace(inspect=lambda path: SimpleNamespace(size_bytes=1048576)),
            consume_drop=handoffs.append,
        )
        candidate = DragCandidate(r"C:\synthetic\never-opened.txt", 1)
        head, body = (180, 140), (180, 330)
        outside = (2000, 2000)
        assert runtime.enter(candidate, body, 1) == 0
        worker.finish()
        assert runtime.active and shown, "body hover inside expectation circle must start preview"
        assert runtime.over(head, 1) == 1 and runtime.active
        token = services.runtime.coordinator.current_token
        assert token.activity is Activity.DRAG_PREVIEW
        assert len(shown) == 1
        assert runtime.over(outside, 1) == 0 and not runtime.active
        for _ in range(3):
            key = next(iter(scheduled))
            scheduled.pop(key)()
            services.runtime.drain()
        assert services.runtime.snapshot().activity is Activity.IDLE and restored
        assert runtime.over(head, 1) == 1 and runtime.active
        runtime.leave()
        for callback in tuple(scheduled.values()):
            callback()
        assert not runtime.active, "cancelled timer resurrected preview"

        runtime.enter(candidate, head, 1)
        runtime.leave()
        worker.finish()
        assert not runtime.active, "late file validation resurrected preview"

        runtime.enter(candidate, head, 1)
        runtime.over(outside, 1)
        worker.finish()
        assert not runtime.active, "validation used stale circle coordinates"
        runtime.over(head, 1)
        assert runtime.active
        hunger.set_units(100_000)
        runtime.over(head, 1)
        assert not runtime.active, "fullness must stop active preview"
        runtime.leave()
        count = len(worker.calls)
        runtime.enter(candidate, head, 1)
        assert len(worker.calls) == count and not runtime.active

        hunger.set_units(500)
        runtime.enter(candidate, head, 1)
        worker.finish()
        assert runtime.active, "critical hunger still allows feeding preview"
        runtime.leave()
        runtime.leave()
        for _ in range(3):
            key = next(iter(scheduled))
            scheduled.pop(key)()
            services.runtime.drain()
        assert services.runtime.snapshot().health is Health.CRITICAL
        assert services.runtime.snapshot().tear == "visible", "leave restores latest health"

        hunger.set_units(50_000)
        runtime.enter(candidate, body, 1)
        worker.finish()
        assert runtime.active
        runtime.drop(candidate, body, 1)
        services.runtime.drain()
        assert not handoffs, "circle must never expand the head-only drop region"
        protected = services.runtime.coordinator.request_activity(Activity.FEED_PROCESSING)
        runtime.enter(candidate, head, 1)
        worker.finish()
        assert not runtime.active and services.runtime.coordinator.current_token == protected
        services.runtime.coordinator.cancel_and_recover(protected)

        runtime.enter(candidate, head, 1)
        worker.finish()
        before = services.state_snapshot()
        assert runtime.drop(candidate, head, 1) == 0
        services.runtime.drain()
        assert len(handoffs) == 1 and handoffs[0].candidate == candidate
        assert services.state_snapshot() == before, "preview/drop must not award or recycle"
        assert runtime.drop(candidate, head, 1) == 0
        services.runtime.drain()
        assert len(handoffs) == 1, "drop handoff must be one-shot"

        before = services.state_snapshot()
        assert runtime.debug_preview() == 1 and runtime.active
        runtime.leave()
        assert services.state_snapshot() == before, "debug preview must not change persisted hunger"

        runtime.debug_preview()
        restore_count = len(restored)
        previous_cancel = runtime._cancel
        runtime._cancel = lambda _key: (_ for _ in ()).throw(RuntimeError("timer cancellation failed"))
        try:
            runtime.leave("exception")
        except RuntimeError:
            pass
        finally:
            runtime._cancel = previous_cancel
        assert len(restored) == restore_count + 1, "timer cancellation failure must still restore the graphic"
        assert services.runtime.snapshot().activity is Activity.IDLE

        reentry_failures = []
        hunger.set_units(50_000)
        runtime.debug_preview()
        runtime.leave()
        hunger.set_units(500)
        scheduled.pop(runtime._timer)()
        services.runtime.post("transaction.review", source="verification")
        before_count = len(shown)
        services.runtime.drain()
        assert services.runtime.snapshot().activity is Activity.TRANSACTION_REVIEW
        if len(shown) != before_count:
            reentry_failures.append("expired exit tick rendered after transaction review preempted it")
        runtime.leave("reset")
        services.runtime.coordinator.cancel_and_recover()

        # A verified drag may keep visual-only expectation after native DragLeave.
        pointer = [(180, 330), True]
        runtime._pointer_state = lambda: (pointer[0], pointer[1])
        hunger.set_units(50_000)
        runtime.enter(candidate, head, 1)
        worker.finish()
        runtime.leave()
        assert runtime.active, "validated drag should retain passive circular preview"
        assert runtime._reconcile() == 1
        pointer[1] = False
        runtime._reconcile()
        assert not runtime.active, "button release outside must clear passive preview"
        runtime._pointer_state = None

        hunger.set_units(50_000)
        runtime.enter(candidate, head, 1)
        request, inspect = worker.calls[-1]
        replacement = DragCandidate(r"C:\synthetic\also-never-opened.txt", 1)
        services.runtime.bind("verification.replace-drag", lambda _event: runtime.enter(replacement, head, 1))
        hunger.set_units(500)
        services.runtime.post("file.result", source="verification", correlation_id=request,
                              ok=True, result=inspect())
        services.runtime.post("verification.replace-drag", source="verification")
        services.runtime.drain()
        assert runtime._candidate == replacement
        if runtime._validation is not None or runtime.active:
            reentry_failures.append("old validation applied to a replacement drag during nested health drain")
        runtime.leave("reset")
        assert not reentry_failures, "; ".join(reentry_failures)

        runtime.close()
        services.close()
    print("PASS: shared drag lifecycle, late-result rejection, reentrant ownership, real hunger, priority, one-shot handoff")


if __name__ == "__main__":
    main()

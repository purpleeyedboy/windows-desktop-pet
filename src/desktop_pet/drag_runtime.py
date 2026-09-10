"""File expectation over the real shared state, coordinator and STA worker.

Only file metadata is inspected. A drop produces one copied handoff event; the
expectation candidate has no recycler and never changes hunger rewards.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from uuid import uuid4

from .drag_foundation_adapter import DragCandidate, FileValidation
from .feed_core.business import quote_reward
from .feed_core.windows_identity import WindowsFileIdentityInspector
from .foundation.platform import Point
from .foundation.runtime import Activity
from .foundation_contract import HEALTH
from .ole_drop_target import DropTargetRegistration, FoundationOleDropTarget


@dataclass(frozen=True)
class ExpectationDrop:
    candidate: DragCandidate
    screen_point: tuple[int, int]
    received_at: float
    session_version: int
    validation: FileValidation

    @property
    def path(self):
        return self.candidate.path

    @property
    def count(self):
        return self.candidate.count


class DragExpectationRuntime:
    def __init__(self, services, *, hunger, frames, show_frame, restore,
                 schedule, cancel, inspector=None, consume_drop=None,
                 durations_ms=(50, 50, 50, 20, 20), pointer_state=None):
        if len(frames) != 5 or any(frame.mode != "RGBA" for frame in frames):
            raise ValueError("expectation requires five real RGBA frames")
        if len(set(frame.size for frame in frames)) != 1:
            raise ValueError("expectation frames must share the runtime canvas")
        self.services, self.hunger = services, hunger
        self.frames = tuple(frames)
        self._show, self._restore = show_frame, restore
        self._schedule, self._cancel = schedule, cancel
        self._durations = tuple(durations_ms)
        roots = [services.paths.root]
        roots.extend(Path(value) for key in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)") if (value := os.environ.get(key)))
        self._inspector = inspector or WindowsFileIdentityInspector(roots)
        self._consume_drop = consume_drop
        self._version = 0
        self._candidate = self._validation = self._request = None
        self._point, self._effects = (0, 0), 0
        self._token = self._timer = None
        self._frame_index = 0
        self._closed = False
        self._ending = False
        self._debug_until = None
        self._pointer_state = pointer_state
        self._tail_until = None
        services.runtime.bind("file.result", self._validated)
        services.runtime.bind("expectation.tick", self._tick)
        services.runtime.bind("expectation.handoff", self._handoff)

    @property
    def active(self):
        return self._token is not None and not self._ending

    @property
    def showing(self):
        return self._token is not None

    def _refresh_health(self):
        snapshot = self.hunger.snapshot()
        runtime = self.services.runtime
        if runtime.snapshot().health is not HEALTH[snapshot.level]:
            runtime.set_health(HEALTH[snapshot.level], source="expectation")
            runtime.drain()
        return snapshot.units

    def _in_region(self, purpose):
        hit = self.services.regions.hit_test(Point(*self._point), purpose)
        return hit is not None and (purpose in ("drag", "expectation") or hit.part == "head")

    def enter(self, candidate, point, effects):
        self.leave("replaced")
        if self._closed:
            return 0
        self._point, self._effects = tuple(point), int(effects)
        if candidate.count != 1 or not effects & 1 or not self._in_region("expectation") or self._refresh_health() >= 100_000:
            return 0
        self._candidate = candidate
        self._request = f"expectation:{uuid4().hex}"
        request, version = self._request, self._version
        def inspect():
            snapshot = self._inspector.inspect(candidate.path)
            return version, int(snapshot.size_bytes)
        try:
            self.services.file_worker.submit(request, inspect)
        except Exception:
            self.leave("worker-unavailable")
        return 0

    def _validated(self, event):
        if self._closed or event.correlation_id != self._request:
            return
        self._request = None
        if not event.payload.get("ok"):
            self.leave("invalid-file")
            return
        version, size = event.payload["result"]
        if version != self._version or self._candidate is None:
            return
        candidate = self._candidate
        current_units = self._refresh_health()
        # Publishing health drains the shared queue and can replace this drag.
        if self._closed or version != self._version or candidate != self._candidate:
            return
        try:
            quote = quote_reward(size, current_units)
        except (ValueError, TypeError):
            self.leave("invalid-size")
            return
        self._validation = FileValidation(True, size, quote.theoretical_units, quote.actual_units, quote.overflow_units)
        self._reconcile()

    def over(self, point, effects):
        self._point, self._effects = tuple(point), int(effects)
        return self._reconcile()

    def _reconcile(self):
        if self._closed:
            return 0
        if self._tail_until is not None:
            try:
                point, held = self._pointer_state()
            except Exception:
                point, held = self._point, False
            if not held or self.services.runtime.clock.monotonic() >= self._tail_until:
                self.leave("passive-end")
                return 0
            self._point = tuple(point)
        current_units = self._refresh_health()
        debug_active = self._debug_until is not None and self.services.runtime.clock.monotonic() < self._debug_until
        valid = (not self._closed and self._candidate is not None
                 and self._validation is not None and self._validation.valid
                 and (debug_active or (self._debug_until is None and bool(self._effects & 1)
                      and self._in_region("expectation") and current_units < 100_000)))
        if not valid:
            if self._token is not None and self._candidate is not None and not self._in_region("expectation") and current_units < 100_000:
                self._begin_exit()
            else:
                self._stop_preview()
            return 0
        coordinator = self.services.runtime.coordinator
        if self._token is not None and coordinator.current_token != self._token:
            self._recover_visual()
        if self._ending:
            if self._timer is not None:
                self._cancel(self._timer)
            self._timer = None
            self._ending = False
            self._frame_index = 0
            self._show(self.frames[0])
            self._arm()
        if self._token is None:
            token = coordinator.request_activity(Activity.DRAG_PREVIEW, animation_id=f"expectation:{self._version}", timeout_seconds=60)
            if token is None:
                return 0
            self._token = token
            coordinator.attach_recovery(token, self._recover_visual)
            self._frame_index = 0
            try:
                self._show(self.frames[0])
                self._arm()
            except Exception:
                self._stop_preview()
                raise
        return 1

    def _arm(self):
        version, token = self._version, self._token
        def due():
            if not self._closed:
                self.services.runtime.post("expectation.tick", source="expectation", version=version, token=token)
        self._timer = self._schedule(self._durations[self._frame_index], due)

    def _owns_tick(self, event):
        token = event.payload["token"]
        return (not self._closed and token is not None
                and event.payload["version"] == self._version
                and token == self._token
                and token == self.services.runtime.coordinator.current_token)

    def _tick(self, event):
        if not self._owns_tick(event):
            return
        self._timer = None
        if self._ending:
            self._refresh_health()
            if not self._owns_tick(event):
                return
            if self._frame_index == 0:
                self._stop_preview()
                return
            self._frame_index -= 1
            self._show(self.frames[self._frame_index])
            self._arm()
            return
        if self._reconcile() == 0 or not self._owns_tick(event):
            return
        self._frame_index = self._frame_index + 1 if self._frame_index < 4 else 3
        try:
            self._show(self.frames[self._frame_index])
            self._arm()
        except Exception:
            self._stop_preview()
            raise

    def _recover_visual(self):
        was_active = self._token is not None
        self._tail_until = None
        self._token = None
        self._ending = False
        timer, self._timer = self._timer, None
        try:
            if timer is not None:
                self._cancel(timer)
        finally:
            if was_active:
                self._restore()

    def _stop_preview(self):
        token = self._token
        if token is not None and self.services.runtime.coordinator.current_token == token:
            self.services.runtime.coordinator.cancel_and_recover(token)
        else:
            self._recover_visual()

    def _begin_exit(self):
        if self._token is None or self._ending:
            return
        try:
            if self._timer is not None:
                self._cancel(self._timer)
            self._timer = None
            self._ending = True
            self._frame_index = 2
            self._show(self.frames[2])
            self._arm()
        except Exception:
            self._stop_preview()
            raise

    def leave(self, reason="leave"):
        # No hook, overlay HWND or IDataObject proxy: only a bounded cursor poll
        # AFTER our own native DragEnter has already validated the file.
        if (reason == "leave" and self.active and self._validation is not None
                and self._validation.valid and self._pointer_state is not None
                and self._debug_until is None):
            self._tail_until = self.services.runtime.clock.monotonic() + 10.0
            self._reconcile()
            return
        self._tail_until = None
        if reason == "leave" and self._ending:
            self._candidate = self._validation = self._request = None
            return
        self._version += 1
        self._candidate = self._validation = self._request = None
        self._debug_until = None
        self._refresh_health()
        if reason == "leave" and self._token is not None:
            self._begin_exit()
        else:
            self._stop_preview()

    def drop(self, candidate, point, effects):
        self._point, self._effects = tuple(point), int(effects)
        accepted = self._tail_until is None and self._debug_until is None and candidate == self._candidate and self._in_region("click") and self._reconcile() == 1
        event = None
        if accepted:
            event = ExpectationDrop(candidate, tuple(point), self.services.runtime.clock.monotonic(), self._version, self._validation)
        self.leave("drop")
        if event is not None:
            self.services.runtime.post("expectation.handoff", source="expectation", event=event)
        return 0

    def _handoff(self, event):
        if not self._closed and self._consume_drop is not None:
            self._consume_drop(event.payload["event"])

    def debug_preview(self):
        self.services.build_info.feature_config.require_debug_injection()
        self.leave("debug-preview")
        self._debug_until = self.services.runtime.clock.monotonic() + 3.0
        self._candidate = DragCandidate("", 1)
        self._validation = FileValidation(True, 0, 0, 0, 0)
        return self._reconcile()

    def close(self):
        if self._closed:
            return
        self.leave("close")
        self._closed = True


class ExpectationDragDropService:
    """Replace the foundation diagnostic target before PetWindow registers OLE."""
    def __init__(self):
        self.handler = None
        self.registration = None

    def register(self, hwnd):
        if os.name != "nt":
            return
        self.registration = DropTargetRegistration(hwnd, FoundationOleDropTarget(self))
        self.registration.register()

    def enter(self, *args):
        return self.handler.enter(*args) if self.handler is not None else 0
    def over(self, *args):
        return self.handler.over(*args) if self.handler is not None else 0
    def leave(self, reason="leave"):
        if self.handler is not None:
            self.handler.leave(reason)
    def drop(self, *args):
        return self.handler.drop(*args) if self.handler is not None else 0
    def candidate_snapshot(self):
        return {"registered": bool(self.registration and self.registration.registered), "candidate_count": int(self.handler is not None and self.handler._candidate is not None)}
    def close(self):
        if self.handler is not None:
            self.handler.close()
        if self.registration is not None:
            self.registration.revoke()
            self.registration = None

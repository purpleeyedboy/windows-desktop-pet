"""Focused V2.1-EARS queue/coordinator/adapter gate; deliberately not pytest."""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.ear_interaction import EAR_KEYFRAMES, EAR_MOTION, EarFeatureAdapter, EarRasterPose
from desktop_pet.assets import load_frames, load_head_neck_compositor
from desktop_pet.eye_follow import CursorPoint
from desktop_pet.eye_runtime import RuntimeEyeSession, SessionResult
from desktop_pet.foundation.platform import Rect
from desktop_pet.foundation.animation import AnimationChannels
from desktop_pet.foundation.runtime import Activity, Health, RuntimeContext
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.idle_head_tilt import IdleTiltPose
from desktop_pet.model import ActionCycle
from desktop_pet.window import PetWindow, _CachedCenterCompositor

class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


class ManualScheduler:
    def __init__(self) -> None:
        self.pending: list[object] = []
        self.history: list[int] = []

    def schedule(self, _delay_ms: int, callback) -> object:
        handle = object()
        self.history.append(_delay_ms)
        self.pending.append((handle, callback))
        return handle

    def cancel(self, handle: object) -> None:
        self.pending = [item for item in self.pending if item[0] is not handle]

    def step(self) -> None:
        _handle, callback = self.pending.pop(0)
        callback()


def require_source() -> None:
    source = (ROOT / "src/desktop_pet/window.py").read_text(encoding="utf-8")
    ast.parse(source)
    required = (
        'runtime.bind("input.ear", self._consume_ear)',
        'self._post_and_drain("input.ear", side=side)',
        'request_activity(\n            Activity.EAR_ACTION',
        'self.services.animation.play("ears", side, token)',
        'self.services.animation.complete(',
        'self.services.animation.recover("ears", self._ear_context)',
        'EarHitMasks.from_frame(frame, self._ear_point_mapper())',
        'system_drag_threshold(self.root.winfo_id())',
        'self._ear_compositor.set_ear_keyframe(side, pose.frame_index)',
        'self.eye_session.refresh_current_pose()',
    )
    missing = [item for item in required if item not in source]
    if missing:
        raise RuntimeError(f"ear runtime wiring missing: {missing}")
    ear_source = (ROOT / "src/desktop_pet/ear_interaction.py").read_text(encoding="utf-8")
    if "Image.Transform.MESH" in ear_source or "render_ear_pose" in source:
        raise RuntimeError("runtime ear mesh path is still reachable")


def require_current_pose_refresh() -> None:
    """Use the real cache/session with fake cursor and scheduler; no desktop IO."""
    clock = ManualClock()
    scheduler = ManualScheduler()
    compositor = _CachedCenterCompositor(load_head_neck_compositor())
    rendered = []

    class FixedCursor:
        def position(self):
            return CursorPoint(240, 350)

    session = RuntimeEyeSession(
        compositor=compositor,
        cursor_provider=FixedCursor(),
        rect_provider=lambda: Rect(0, 0, 640, 768),
        display=rendered.append,
        scheduler=scheduler.schedule,
        cancel=scheduler.cancel,
        clock=clock.monotonic,
        on_disabled=lambda: None,
        action_cycle=ActionCycle(),
        physical_frames=load_frames(ROOT / "assets/keyframes"),
        play_action=lambda _: True,
        cancel_action=lambda _: True,
        choose_phrase=lambda _: "",
        present_phrase=lambda _: None,
        on_action_failed=lambda *_: None,
        head_follow=True,
    )
    if session.start() is not SessionResult.ACCEPTED:
        raise RuntimeError("ear verification session could not start")
    for pose, head, tilt in (((0.0, 0.0), (0.0, 0.0), 0.0), ((1.5, -1.0), (0.2, -0.1), 18.0)):
        session._idle_tilt_pose = IdleTiltPose(tilt, 0.0)
        session._try_display_pose(pose, session._lifecycle_epoch, "following", head)
        neutral = rendered[-1].tobytes()
        compositor.set_ear_keyframe("left", 3)
        if not session.refresh_current_pose() or rendered[-1].tobytes() == neutral:
            raise RuntimeError("ear frame hidden by center cache or refresh failure")
        if session.last_displayed_pose != pose or session.last_displayed_head_pose != head:
            raise RuntimeError("ear refresh moved the eye/head pose")
        compositor.set_ear_keyframe(None, None)
        if not session.refresh_current_pose() or rendered[-1].tobytes() != neutral:
            raise RuntimeError("ear cancellation failed exact current-pose recovery")
    session.stop()

    # Recovery must clear the selected crop even if the timer/adapter already
    # ended, so an inactive cancel result cannot strand a visible ear pose.
    compositor.set_ear_keyframe(None, None)
    neutral = compositor.compose_head(0.0, 0.0, HeadPose(0.0, 0.0)).tobytes()
    compositor.set_ear_keyframe("left", 3)
    window = object.__new__(PetWindow)
    window._ear_adapter = EarFeatureAdapter(scheduler.schedule, scheduler.cancel,
                                           clock.monotonic, lambda *_: None, lambda *_: None)
    window._ear_compositor = compositor
    window._ear_context = object()
    window._ear_pose = EarRasterPose(8)
    window.eye_session = session
    if not window._recover_ear_channel() or window._ear_context is not None:
        raise RuntimeError("inactive ear recovery retained action ownership")
    restored = compositor.compose_head(0.0, 0.0, HeadPose(0.0, 0.0)).tobytes()
    if restored != neutral:
        raise RuntimeError("inactive ear recovery retained compositor selection")


def require_stale_callback_rejected() -> None:
    scheduler = ManualScheduler()
    rendered = []
    adapter = EarFeatureAdapter(scheduler.schedule, scheduler.cancel, lambda: 0.0,
                                lambda *args: rendered.append(args), lambda *_: None)
    adapter.start_approved("left", object())
    stale = scheduler.pending[0][1]
    adapter.cancel_active()
    adapter.start_approved("right", object())
    before = (len(rendered), len(scheduler.pending))
    stale()
    if (len(rendered), len(scheduler.pending)) != before:
        raise RuntimeError("cancelled ear callback advanced a newer action")
    adapter.cancel_active()


def main() -> int:
    require_source()
    require_current_pose_refresh()
    require_stale_callback_rejected()
    compositor = load_head_neck_compositor()
    for degrees in (0.0, 18.0, -18.0):
        pose = HeadPose(0.0, 0.0, degrees, 0.0)
        compositor.set_ear_keyframe(None, None)
        neutral = compositor.compose_head(1.5, -1.0, pose)
        compositor.set_ear_keyframe("left", 3)
        animated = compositor.compose_head(1.5, -1.0, pose)
        compositor.set_ear_keyframe("left", 7)
        restored = compositor.compose_head(1.5, -1.0, pose)
        if animated.tobytes() == neutral.tobytes() or restored.tobytes() != neutral.tobytes():
            raise RuntimeError(f"pre-deformation raster composition failed at {degrees} degrees")
    clock = ManualClock()
    runtime = RuntimeContext(clock)
    scheduler = ManualScheduler()
    rendered: list[tuple[str, EarRasterPose]] = []
    channels = AnimationChannels(runtime.coordinator)
    holder = {"token": None}

    def completed(token, safe: bool) -> None:
        if not safe or token != holder["token"]:
            raise RuntimeError("stale or unsafe ear completion")
        if not channels.complete("ears", token, token.animation_id or ""):
            raise RuntimeError("shared completion rejected")
        holder["token"] = None

    adapter = EarFeatureAdapter(
        scheduler.schedule,
        scheduler.cancel,
        clock.monotonic,
        lambda side, pose: rendered.append((side, pose)),
        completed,
    )
    channels.register("ears", lambda side: adapter.start_approved(side, holder["token"]), adapter.cancel_active)

    runtime.bind("input.ear", lambda event: start(str(event.payload["side"])))

    def start(side: str) -> None:
        animation_id = f"ear:{side}"
        token = runtime.coordinator.request_activity(Activity.EAR_ACTION, animation_id=animation_id, timeout_seconds=2.0)
        if token is None:
            return
        holder["token"] = token
        if not channels.play("ears", side, token):
            holder["token"] = None
            runtime.coordinator.cancel_and_recover(token)

    runtime.post("input.ear", source="probe", side="left")
    runtime.drain()
    first = holder["token"]
    if first is None or not adapter.active:
        raise RuntimeError("queue did not reach the ear adapter")
    runtime.post("input.ear", source="probe", side="right")
    runtime.drain()
    if holder["token"] != first:
        raise RuntimeError("second ear click restarted the shared lock")

    frames = EAR_KEYFRAMES["left"].frames
    angles = [abs(frame.angle_degrees) for frame in frames]
    if (sum(frame.duration_ms for frame in frames) != 1000
            or angles[:4] != sorted(angles[:4])
            or angles[3:] != sorted(angles[3:], reverse=True)):
        raise RuntimeError("single recoil/return timing sequence is invalid")
    if frames[3].frame_id != "throw-maximum" or frames[-1].angle_degrees != 0.0:
        raise RuntimeError("authored throw or exact neutral frame is absent")

    while adapter.active:
        clock.now += EAR_MOTION.frame_ms / 1000
        scheduler.step()
    if scheduler.history[:8] != [frame.duration_ms for frame in frames]:
        raise RuntimeError("adapter did not play the authored per-frame durations")
    if runtime.snapshot().activity is not Activity.IDLE or rendered[-1][1].frame_index != 7:
        raise RuntimeError("natural completion did not restore exact neutral")

    runtime.post("input.ear", source="probe", side="right")
    runtime.drain()
    if not adapter.active:
        raise RuntimeError("completed ear action did not allow immediate replay")
    token = holder["token"]
    if token is None:
        raise RuntimeError("ear did not unlock immediately")
    higher = runtime.coordinator.request_activity(Activity.CONTEXT_MENU_OPEN)
    if higher is None or adapter.active or rendered[-1][1] != EarRasterPose():
        raise RuntimeError("high-priority recovery did not cancel to neutral")
    holder["token"] = None
    runtime.coordinator.cancel_and_recover(higher)

    # Exercise the real queue/channel lock for 100 rapid alternating requests.
    for index in range(100):
        clock.now += EAR_MOTION.cooldown_seconds
        runtime.post(
            "input.ear",
            source="rapid-probe",
            side="left" if index % 2 == 0 else "right",
        )
        runtime.drain()
        if holder["token"] is None:
            raise RuntimeError(f"rapid interaction {index} was not accepted")
        while adapter.active:
            clock.now += EAR_MOTION.frame_ms / 1000
            scheduler.step()
        if runtime.snapshot().activity is not Activity.IDLE:
            raise RuntimeError(f"rapid interaction {index} did not recover")

    runtime.coordinator._set_health(Health.CRITICAL)
    if runtime.coordinator.request_activity(Activity.EAR_ACTION, animation_id="ear:left") is not None:
        raise RuntimeError("critical health accepted an ear action")

    print("V2.1-EARS runtime wiring verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

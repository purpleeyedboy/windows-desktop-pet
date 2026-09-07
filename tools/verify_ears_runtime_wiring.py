"""Focused V2.1-EARS queue/coordinator/adapter gate; deliberately not pytest."""
from __future__ import annotations

import ast
from pathlib import Path

from desktop_pet.ear_interaction import EAR_MOTION, EarFeatureAdapter, EarPose, sample_ear_pose
from desktop_pet.foundation.animation import AnimationChannels
from desktop_pet.foundation.runtime import Activity, Health, RuntimeContext

ROOT = Path(__file__).resolve().parents[1]


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


class ManualScheduler:
    def __init__(self) -> None:
        self.pending: list[object] = []

    def schedule(self, _delay_ms: int, callback) -> object:
        handle = object()
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
    )
    missing = [item for item in required if item not in source]
    if missing:
        raise RuntimeError(f"ear runtime wiring missing: {missing}")


def main() -> int:
    require_source()
    clock = ManualClock()
    runtime = RuntimeContext(clock)
    scheduler = ManualScheduler()
    rendered: list[tuple[str, EarPose]] = []
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

    samples = [sample_ear_pose("left", EAR_MOTION.shake_seconds * i / 12).angle_degrees for i in range(13)]
    direction_changes = sum((a < b > c) or (a > b < c) for a, b, c in zip(samples, samples[1:], samples[2:]))
    if direction_changes < 5:
        raise RuntimeError("three discernible shake cycles are absent")

    while adapter.active:
        clock.now += EAR_MOTION.frame_ms / 1000
        scheduler.step()
    if runtime.snapshot().activity is not Activity.IDLE or rendered[-1][1] != EarPose():
        raise RuntimeError("natural completion did not restore exact neutral")

    runtime.post("input.ear", source="probe", side="right")
    runtime.drain()
    if adapter.active:
        raise RuntimeError("cooldown did not reject immediate replay")
    clock.now += EAR_MOTION.cooldown_seconds
    runtime.post("input.ear", source="probe", side="right")
    runtime.drain()
    token = holder["token"]
    if token is None:
        raise RuntimeError("ear did not unlock after cooldown")
    higher = runtime.coordinator.request_activity(Activity.CONTEXT_MENU_OPEN)
    if higher is None or adapter.active or rendered[-1][1] != EarPose():
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

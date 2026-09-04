"""Scheduler/lifecycle adapter around the hunger state owner."""

from __future__ import annotations

from pathlib import Path
import os
import time
from typing import Callable, Protocol

from .hunger import HungerStore, HungerSystem, system_utc_seconds
from .hunger_animation import HungerAnimationController, HungerAnimationFrame


class AdvanceableClock(Protocol):
    def advance(self, seconds: int) -> None: ...


def default_hunger_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "WindowsDesktopPet" / "hunger-v1.json"
    return Path.home() / ".windows-desktop-pet" / "hunger-v1.json"


def enable_debug_time_simulation(
    *, test_build: bool, clock: object, seconds: int
) -> None:
    if not test_build:
        raise RuntimeError("debug time simulation is disabled outside a test build")
    advance = getattr(clock, "advance", None)
    if not callable(advance):
        raise TypeError("debug simulation requires an injected mutable clock")
    advance(int(seconds))


class HungerRuntime:
    # Ten presentation frames per second is enough for the deliberately small
    # programmatic effect; persistence remains independently throttled.
    TICK_MS = 100

    def __init__(
        self,
        *,
        store: HungerStore,
        utc_clock: Callable[[], int] = system_utc_seconds,
        monotonic_clock: Callable[[], float] = time.monotonic,
        schedule: Callable[[int, Callable[[], None]], object],
        cancel: Callable[[object], None],
        on_frame: Callable[[HungerAnimationFrame], None] | None = None,
        save_interval_s: int = 60,
    ) -> None:
        self.store = store
        self.utc_clock = utc_clock
        self.schedule = schedule
        self.cancel = cancel
        self.on_frame = on_frame or (lambda _frame: None)
        if save_interval_s <= 0:
            raise ValueError("save interval must be positive")
        self.save_interval_s = int(save_interval_s)
        self.monotonic_clock = monotonic_clock
        self.system: HungerSystem = store.load(now_utc_s=utc_clock())
        self.animation = HungerAnimationController(clock=monotonic_clock)
        self._saved_signature = self._persistence_signature()
        self._last_save_time = monotonic_clock()
        self._token: object | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tick()

    def _tick(self) -> None:
        if not self._running:
            return
        self.system.advance_to(self.utc_clock())
        self.on_frame(self.animation.update(self.system.level))
        self._save_if_needed(
            critical=self.system.level.value != self._saved_signature[1]
        )
        self._token = self.schedule(self.TICK_MS, self._tick)

    def _persistence_signature(self) -> tuple[object, ...]:
        payload = self.system.payload()
        return (
            payload["value_units"],
            payload["level"],
            tuple(payload["reward_ids"]),
        )

    def _save_if_needed(self, *, critical: bool = False, force: bool = False) -> None:
        signature = self._persistence_signature()
        if signature == self._saved_signature:
            return
        now = self.monotonic_clock()
        if not force and not critical and now - self._last_save_time < self.save_interval_s:
            return
        self.store.save(self.system)
        self._saved_signature = signature
        self._last_save_time = now

    def user_animation_started(self) -> None:
        self.animation.user_animation_started()

    def user_animation_finished(self) -> None:
        self.on_frame(self.animation.user_animation_finished())

    def stop(self) -> None:
        self._running = False
        if self._token is not None:
            try:
                self.cancel(self._token)
            except Exception:
                pass
            self._token = None
        self.system.advance_to(self.utc_clock())
        self._save_if_needed(force=True)

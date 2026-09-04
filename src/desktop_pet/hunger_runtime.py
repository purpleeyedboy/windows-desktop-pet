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
    TICK_MS = 1_000

    def __init__(
        self,
        *,
        store: HungerStore,
        utc_clock: Callable[[], int] = system_utc_seconds,
        monotonic_clock: Callable[[], float] = time.monotonic,
        schedule: Callable[[int, Callable[[], None]], object],
        cancel: Callable[[object], None],
        on_frame: Callable[[HungerAnimationFrame], None] | None = None,
    ) -> None:
        self.store = store
        self.utc_clock = utc_clock
        self.schedule = schedule
        self.cancel = cancel
        self.on_frame = on_frame or (lambda _frame: None)
        self.system: HungerSystem = store.load(now_utc_s=utc_clock())
        self.animation = HungerAnimationController(clock=monotonic_clock)
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
        self.store.save(self.system)
        self._token = self.schedule(self.TICK_MS, self._tick)

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
        self.store.save(self.system)

from pathlib import Path

import pytest

from desktop_pet.hunger import HungerConfig, HungerStore, MutableUtcClock
from desktop_pet.hunger_runtime import HungerRuntime, enable_debug_time_simulation


class Scheduler:
    def __init__(self) -> None:
        self.pending = []

    def after(self, delay, callback):
        self.pending.append((delay, callback))
        return len(self.pending)

    def cancel(self, _token):
        pass


def test_runtime_uses_injected_clock_storage_and_persists_on_stop(tmp_path) -> None:
    from datetime import datetime, timezone

    clock = MutableUtcClock(datetime(2026, 9, 4, tzinfo=timezone.utc))
    scheduler = Scheduler()
    path = tmp_path / "state.json"
    runtime = HungerRuntime(
        store=HungerStore(path, HungerConfig(decay_units=60, decay_period_s=60)),
        utc_clock=clock.utc_seconds,
        monotonic_clock=lambda: 0.0,
        schedule=scheduler.after,
        cancel=scheduler.cancel,
    )
    initial = runtime.system.value_units
    runtime.start()
    clock.advance(60)
    scheduler.pending.pop()[1]()
    assert runtime.system.value_units == initial - 60
    runtime.stop()
    assert path.is_file()


def test_debug_time_simulation_is_impossible_in_production() -> None:
    with pytest.raises(RuntimeError, match="test build"):
        enable_debug_time_simulation(test_build=False, clock=object(), seconds=60)


def test_debug_time_simulation_requires_mutable_injected_clock() -> None:
    class Clock:
        def __init__(self): self.value = 0
        def advance(self, seconds): self.value += seconds

    clock = Clock()
    enable_debug_time_simulation(test_build=True, clock=clock, seconds=120)
    assert clock.value == 120

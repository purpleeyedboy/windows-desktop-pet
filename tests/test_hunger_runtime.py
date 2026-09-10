import pytest

from desktop_pet.hunger import OffsetUtcClock
from desktop_pet.hunger_runtime import enable_debug_time_simulation


def test_debug_time_simulation_is_impossible_in_production():
    with pytest.raises(RuntimeError, match="test build"):
        enable_debug_time_simulation(test_build=False, clock=object(), seconds=60)


def test_debug_time_simulation_requires_mutable_injected_clock():
    clock = OffsetUtcClock(lambda: 1_000)
    enable_debug_time_simulation(test_build=True, clock=clock, seconds=120)
    assert clock.utc_seconds() == 1_120
    with pytest.raises(ValueError, match="backwards"):
        enable_debug_time_simulation(test_build=True, clock=clock, seconds=-1)

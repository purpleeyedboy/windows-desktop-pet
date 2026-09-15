from copy import deepcopy

import pytest

from desktop_pet.hunger import HungerLevel, HungerService, default_hunger_state


class MemoryStore:
    def __init__(self, state=None, recovery="primary"):
        self.state = deepcopy(state)
        self.recovery = recovery
        self.fail = False

    def load_hunger(self, now_utc):
        if self.state is None:
            self.state = default_hunger_state(now_utc)
            self.recovery = "first-launch"
        return deepcopy(self.state), self.recovery

    def commit_hunger(self, state):
        if self.fail:
            raise OSError("injected commit failure")
        self.state = deepcopy(state)


def service_at(units, *, anchor=0, clock=lambda: 0):
    state = default_hunger_state(anchor)
    state["HungerAnchorUnits"] = units
    return HungerService(MemoryStore(state), clock)


def test_level_boundaries_use_strict_v21_thresholds():
    assert HungerService.level_for(20_000) is HungerLevel.NORMAL
    assert HungerService.level_for(19_999) is HungerLevel.HUNGRY
    assert HungerService.level_for(10_000) is HungerLevel.HUNGRY
    assert HungerService.level_for(9_999) is HungerLevel.SEVERE_HUNGRY
    assert HungerService.level_for(1_000) is HungerLevel.SEVERE_HUNGRY
    assert HungerService.level_for(999) is HungerLevel.CRITICAL_HUNGRY


def test_elapsed_time_and_large_offline_step_are_integer_and_saturating():
    hunger = service_at(100_000)
    assert hunger.snapshot(3_600).units == 50_000
    assert hunger.snapshot(7_200).units == 0
    assert hunger.snapshot(10**100).units == 0


def test_restart_restores_elapsed_time_and_fractional_remainder():
    now = [1]
    store = MemoryStore(default_hunger_state(0))
    hunger = HungerService(store, lambda: now[0])
    hunger.close()
    assert store.state["HungerAnchorUnits"] == 99_987
    assert store.state["HungerDecayRemainder"] == 6_400
    now[0] = 2
    restored = HungerService(store, lambda: now[0])
    restored.close()
    assert store.state["HungerAnchorUnits"] == 99_973
    assert store.state["HungerDecayRemainder"] == 5_600


def test_shutdown_uses_one_clock_sample_so_restart_does_not_lose_decay():
    readings = iter((0, 1, 2))
    store = MemoryStore(default_hunger_state(0))
    hunger = HungerService(store, lambda: next(readings))
    hunger.close()
    assert store.state["HungerAnchorUtc"] == 1
    assert store.state["HungerAnchorUnits"] == 99_987


def test_clock_rollback_never_adds_hunger_or_reanchors_backwards():
    store = MemoryStore(default_hunger_state(10_000))
    store.state["HungerAnchorUnits"] = 5_000
    hunger = HungerService(store, lambda: 9_000)
    assert hunger.snapshot().units == 5_000
    hunger.close()
    assert store.state["HungerAnchorUtc"] == 10_000


def test_reward_is_idempotent_and_failed_commit_is_retryable():
    store = MemoryStore(default_hunger_state(0))
    store.state["HungerAnchorUnits"] = 100
    hunger = HungerService(store, lambda: 0)
    snapshot, applied = hunger.apply_reward("feed-1", 500)
    assert applied and snapshot.units == 600
    assert hunger.apply_reward("feed-1", 500)[1] is False
    store.fail = True
    with pytest.raises(OSError, match="injected"):
        hunger.apply_reward("feed-2", 100)
    assert hunger.snapshot().units == 600
    store.fail = False
    assert hunger.apply_reward("feed-2", 100)[0].units == 700
    assert hunger.apply_reward("feed-2", 100)[1] is False

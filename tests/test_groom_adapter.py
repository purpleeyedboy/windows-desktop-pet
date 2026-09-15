from __future__ import annotations

from desktop_pet.groom_adapter import (
    GroomFeatureAdapter,
    GroomRunIdentity,
    GroomStartRequest,
)


class Rng:
    def __init__(self, side: str, count: int) -> None:
        self.side = side
        self.count = count

    def choice(self, _values):
        return self.side

    def randint(self, _low, _high):
        return self.count


def identity(version: int = 7) -> GroomRunIdentity:
    return GroomRunIdentity("groom-1", version, "cancel-1")


def test_adapter_starts_only_an_already_authorized_request_and_fixes_side_count() -> None:
    adapter = GroomFeatureAdapter(rng=Rng("left", 20))

    assert adapter.start(GroomStartRequest(identity(), 10.0, authorized=False)) is False
    assert adapter.start(GroomStartRequest(identity(), 10.0, authorized=True)) is True
    assert adapter.side == "left"
    assert adapter.planned_licks == 20
    assert adapter.total_duration <= 13.0
    assert adapter.lick_duration == 0.45


def test_stale_identity_cannot_sample_interrupt_or_complete_new_run() -> None:
    completed = []
    adapter = GroomFeatureAdapter(rng=Rng("right", 3), on_complete=completed.append)
    current = identity(8)
    stale = identity(7)
    adapter.start(GroomStartRequest(current, 4.0, authorized=True))

    assert adapter.sample(5.0, stale).phase == "neutral"
    assert adapter.request_cycle_boundary_stop(stale) is False
    assert adapter.active is True
    assert completed == []


def test_urgent_drag_cancel_recovers_all_channels_within_150ms() -> None:
    completed = []
    adapter = GroomFeatureAdapter(rng=Rng("left", 20), on_complete=completed.append)
    run = identity()
    adapter.start(GroomStartRequest(run, 0.0, authorized=True))
    assert adapter.sample(2.0, run).phase != "neutral"

    assert adapter.request_urgent_recovery(run, 2.0) is True
    recovering = adapter.sample(2.075, run)
    neutral = adapter.sample(2.15, run)

    assert 0.0 < recovering.arm < 1.0
    assert neutral.phase == "neutral"
    assert neutral.arm == neutral.tongue == 0.0
    assert adapter.active is False
    assert completed == [run]


def test_normal_interrupt_finishes_current_lick_then_recovers() -> None:
    adapter = GroomFeatureAdapter(rng=Rng("right", 20))
    run = identity()
    adapter.start(GroomStartRequest(run, 0.0, authorized=True))
    adapter.sample(1.7, run)
    assert adapter.request_cycle_boundary_stop(run) is True

    adapter.sample(1.95, run)

    assert adapter.completed_licks <= 1
    assert adapter.stopping is True

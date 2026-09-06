from dataclasses import dataclass

from desktop_pet.drag_foundation_adapter import (
    DROPEFFECT_COPY,
    DROPEFFECT_NONE,
    DragCandidate,
    DragFoundationAdapter,
    DragRegion,
    FileValidation,
    theoretical_reward_units,
)


class Router:
    def __init__(self): self.calls = []
    def submit(self, callback): self.calls.append(callback); callback()


class Regions:
    region = DragRegion(False, False)
    def classify_drag_point(self, _point): return self.region


class Coordinator:
    def __init__(self): self.events = []
    def begin_drag_preview(self, session, candidate, validation): self.events.append(("begin", session, candidate, validation))
    def end_drag_preview(self, session, reason): self.events.append(("end", session, reason))


class Health:
    full = False
    def is_full(self): return self.full


class Validator:
    def __init__(self): self.requests = []
    def validate_async(self, candidate, session, done): self.requests.append((candidate, session, done))


class Clock:
    def now(self): return 12.5


def make_adapter():
    router, regions, coordinator = Router(), Regions(), Coordinator()
    health, validator = Health(), Validator()
    drops = []
    adapter = DragFoundationAdapter(
        input_router=router,
        regions=regions,
        activities=coordinator,
        hunger=health,
        clock=Clock(),
        validator=validator,
        consume_drop=drops.append,
    )
    return adapter, regions, coordinator, health, validator, drops


def test_theoretical_reward_uses_the_v21_integer_formula():
    assert theoretical_reward_units(1048576) == 10000
    assert theoretical_reward_units(104857) == 999


def test_validation_is_versioned_and_only_valid_head_candidate_returns_copy():
    adapter, regions, coordinator, _, validator, _ = make_adapter()
    candidate = DragCandidate(r"C:\tmp\cat.txt", 1)
    regions.region = DragRegion(True, True)

    assert adapter.enter(candidate, (10, 20), DROPEFFECT_COPY) == DROPEFFECT_NONE
    session = validator.requests[-1][1]
    validator.requests[-1][2](FileValidation(True, 1048576, 100000, 100000, 0))

    assert adapter.over((10, 20), DROPEFFECT_COPY) == DROPEFFECT_COPY
    assert coordinator.events == [("begin", session, candidate, FileValidation(True, 1048576, 100000, 100000, 0))]


def test_stale_validation_cannot_revive_cancelled_or_replaced_session():
    adapter, regions, coordinator, _, validator, _ = make_adapter()
    regions.region = DragRegion(True, True)
    adapter.enter(DragCandidate(r"C:\tmp\one.txt", 1), (1, 1), DROPEFFECT_COPY)
    old_done = validator.requests[-1][2]
    adapter.leave()
    adapter.enter(DragCandidate(r"C:\tmp\two.txt", 1), (1, 1), DROPEFFECT_COPY)

    old_done(FileValidation(True, 10, 1, 1, 0))

    assert not [event for event in coordinator.events if event[0] == "begin"]


def test_non_head_full_health_and_disallowed_source_are_none():
    adapter, regions, _, health, validator, _ = make_adapter()
    regions.region = DragRegion(True, False)
    assert adapter.enter(DragCandidate(r"C:\tmp\cat.txt", 1), (1, 1), DROPEFFECT_COPY) == DROPEFFECT_NONE
    assert validator.requests == []
    regions.region = DragRegion(True, True)
    health.full = True
    assert adapter.enter(DragCandidate(r"C:\tmp\cat.txt", 1), (1, 1), DROPEFFECT_COPY) == DROPEFFECT_NONE
    assert adapter.enter(DragCandidate(r"C:\tmp\cat.txt", 1), (1, 1), DROPEFFECT_NONE) == DROPEFFECT_NONE


def test_drop_copies_values_and_ends_preview_before_async_consumer():
    adapter, regions, coordinator, _, validator, drops = make_adapter()
    regions.region = DragRegion(True, True)
    candidate = DragCandidate(r"C:\tmp\cat.txt", 1)
    adapter.enter(candidate, (1, 2), DROPEFFECT_COPY)
    validator.requests[-1][2](FileValidation(True, 50, 1, 1, 0))

    assert adapter.drop(candidate, (3, 4), DROPEFFECT_COPY) == DROPEFFECT_NONE
    assert drops[0].path == candidate.path
    assert drops[0].count == 1
    assert drops[0].screen_point == (3, 4)
    assert drops[0].received_at == 12.5
    assert coordinator.events[-1][0] == "end"

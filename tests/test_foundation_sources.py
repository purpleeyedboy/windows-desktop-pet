from datetime import datetime, timezone

from desktop_pet.foundation.sources import FixedTimeSource, SeededRandomSource, SystemRandomSource


def test_fixed_time_source_returns_injected_utc_and_monotonic_values():
    instant = datetime(2026, 9, 4, 12, 30, tzinfo=timezone.utc)
    source = FixedTimeSource(instant, 41.5)
    assert source.utc_now() is instant
    assert source.monotonic() == 41.5
    source.advance(2.25)
    assert source.monotonic() == 43.75


def test_seeded_random_source_is_repeatable_but_system_source_is_not_seeded():
    first = SeededRandomSource(2409)
    second = SeededRandomSource(2409)
    assert [first.random() for _ in range(4)] == [second.random() for _ in range(4)]
    assert SystemRandomSource().fixed_seed is None

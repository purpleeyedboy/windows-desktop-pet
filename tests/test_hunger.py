from datetime import datetime, timezone
import json

from desktop_pet.hunger import (
    HungerConfig,
    HungerLevel,
    HungerStore,
    HungerSystem,
    MutableUtcClock,
)


def test_level_boundaries_and_hysteresis_do_not_chatter() -> None:
    config = HungerConfig(max_units=10_000, severe_below=4_000, extreme_below=2_000, hysteresis_units=200)
    hunger = HungerSystem(config=config, value_units=4_001, anchor_utc_s=100)
    assert hunger.level is HungerLevel.NORMAL
    hunger.set_value(4_000)
    assert hunger.level is HungerLevel.SEVERE
    hunger.set_value(4_100)
    assert hunger.level is HungerLevel.SEVERE
    hunger.set_value(4_200)
    assert hunger.level is HungerLevel.NORMAL
    hunger.set_value(2_000)
    assert hunger.level is HungerLevel.EXTREME
    hunger.set_value(2_199)
    assert hunger.level is HungerLevel.EXTREME
    hunger.set_value(2_200)
    assert hunger.level is HungerLevel.SEVERE


def test_integer_time_accumulation_has_no_fractional_drift() -> None:
    config = HungerConfig(max_units=10_000, decay_units=3, decay_period_s=10)
    hunger = HungerSystem(config=config, value_units=10_000, anchor_utc_s=0)
    for second in range(1, 101):
        hunger.advance_to(second)
    assert hunger.value_units == 9_970
    assert hunger.remainder_unit_seconds == 0


def test_restart_restores_real_elapsed_time_and_remainder(tmp_path) -> None:
    config = HungerConfig(max_units=10_000, decay_units=7, decay_period_s=60)
    path = tmp_path / "state.json"
    first = HungerSystem(config=config, value_units=9_000, anchor_utc_s=1_000)
    first.advance_to(1_031)
    HungerStore(path, config).save(first)
    restored = HungerStore(path, config).load(now_utc_s=1_121)
    assert restored.value_units == 8_986
    assert restored.anchor_utc_s == 1_121
    assert restored.remainder_unit_seconds == 7


def test_utc_datetime_is_timezone_independent_and_fixed_clock_is_injectable() -> None:
    clock = MutableUtcClock(datetime(2026, 9, 4, tzinfo=timezone.utc))
    assert clock.utc_seconds() == 1_788_480_000
    clock.advance(3600)
    assert clock.utc_seconds() == 1_788_483_600


def test_clock_rollback_and_future_anchor_never_add_hunger_or_freeze() -> None:
    hunger = HungerSystem(value_units=5_000, anchor_utc_s=10_000)
    hunger.advance_to(9_000)
    assert hunger.value_units == 5_000
    assert hunger.anchor_utc_s == 9_000
    hunger.advance_to(9_100)
    assert hunger.value_units < 5_000


def test_large_offline_step_and_huge_timestamp_saturate_safely() -> None:
    hunger = HungerSystem(value_units=5_000, anchor_utc_s=0)
    hunger.advance_to(10**100)
    assert hunger.value_units == 0
    assert hunger.anchor_utc_s == HungerConfig().max_utc_s


def test_adjustment_clamps_and_reward_interface_is_idempotent() -> None:
    hunger = HungerSystem(value_units=100, anchor_utc_s=0)
    assert hunger.apply_reward("event-1", 500) is True
    assert hunger.apply_reward("event-1", 500) is False
    assert hunger.value_units == 600
    hunger.adjust(10**30)
    assert hunger.value_units == hunger.config.max_units
    hunger.adjust(-(10**30))
    assert hunger.value_units == 0


def test_corrupt_primary_recovers_backup_and_never_reads_real_user_files(tmp_path) -> None:
    config = HungerConfig()
    path = tmp_path / "hunger.json"
    store = HungerStore(path, config)
    original = HungerSystem(config=config, value_units=7_777, anchor_utc_s=100)
    store.save(original)
    original.adjust(-1)
    store.save(original)
    path.write_text("not json", encoding="utf-8")
    recovered = store.load(now_utc_s=100)
    assert recovered.value_units == 7_777


def test_both_corrupt_or_wrong_version_uses_safe_default(tmp_path) -> None:
    path = tmp_path / "hunger.json"
    path.write_text(json.dumps({"version": 999}), encoding="utf-8")
    path.with_suffix(".json.bak").write_text("{}", encoding="utf-8")
    restored = HungerStore(path).load(now_utc_s=123)
    assert restored.value_units == HungerConfig().safe_default_units
    assert restored.anchor_utc_s == 123


def test_save_is_versioned_and_leaves_no_temporary_file(tmp_path) -> None:
    path = tmp_path / "hunger.json"
    HungerStore(path).save(HungerSystem(anchor_utc_s=12))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert not path.with_suffix(".json.tmp").exists()

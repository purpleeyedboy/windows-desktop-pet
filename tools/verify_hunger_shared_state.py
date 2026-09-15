"""Focused shared-state integration check; all state is confined to a temp folder."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desktop_pet.foundation.config import BuildInfo
from desktop_pet.foundation.services import create_application_services
from desktop_pet.foundation.runtime import Activity, Health
from desktop_pet.foundation_contract import SharedHungerState, SharedActivityAdapter
from desktop_pet.hunger import HungerService, HungerLevel


def main() -> int:
    with TemporaryDirectory(prefix="desktop-pet-hunger-verify-") as directory:
        root = Path(directory)
        info = BuildInfo("2.1.2", date(2026, 9, 9), "integration-check")
        services = create_application_services(info, state_root=root / "DesktopPet", legacy_root=root / "absent-legacy")
        services.load_state()
        now = [100_000]
        hunger = HungerService(SharedHungerState(services), lambda: now[0])
        stale_startup = services.state_snapshot()
        now[0] += 3600
        assert hunger.snapshot().units == 50_000
        services.update_state(lambda state: state.update(pending_transaction={"operation_id": "verify", "phase": "confirmed"}), durable=True)
        snapshot, applied = hunger.apply_reward("verify-reward", 12_345)
        assert applied and snapshot.units == 62_345
        assert hunger.apply_reward("verify-reward", 12_345)[1] is False
        current = services.state_snapshot()
        assert current["pending_transaction"]["operation_id"] == "verify"
        assert current["hunger"]["HungerAnchorUnits"] == 62_345
        assert "verify-reward" in current["recent_operation_ids"]
        original_save = services.store.save
        def fail_save(*_args, **_kwargs):
            raise OSError("injected write failure in isolated check")
        services.store.save = fail_save
        try:
            hunger.apply_reward("retry", 100)
        except OSError:
            pass
        else:
            raise AssertionError("failed persistence was not reported")
        assert hunger.snapshot().units == 62_345
        assert services.state_snapshot() == current
        services.store.save = original_save
        assert hunger.apply_reward("retry", 100)[1] is True
        assert hunger.apply_reward("retry", 100)[1] is False
        activity = SharedActivityAdapter(services)
        activity.publish_health(HungerLevel.CRITICAL_HUNGRY, 0)
        assert services.runtime.snapshot().health is Health.CRITICAL
        assert not services.runtime.coordinator.permits(Activity.GROOM)
        assert not services.runtime.coordinator.permits(Activity.BODY_ACTION)
        assert services.runtime.coordinator.permits(Activity.FEED_CONFIRM)
        assert services.runtime.coordinator.permits(Activity.FEED_ANIMATION)
        assert services.runtime.coordinator.permits(Activity.SHUTTING_DOWN)
        hunger.close()
        services.close(stale_startup)
        reopened = create_application_services(info, state_root=root / "DesktopPet", legacy_root=root / "absent-legacy")
        try:
            reopened.load_state()
            restored = HungerService(SharedHungerState(reopened), lambda: now[0])
            assert restored.snapshot().units == 62_445
            assert not restored.apply_reward("retry", 100)[1]
            assert reopened.state_snapshot()["pending_transaction"]["operation_id"] == "verify"
        finally:
            reopened.close()
    print("hunger shared services, atomic reward, critical permissions and restart checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Exit-frame failures must release the shared activity just like loop failures."""
from datetime import date
from types import SimpleNamespace

import pytest
from PIL import Image

from desktop_pet.drag_runtime import DragExpectationRuntime
from desktop_pet.foundation.config import BuildInfo, FeatureConfig
from desktop_pet.foundation.runtime import Activity
from desktop_pet.foundation.services import create_application_services
from desktop_pet.foundation_contract import SharedHungerState
from desktop_pet.hunger import HungerService


@pytest.mark.parametrize("failure", ["render", "schedule"])
def test_exit_callback_failure_recovers_activity(tmp_path, failure):
    info = BuildInfo("2.1-drag", date(2026, 9, 10), "verify", "6af8446", FeatureConfig(test_build=True))
    services = create_application_services(info, state_root=tmp_path / "state", legacy_root=tmp_path / "legacy")
    services.load_state()
    hunger = HungerService(SharedHungerState(services), utc_clock=lambda: 1000)
    restored = []
    def fail(*_args):
        raise RuntimeError("synthetic callback failure")
    runtime = DragExpectationRuntime(
        services, hunger=hunger,
        frames=[Image.new("RGBA", (512, 768)) for _ in range(5)],
        show_frame=lambda _frame: None, restore=lambda: restored.append(True),
        schedule=lambda *_args: object(), cancel=lambda _token: None,
    )
    try:
        runtime.debug_preview()
        runtime._begin_exit()
        event = SimpleNamespace(payload={"version": runtime._version, "token": runtime._token})
        if failure == "render":
            runtime._show = fail
        else:
            runtime._schedule = fail
        with pytest.raises(RuntimeError, match="synthetic callback failure"):
            runtime._tick(event)
        assert not runtime.showing
        assert services.runtime.snapshot().activity is Activity.IDLE
        assert restored == [True]
    finally:
        runtime.close()
        hunger.close()
        services.file_worker.close()


@pytest.mark.parametrize("failure", ["cancel", "render", "schedule"])
def test_reenter_during_exit_callback_failure_recovers_activity(tmp_path, failure):
    info = BuildInfo("2.1-drag", date(2026, 9, 10), "verify", "6af8446", FeatureConfig(test_build=True))
    services = create_application_services(info, state_root=tmp_path / "state", legacy_root=tmp_path / "legacy")
    services.load_state()
    hunger = HungerService(SharedHungerState(services), utc_clock=lambda: 1000)
    restored = []
    runtime = DragExpectationRuntime(
        services, hunger=hunger,
        frames=[Image.new("RGBA", (512, 768)) for _ in range(5)],
        show_frame=lambda _frame: None, restore=lambda: restored.append(True),
        schedule=lambda *_args: object(), cancel=lambda _token: None,
    )
    try:
        runtime.debug_preview()
        runtime._begin_exit()

        def fail(*_args):
            raise RuntimeError("synthetic callback failure")

        if failure == "cancel":
            runtime._cancel = fail
        elif failure == "render":
            runtime._show = fail
        else:
            runtime._schedule = fail
        with pytest.raises(RuntimeError, match="synthetic callback failure"):
            runtime._reconcile()
        assert not runtime.showing
        assert services.runtime.snapshot().activity is Activity.IDLE
        assert restored == [True]
    finally:
        runtime.close()
        hunger.close()
        services.file_worker.close()


def test_expectation_arbitrates_menu_actions_and_protected_activity(tmp_path):
    info = BuildInfo("2.1-drag", date(2026, 9, 10), "verify", "6af8446", FeatureConfig(test_build=True))
    services = create_application_services(info, state_root=tmp_path / "state", legacy_root=tmp_path / "legacy")
    services.load_state()
    hunger = HungerService(SharedHungerState(services), utc_clock=lambda: 1000)
    restored = []
    runtime = DragExpectationRuntime(
        services, hunger=hunger,
        frames=[Image.new("RGBA", (512, 768)) for _ in range(5)],
        show_frame=lambda _frame: None, restore=lambda: restored.append(True),
        schedule=lambda *_args: object(), cancel=lambda _token: None,
    )
    try:
        assert runtime.debug_preview() == 1
        coordinator = services.runtime.coordinator
        expectation_token = coordinator.current_token
        assert expectation_token is not None
        assert coordinator.request_activity(Activity.CONTEXT_MENU_OPEN) is None
        assert coordinator.request_activity(Activity.BODY_ACTION) is None
        assert coordinator.current_token == expectation_token

        protected = coordinator.request_activity(Activity.TRANSACTION_REVIEW)
        assert protected is not None
        assert not runtime.showing
        assert restored == [True]
        assert runtime._reconcile() == 0
        assert coordinator.current_token == protected
    finally:
        runtime.close()
        hunger.close()
        services.file_worker.close()

@pytest.mark.parametrize("late_callback", ["recovery", "leave-health-drain"])
def test_previous_drag_cannot_clear_replacement_preview(tmp_path, late_callback):
    info = BuildInfo("2.1-drag", date(2026, 9, 12), "verify", "eeaa994", FeatureConfig(test_build=True))
    services = create_application_services(info, state_root=tmp_path / "state", legacy_root=tmp_path / "legacy")
    services.load_state()
    hunger = HungerService(SharedHungerState(services), utc_clock=lambda: 1000)
    restored = []
    runtime = DragExpectationRuntime(
        services, hunger=hunger,
        frames=[Image.new("RGBA", (512, 768)) for _ in range(5)],
        show_frame=lambda _frame: None, restore=lambda: restored.append(True),
        schedule=lambda *_args: object(), cancel=lambda _token: None,
    )
    try:
        runtime.debug_preview()
        coordinator = services.runtime.coordinator
        old_recovery = coordinator._recovery[runtime._token.cancellation_id]
        if late_callback == "recovery":
            runtime.debug_preview()
            replacement = runtime._token
            restores_before = len(restored)
            old_recovery()
        else:
            original_refresh = runtime._refresh_health
            replacement = None
            restores_before = None
            def refresh_and_replace():
                nonlocal replacement, restores_before
                runtime._refresh_health = original_refresh
                runtime.debug_preview()
                replacement = runtime._token
                restores_before = len(restored)
                return original_refresh()
            runtime._refresh_health = refresh_and_replace
            runtime.leave("replaced")
        assert replacement is not None
        assert runtime._token == replacement
        assert coordinator.current_token == replacement
        assert runtime.active and runtime._timer is not None
        assert len(restored) == restores_before
    finally:
        runtime.close()
        hunger.close()
        services.file_worker.close()

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

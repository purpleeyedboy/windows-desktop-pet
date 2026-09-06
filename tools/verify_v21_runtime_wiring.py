"""Import and source-reachability gate for the V2.1 runtime candidate (no pytest)."""
from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from desktop_pet.foundation.config import BuildInfo
from desktop_pet.foundation.runtime import Activity, RuntimeContext
from desktop_pet.foundation.services import DEFAULT_STATE, create_application_services
from desktop_pet.foundation.sources import SystemTimeSource


ROOT = Path(__file__).resolve().parents[1]


def require(path: str, snippets: tuple[str, ...], *, python: bool = True) -> None:
    source = (ROOT / path).read_text(encoding="utf-8-sig")
    if python:
        ast.parse(source, filename=path)
    missing = [snippet for snippet in snippets if snippet not in source]
    if missing:
        raise RuntimeError(f"{path} is not wired: {missing}")


def main() -> int:
    require("src/desktop_pet/main.py", (
        "create_application_services(build_info)", "services.store.load",
        "services=services", "notify_existing_instance(build_info)",
    ))
    require("src/desktop_pet/window.py", (
        'runtime.bind("input.action"', 'runtime.bind("input.context_menu"',
        'runtime.post(event_type, source="window"', "coordinator.request_activity",
        "coordinator.complete", "services.regions.update_pose",
        "services.dragdrop.register", "services.close", "finished_with_id=self._animation_finished",
    ))
    require("src/desktop_pet/foundation/services.py", (
        "OleInitialize", "RegisterDragDrop", "RevokeDragDrop",
        'schema="desktop-pet-v2.1"', "SystemTimeSource()", "SystemRandomSource()",
    ))
    require("src/desktop_pet/animation.py", ("playback_id", "self._finished_with_id(action, outcome.playback_id)"))
    require("desktop_pet_v21_core.spec", (
        "desktop_pet_v21_core.manifest", "build_identity.json",
        "桌面宠物_公共基础接线与版本识别修复",
    ), python=False)
    require("build_v21_core.ps1", (
        "foundation_commit = $fullHash", "test_build = $true",
        "debug_menu_enabled = $true", "桌面宠物_公共基础接线与版本识别修复.exe",
    ), python=False)
    ET.parse(ROOT / "desktop_pet_v21_core.manifest")
    runtime = RuntimeContext(SystemTimeSource())
    observed: list[str] = []
    runtime.bind("smoke", lambda event: observed.append(event.correlation_id))
    correlation = runtime.post("smoke", source="wiring-gate")
    if runtime.drain() != 1 or observed != [correlation]:
        raise RuntimeError("runtime queue is not reachable")
    token = runtime.coordinator.request_activity(Activity.BODY_ACTION, animation_id="jump")
    if token is None or not runtime.coordinator.complete(token, animation_id="jump"):
        raise RuntimeError("coordinated animation completion is not reachable")
    with tempfile.TemporaryDirectory(prefix="desktop-pet-v21-wiring-") as directory:
        services = create_application_services(BuildInfo.load_embedded(), Path(directory))
        state = services.store.load(default=DEFAULT_STATE)
        services.close(state)
    print("V2.1 runtime wiring verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

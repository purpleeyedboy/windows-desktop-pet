"""Fail-closed packaging gate for PR5 plus the trusted shared FEED handler."""
from desktop_pet.feed_core.foundation_contract import (
    foundation_feed_ready,
    load_foundation_services,
    load_runtime_context_type,
)
import json
from pathlib import Path

build_info = json.loads(Path("BUILD_INFO_FEED_CORE.json").read_text(encoding="utf-8-sig"))
if load_runtime_context_type() is None or not foundation_feed_ready(
    load_foundation_services(build_info)
):
    raise SystemExit(
        "BLOCKED: codex-od26j1 services/runtime or trusted ProgressSink FEED handler is unavailable"
    )
print("foundation and trusted FEED handler available")

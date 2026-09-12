"""Fail-closed packaging gate for PR5 plus the trusted shared FEED handler."""
from desktop_pet.feed_core.foundation_contract import (
    foundation_feed_ready,
    load_foundation_services,
)

if not foundation_feed_ready(load_foundation_services()):
    raise SystemExit(
        "BLOCKED: PR5 foundation or trusted ProgressSink FEED handler is unavailable"
    )
print("foundation and trusted FEED handler available")

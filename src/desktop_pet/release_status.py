"""Visible identity for test candidates; packaged builds carry generated JSON."""

from __future__ import annotations

import json

from .paths import asset_path


def release_status_text() -> str:
    try:
        identity = json.loads(
            asset_path("build_identity.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        identity = {
            "version": "V2.1-PAWS repair source checkout",
            "git_commit": "source checkout",
            "foundation_commit": "pending PR5 integration",
            "features": ["dual forepaw press", "bounded cursor push"],
            "acceptance": "NOT ACCEPTED - foundation integration pending",
        }
    return "\n".join((
        str(identity["version"]),
        f"Git: {identity['git_commit']}",
        f"Foundation: {identity['foundation_commit']}",
        "Features: " + ", ".join(identity["features"]),
        str(identity["acceptance"]),
    ))

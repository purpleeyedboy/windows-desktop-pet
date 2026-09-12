"""Compatibility exports for the PR5 shared FEED foundation adapter."""
from .foundation_contract import (
    FoundationFeedInputAdapter,
    foundation_feed_ready,
    load_foundation_services,
)

__all__ = ["FoundationFeedInputAdapter", "foundation_feed_ready", "load_foundation_services"]

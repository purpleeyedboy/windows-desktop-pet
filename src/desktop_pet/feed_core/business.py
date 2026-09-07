"""FEED business handler using only shared-foundation and feature ports."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

MIB = 1_048_576
MAX_BYTES = 1_073_741_824
HUNGER_CAPACITY = 100_000


@dataclass(frozen=True)
class FileSnapshot:
    canonical_path: str
    volume_serial: int
    file_id_128: bytes
    size_bytes: int
    modified_100ns: int
    attributes: int


@dataclass(frozen=True)
class RewardQuote:
    theoretical_units: int
    actual_units: int
    overflow_units: int
    enhanced_warning: bool


@dataclass(frozen=True)
class PreparedFeed:
    operation_id: str
    snapshot: FileSnapshot
    quote: RewardQuote
    activity_version: int
    animation_id: str
    cancellation_token: object


@dataclass(frozen=True)
class TrustedRecycleReceipt:
    operation_id: str
    item_count: int
    post_delete_hresult: int
    newly_created_item_id: str
    perform_hresult: int
    aborted: bool
    source_volume_serial: int
    source_file_id_128: bytes

    @property
    def trustworthy(self) -> bool:
        return (
            self.item_count == 1
            and self.post_delete_hresult >= 0
            and bool(self.newly_created_item_id)
            and self.perform_hresult >= 0
            and not self.aborted
        )


class FileIdentityPort(Protocol):
    def inspect(self, path: str) -> FileSnapshot: ...


class ConfirmationPort(Protocol):
    def show(self, prepared: PreparedFeed, current_hunger: int, callback: Callable[[bool], None]) -> None: ...
    def cancel(self) -> None: ...


class RecyclePort(Protocol):
    def submit(self, prepared: PreparedFeed, callback: Callable[[TrustedRecycleReceipt | Exception], None]) -> None: ...


class FeedStatePort(Protocol):
    def new_operation_id(self) -> str: ...
    def persist_prepared(self, prepared: PreparedFeed) -> None: ...
    def replace_prepared(self, prepared: PreparedFeed) -> None: ...
    def persist_cancelled(self, operation_id: str) -> None: ...
    def persist_recycle_confirmed(self, prepared: PreparedFeed, receipt: TrustedRecycleReceipt) -> None: ...
    def apply_reward_atomically(self, operation_id: str, units: int, utc_anchor: str) -> bool: ...
    def persist_completed(self, operation_id: str) -> None: ...
    def persist_needs_review(
        self, operation_id: str, reason: str, evidence: object | None = None
    ) -> None: ...


class SharedActivityPort(Protocol):
    def begin_feed_confirm(self) -> tuple[int, str, object]: ...
    def transition_feed_processing(self, version: int, token: object) -> bool: ...
    def transition_feed_animation(self, version: int, token: object) -> bool: ...
    def validate_completion(self, animation_id: str, version: int, token: object) -> bool: ...
    def recover(self, version: int, token: object) -> None: ...


def quote_reward(size_bytes: int, current_units: int) -> RewardQuote:
    if not 0 < size_bytes <= MAX_BYTES:
        raise ValueError("feed file size must be >0 and <=1 GiB")
    if not 0 <= current_units <= HUNGER_CAPACITY:
        raise ValueError("hunger units outside fixed-point range")
    theoretical = max(1, (size_bytes * 10_000) // MIB)
    remaining = HUNGER_CAPACITY - current_units
    actual = min(theoretical, remaining)
    overflow = theoretical - actual
    overflow_ratio = overflow / theoretical
    actual_ratio = actual / theoretical
    return RewardQuote(
        theoretical,
        actual,
        overflow,
        size_bytes > 100 * MIB or overflow_ratio > 0.5 or actual_ratio < 0.5,
    )


class FeedBusinessHandler:
    """Callback handler invoked by PR5's single serialized ActivityCoordinator."""

    def __init__(self, identity, confirmation, recycler, state, activity, hunger, clock):
        self.identity = identity
        self.confirmation = confirmation
        self.recycler = recycler
        self.state = state
        self.activity = activity
        self.hunger = hunger
        self.clock = clock
        self._active: PreparedFeed | None = None

    def handle_drop(self, event) -> bool:
        if self._active is not None or len(event.paths) != 1:
            return False
        snapshot = self.identity.inspect(event.paths[0])
        quote = quote_reward(snapshot.size_bytes, self.hunger.value_units)
        if quote.actual_units <= 0:
            return False
        version, animation_id, token = self.activity.begin_feed_confirm()
        operation_id = self.state.new_operation_id()
        prepared = PreparedFeed(operation_id, snapshot, quote, version, animation_id, token)
        self.state.persist_prepared(prepared)  # must flush before any file operation
        self._active = prepared
        self.confirmation.show(
            prepared, self.hunger.value_units,
            lambda accepted, expected=prepared: self._on_confirmation(expected, accepted),
        )
        return True

    def _on_confirmation(self, expected: PreparedFeed, accepted: bool) -> None:
        prepared = self._active
        if prepared is None or prepared != expected:
            return
        if not self.activity.validate_completion(
            prepared.animation_id, prepared.activity_version, prepared.cancellation_token
        ):
            self.state.persist_cancelled(prepared.operation_id)
            self.activity.recover(prepared.activity_version, prepared.cancellation_token)
            self._active = None
            return
        if not accepted:
            self.state.persist_cancelled(prepared.operation_id)
            self.activity.recover(prepared.activity_version, prepared.cancellation_token)
            self._active = None
            return
        try:
            latest = self.identity.inspect(prepared.snapshot.canonical_path)
        except Exception as error:
            self.state.persist_needs_review(
                prepared.operation_id, f"final_identity_error:{type(error).__name__}"
            )
            self.activity.recover(prepared.activity_version, prepared.cancellation_token)
            self._active = None
            return
        stable_identity = (
            latest.canonical_path == prepared.snapshot.canonical_path
            and latest.volume_serial == prepared.snapshot.volume_serial
            and latest.file_id_128 == prepared.snapshot.file_id_128
        )
        if not stable_identity:
            self.state.persist_needs_review(prepared.operation_id, "identity_changed_before_commit")
            self.activity.recover(prepared.activity_version, prepared.cancellation_token)
            self._active = None
            return
        if latest != prepared.snapshot:
            refreshed_quote = quote_reward(latest.size_bytes, self.hunger.value_units)
            refreshed = PreparedFeed(
                prepared.operation_id, latest, refreshed_quote, prepared.activity_version,
                prepared.animation_id, prepared.cancellation_token,
            )
            self.state.replace_prepared(refreshed)
            self._active = refreshed
            self.confirmation.show(
                refreshed, self.hunger.value_units,
                lambda accepted, expected=refreshed: self._on_confirmation(expected, accepted),
            )
            return
        current_quote = quote_reward(latest.size_bytes, self.hunger.value_units)
        if current_quote.actual_units <= 0:
            self.state.persist_cancelled(prepared.operation_id)
            self.activity.recover(prepared.activity_version, prepared.cancellation_token)
            self._active = None
            return
        if abs(current_quote.actual_units - prepared.quote.actual_units) > 100:
            refreshed = PreparedFeed(
                prepared.operation_id, latest, current_quote, prepared.activity_version,
                prepared.animation_id, prepared.cancellation_token,
            )
            self.state.replace_prepared(refreshed)
            self._active = refreshed
            self.confirmation.show(
                refreshed, self.hunger.value_units,
                lambda accepted, expected=refreshed: self._on_confirmation(expected, accepted),
            )
            return
        if current_quote != prepared.quote:
            prepared = PreparedFeed(
                prepared.operation_id, latest, current_quote, prepared.activity_version,
                prepared.animation_id, prepared.cancellation_token,
            )
            self.state.replace_prepared(prepared)
            self._active = prepared
        if not self.activity.transition_feed_processing(prepared.activity_version, prepared.cancellation_token):
            self.state.persist_cancelled(prepared.operation_id)
            self._active = None
            return
        try:
            self.recycler.submit(
                prepared, lambda result, expected=prepared: self._on_recycle(expected, result)
            )
        except Exception as error:
            self.state.persist_needs_review(
                prepared.operation_id, f"recycle_submit_error:{type(error).__name__}"
            )
            self.activity.recover(prepared.activity_version, prepared.cancellation_token)
            self._active = None

    def _on_recycle(self, expected: PreparedFeed, result) -> None:
        prepared = self._active
        if prepared is None or prepared != expected:
            return
        if not self.activity.validate_completion(
            prepared.animation_id, prepared.activity_version, prepared.cancellation_token
        ):
            self.state.persist_needs_review(
                prepared.operation_id, "stale_activity_after_recycle", result
            )
            self.activity.recover(prepared.activity_version, prepared.cancellation_token)
            self._active = None
            return
        if (
            not isinstance(result, TrustedRecycleReceipt)
            or not result.trustworthy
            or result.operation_id != prepared.operation_id
            or result.source_volume_serial != prepared.snapshot.volume_serial
            or result.source_file_id_128 != prepared.snapshot.file_id_128
        ):
            self.state.persist_needs_review(prepared.operation_id, "missing_trusted_recycle_receipt")
            self.activity.recover(prepared.activity_version, prepared.cancellation_token)
            self._active = None
            return
        self.state.persist_recycle_confirmed(prepared, result)
        applied = self.state.apply_reward_atomically(
            prepared.operation_id, prepared.quote.actual_units, self.clock.utc_iso()
        )
        if not applied:
            self.state.persist_needs_review(prepared.operation_id, "reward_atomic_commit_failed")
            self._active = None
            return
        animation_started = self.activity.transition_feed_animation(
            prepared.activity_version, prepared.cancellation_token
        )
        self.state.persist_completed(prepared.operation_id)
        if not animation_started:
            self.activity.recover(prepared.activity_version, prepared.cancellation_token)
        self._active = None

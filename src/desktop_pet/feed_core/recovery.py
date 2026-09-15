"""Replay-safe FEED recovery over the shared StateStore transaction API."""
from __future__ import annotations

from enum import Enum

from .business import TrustedRecycleReceipt


class RecoveryPhase(str, Enum):
    PREPARED = "Prepared"
    RECYCLE_CONFIRMED = "RecycleConfirmed"
    REWARD_APPLIED = "RewardApplied"
    COMPLETED = "Completed"
    NEEDS_REVIEW = "NeedsReview"


class FeedRecovery:
    """Resolve durable stages without ever issuing another recycle request.

    ``store`` is the shared foundation StateStore adapter.  Its
    ``apply_feed_reward_once`` operation must atomically update hunger, its UTC
    anchor and the bounded recent-operation-id ledger before returning true.
    """

    def __init__(self, store, utc_now):
        self.store = store
        self.utc_now = utc_now

    @property
    def feed_blocked(self) -> bool:
        return bool(tuple(self.store.incomplete_feed_transactions()))

    def recover_startup(self) -> None:
        for record in self.store.incomplete_feed_transactions():
            phase = self._phase(record)
            if phase is None:
                self._review(record.operation_id, "unknown_recovery_phase")
                continue
            if phase is RecoveryPhase.PREPARED:
                # A crash may have happened before, during or after Shell.  Never
                # infer success from source-path absence and never submit again.
                self._review(record.operation_id, "prepared_outcome_unknown")
            elif phase is RecoveryPhase.RECYCLE_CONFIRMED:
                if not self._receipt_matches(record):
                    self._review(record.operation_id, "recycle_receipt_untrusted")
                elif self._reward_once(record):
                    self.store.set_feed_phase(record.operation_id, RecoveryPhase.REWARD_APPLIED)
                    self.store.set_feed_phase(record.operation_id, RecoveryPhase.COMPLETED)
            elif phase is RecoveryPhase.REWARD_APPLIED:
                # Reward and its operation-id ledger were already committed in
                # one atomic StateStore write.  Only finish the journal stage.
                if self.store.has_feed_reward(record.operation_id):
                    self.store.set_feed_phase(record.operation_id, RecoveryPhase.COMPLETED)
                else:
                    self._review(record.operation_id, "reward_ledger_missing")

    def resolve(self, operation_id: str, *, claim_reward: bool) -> bool:
        records = {r.operation_id: r for r in self.store.incomplete_feed_transactions()}
        record = records.get(operation_id)
        if record is None or self._phase(record) is not RecoveryPhase.NEEDS_REVIEW:
            return False
        if not claim_reward:
            self.store.clear_feed_transaction(operation_id)
            return True
        if not self._receipt_matches(record):
            return False
        if not self._reward_once(record):
            return False
        self.store.set_feed_phase(operation_id, RecoveryPhase.REWARD_APPLIED)
        self.store.set_feed_phase(operation_id, RecoveryPhase.COMPLETED)
        return True

    def _reward_once(self, record) -> bool:
        if self.store.has_feed_reward(record.operation_id):
            return True
        applied = self.store.apply_feed_reward_once(
            record.operation_id, int(record.reward_units), self.utc_now()
        )
        if not applied:
            self._review(record.operation_id, "atomic_reward_commit_failed")
        return bool(applied)

    @staticmethod
    def _receipt_matches(record) -> bool:
        receipt = getattr(record, "receipt", None)
        if not (
            isinstance(receipt, TrustedRecycleReceipt)
            and receipt.trustworthy
            and receipt.operation_id == record.operation_id
        ):
            return False
        snapshot = getattr(record, "snapshot", None)
        return snapshot is not None and (
            receipt.source_volume_serial == snapshot.volume_serial
            and receipt.source_file_id_128 == snapshot.file_id_128
        )

    def _review(self, operation_id: str, reason: str) -> None:
        self.store.set_feed_phase(operation_id, RecoveryPhase.NEEDS_REVIEW, reason=reason)

    @staticmethod
    def _phase(record):
        try:
            return RecoveryPhase(record.phase)
        except (TypeError, ValueError):
            return None

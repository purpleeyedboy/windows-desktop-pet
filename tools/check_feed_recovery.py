"""Non-destructive FEED recovery contract check using memory-only fakes."""
from types import SimpleNamespace

from desktop_pet.feed_core.business import FileSnapshot, TrustedRecycleReceipt
from desktop_pet.feed_core.recovery import FeedRecovery, RecoveryPhase
from desktop_pet.feed_core.review import NeedsReviewController


class Store:
    def __init__(self, records):
        self.records = {record.operation_id: record for record in records}
        self.rewards = [r.operation_id for r in records if r.phase is RecoveryPhase.REWARD_APPLIED]

    def incomplete_feed_transactions(self):
        return tuple(r for r in self.records.values() if r.phase != RecoveryPhase.COMPLETED)

    def set_feed_phase(self, operation_id, phase, reason=None):
        record = self.records[operation_id]
        self.records[operation_id] = SimpleNamespace(**{
            **record.__dict__, "phase": phase, "reason": reason,
        })

    def apply_feed_reward_once(self, operation_id, units, utc_anchor):
        if operation_id in self.rewards:
            return False
        self.rewards.append(operation_id)
        return True

    def has_feed_reward(self, operation_id):
        return operation_id in self.rewards

    def clear_feed_transaction(self, operation_id):
        self.records.pop(operation_id, None)


def receipt(operation_id):
    return TrustedRecycleReceipt(operation_id, 1, 0, "recycle-item", 0, False, 7, b"x" * 16)


snapshot = FileSnapshot(r'C:\owned-test-fixture.txt', 7, b'x' * 16, 1024, 20, 0)
prepared = SimpleNamespace(operation_id="prepared", phase=RecoveryPhase.PREPARED,
                           receipt=None, reward_units=10)
confirmed = SimpleNamespace(operation_id="confirmed", phase=RecoveryPhase.RECYCLE_CONFIRMED,
                            receipt=receipt("confirmed"), reward_units=10, snapshot=snapshot)
applied = SimpleNamespace(operation_id="applied", phase=RecoveryPhase.REWARD_APPLIED,
                          receipt=receipt("applied"), reward_units=10)
store = Store([prepared, confirmed, applied])
recovery = FeedRecovery(store, lambda: "2026-09-07T00:00:00Z")
recovery.recover_startup()
assert store.records["prepared"].phase is RecoveryPhase.NEEDS_REVIEW
assert store.records["confirmed"].phase is RecoveryPhase.COMPLETED
assert store.records["applied"].phase is RecoveryPhase.COMPLETED
assert store.rewards == ["applied", "confirmed"]
assert recovery.feed_blocked is True

# Replaying startup and a delayed duplicate callback cannot award twice.
recovery.recover_startup()
assert store.rewards == ["applied", "confirmed"]

review = SimpleNamespace(operation_id="review", phase=RecoveryPhase.NEEDS_REVIEW,
                         receipt=receipt("review"), reward_units=3, snapshot=snapshot)
store.records["review"] = review
assert recovery.resolve("review", claim_reward=True) is True
assert recovery.resolve("review", claim_reward=True) is False
assert store.rewards.count("review") == 1

declined = SimpleNamespace(operation_id="declined", phase=RecoveryPhase.NEEDS_REVIEW,
                           receipt=None, reward_units=3)
store.records["declined"] = declined
assert recovery.resolve("declined", claim_reward=False) is True
assert "declined" not in store.records

opened = []; exited = []; refreshed = []
controller = NeedsReviewController(recovery, opened.append, lambda: exited.append(True),
                                   lambda records: refreshed.append(tuple(records)))
controller.refresh()
controller.open_recycle_bin()
controller.exit_application()
assert opened == ["shell:RecycleBinFolder"] and exited == [True]
assert all(not hasattr(record, "canonical_path") for record in refreshed[-1])
print("FEED_RECOVERY_CHECK_OK")

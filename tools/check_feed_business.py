"""Memory-only FEED ordering/idempotency check; performs no filesystem I/O."""
from types import SimpleNamespace

from desktop_pet.feed_core.business import (
    FeedBusinessHandler, FileSnapshot, TrustedRecycleReceipt,
)


class Confirmation:
    def show(self, prepared, current, callback): self.callback = callback
    def cancel(self): self.callback(False)


class Recycler:
    def submit(self, prepared, callback): self.prepared, self.callback = prepared, callback


class State:
    def __init__(self): self.events=[]; self.rewarded=set()
    def new_operation_id(self): return "op-1"
    def persist_prepared(self, value): self.events.append("Prepared")
    def persist_cancelled(self, value): self.events.append("Cancelled")
    def persist_recycle_confirmed(self, prepared, receipt): self.events.append("RecycleConfirmed")
    def apply_reward_atomically(self, operation_id, units, anchor):
        if operation_id in self.rewarded: return False
        self.rewarded.add(operation_id); self.events.append("AtomicReward"); return True
    def persist_reward_applied(self, operation_id): self.events.append("RewardApplied")
    def persist_completed(self, operation_id): self.events.append("Completed")
    def persist_needs_review(self, operation_id, reason, evidence=None): self.events.append("NeedsReview")


class Activity:
    def begin_feed_confirm(self): return 1, "feed-animation", object()
    def validate_completion(self, *args): return True
    def transition_feed_processing(self, *args): return True
    def transition_feed_animation(self, *args): return True
    def recover(self, *args): pass


snapshot = FileSnapshot("C:\\temporary-owned.txt", 7, b"x" * 16, 100, 20, 0)
identity = SimpleNamespace(inspect=lambda path: snapshot)
hunger = SimpleNamespace(value_units=0)
clock = SimpleNamespace(utc_iso=lambda: "2026-09-07T00:00:00Z")

# Cancelled confirmation never creates a transaction.
confirmation=Confirmation(); recycler=Recycler(); state=State()
handler=FeedBusinessHandler(identity, confirmation, recycler, state, Activity(), hunger, clock)
assert handler.handle_drop(SimpleNamespace(paths=(snapshot.canonical_path,)))
assert state.events == []
confirmation.callback(False)
assert state.events == []

# Prepared is flushed only after final confirmation; duplicate COM callbacks
# cannot apply a second reward because the handler has already detached it.
confirmation=Confirmation(); recycler=Recycler(); state=State()
handler=FeedBusinessHandler(identity, confirmation, recycler, state, Activity(), hunger, clock)
handler.handle_drop(SimpleNamespace(paths=(snapshot.canonical_path,)))
confirmation.callback(True)
assert state.events == ["Prepared"]
receipt = TrustedRecycleReceipt("op-1", 1, 0, "proof", 0, False, 7, b"x" * 16)
recycler.callback(receipt); recycler.callback(receipt)
assert state.events == ["Prepared", "RecycleConfirmed", "AtomicReward", "RewardApplied", "Completed"]
assert state.rewarded == {"op-1"}
print("FEED_BUSINESS_CHECK_OK")

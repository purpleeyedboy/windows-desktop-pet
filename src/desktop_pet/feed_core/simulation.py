"""Safe candidate demonstration: simulated recycle only, never deletes or moves a file."""
from __future__ import annotations

import tempfile
from pathlib import Path

from .adapters import IdempotentRewardFake
from .coordinator import FeedCoordinator
from .journal import TransactionJournal
from .model import FeedState, RecycleReceipt
from .validation import FileValidator


class MemoryRecycleSimulator:
    def __init__(self):
        self._receipts = {}
        self.operation_count = 0

    def recycle(self, path, transaction_id, *, expected_identity, timeout_seconds, cancel_event):
        del timeout_seconds
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("simulation cancelled")
        if transaction_id not in self._receipts:
            if not Path(path).is_file():
                raise OSError("simulation source missing")
            self.operation_count += 1
            self._receipts[transaction_id] = RecycleReceipt.create(
                transaction_id,
                expected_identity,
                evidence="simulation:source-preserved:no-real-operation",
            )
        return self._receipts[transaction_id]


class _ConfirmSimulation:
    def confirm(self, target, consequence):
        del target, consequence
        return True


class _AnimationSimulation:
    def __init__(self):
        self.calls = []

    def play_eating(self, transaction_id):
        self.calls.append(transaction_id)


def run_safe_demo() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="desktop-pet-feed-simulation-") as owned:
        root = Path(owned)
        source = root / "模拟文件.txt"
        source.write_text("simulation only", encoding="utf-8")
        simulator = MemoryRecycleSimulator()
        reward = IdempotentRewardFake(root / "reward-ledger.json")
        animation = _AnimationSimulation()
        coordinator = FeedCoordinator(
            TransactionJournal(root / "journal"),
            FileValidator(
                protected_roots=[],
                application_path=root / "candidate.exe",
                repository_root=root / "not-the-source",
            ),
            _ConfirmSimulation(),
            simulator,
            reward,
            animation,
        )
        result = coordinator.handle_explicit_drop(source)
        return {
            "mode": "SIMULATION",
            "state": result.state.value,
            "simulator_calls": simulator.operation_count,
            "source_still_exists": source.exists(),
            "reward_commits": len(reward.commits),
            "animation_calls": len(animation.calls),
        }

from __future__ import annotations
import json, os
from pathlib import Path
class IdempotentRewardFake:
    """Durable fake demonstrating the idempotency-key contract for FEED-WIRING."""
    def __init__(self, ledger_path=None):
        self.ledger_path=Path(ledger_path) if ledger_path else None
        self.commits=[]
        if self.ledger_path and self.ledger_path.exists(): self.commits=list(json.loads(self.ledger_path.read_text(encoding='utf-8')))
    def commit_once(self, transaction_id):
        if transaction_id not in self.commits:
            self.commits.append(transaction_id)
            if self.ledger_path:
                self.ledger_path.parent.mkdir(parents=True,exist_ok=True)
                temp=self.ledger_path.with_suffix('.tmp'); temp.write_text(json.dumps(self.commits),encoding='utf-8'); os.replace(temp,self.ledger_path)
        return f'fake-reward:{transaction_id}'
class DropEventAdapter:
    """Consumes a host-provided standard Drop event; never registers/owns a DropTarget."""
    def __init__(self, coordinator): self.coordinator=coordinator
    def on_drop(self, paths): return [self.coordinator.handle_explicit_drop(p) for p in paths]

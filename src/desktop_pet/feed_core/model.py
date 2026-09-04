from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class FeedState(str, Enum):
    PENDING_CONFIRMATION='PendingConfirmation'
    CANCELLED='Cancelled'
    EXECUTING='Executing'
    RECYCLED='Recycled'
    FAILED='Failed'
    REWARD_COMMITTED='RewardCommitted'
    COMPLETED='Completed'
    NEEDS_REVIEW='NeedsReview'

@dataclass(frozen=True)
class FeedTransaction:
    id: str
    state: FeedState
    target_name: str
    target_fingerprint: str
    recycle_credential: str | None = None
    reward_credential: str | None = None
    animation_interrupted: bool = False
    failure_code: str | None = None

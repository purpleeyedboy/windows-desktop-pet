from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib


class FeedState(str, Enum):
    PENDING_CONFIRMATION = "PendingConfirmation"
    CANCELLED = "Cancelled"
    EXECUTING = "Executing"
    RECYCLED = "Recycled"
    FAILED = "Failed"
    REWARD_COMMITTED = "RewardCommitted"
    COMPLETED = "Completed"
    NEEDS_REVIEW = "NeedsReview"


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    size_bytes: int
    modified_ns: int
    changed_ns: int
    fingerprint: str


@dataclass(frozen=True)
class ConfirmationTarget:
    name: str
    size_bytes: int
    modified_ns: int

    @property
    def summary(self) -> str:
        return f"文件名：{self.name}\n大小：{self.size_bytes} 字节\n修改时间标识：{self.modified_ns}"


@dataclass(frozen=True)
class RecycleReceipt:
    credential: str
    verified: bool
    evidence: str
    transaction_id: str
    identity_fingerprint: str

    @classmethod
    def create(cls, transaction_id: str, identity: FileIdentity, *, evidence: str):
        proof = hashlib.sha256(
            f"{transaction_id}\0{identity.fingerprint}\0{evidence}".encode("utf-8")
        ).hexdigest()
        return cls(
            credential=f"recycle-v1:{proof}",
            verified=True,
            evidence=evidence,
            transaction_id=transaction_id,
            identity_fingerprint=identity.fingerprint,
        )

    @staticmethod
    def verify_credential(credential: str, transaction_id: str, fingerprint: str, evidence: str) -> bool:
        proof = hashlib.sha256(
            f"{transaction_id}\0{fingerprint}\0{evidence}".encode("utf-8")
        ).hexdigest()
        return credential == f"recycle-v1:{proof}"

    def verifies(self, transaction_id: str, identity: FileIdentity) -> bool:
        return (
            self.verified
            and self.transaction_id == transaction_id
            and self.identity_fingerprint == identity.fingerprint
            and self.verify_credential(
                self.credential, transaction_id, identity.fingerprint, self.evidence
            )
        )


@dataclass(frozen=True)
class FeedTransaction:
    id: str
    state: FeedState
    target_name: str
    target_fingerprint: str
    recycle_credential: str | None = None
    recycle_evidence: str | None = None
    reward_credential: str | None = None
    animation_interrupted: bool = False
    failure_code: str | None = None

from __future__ import annotations

import threading

from .model import FeedState, RecycleReceipt


class FeedCoordinator:
    def __init__(
        self,
        journal,
        validator,
        confirmer,
        recycler,
        reward,
        animator,
        *,
        operation_timeout_seconds: float = 30.0,
    ):
        self.journal = journal
        self.validator = validator
        self.confirmer = confirmer
        self.recycler = recycler
        self.reward = reward
        self.animator = animator
        self.operation_timeout_seconds = operation_timeout_seconds
        self._active_fingerprints: set[str] = set()
        self._active_lock = threading.Lock()

    def handle_explicit_drop(self, path, *, cancel_event=None):
        valid = self.validator.validate(path, explicitly_dropped=True)
        transaction = self.journal.create(valid.path)
        with self._active_lock:
            if valid.fingerprint in self._active_fingerprints:
                return self.journal.transition(
                    transaction.id, FeedState.FAILED, failure_code="duplicate_request"
                )
            self._active_fingerprints.add(valid.fingerprint)
        try:
            consequence = "确认后将此文件移入回收站；取消或关闭不会执行。"
            answer = self.confirmer.confirm(valid.confirmation, consequence)
            if answer is not True:
                return self.journal.transition(transaction.id, FeedState.CANCELLED)
            try:
                current = self.validator.validate(path, explicitly_dropped=True)
            except Exception as error:
                return self.journal.transition(
                    transaction.id, FeedState.FAILED, failure_code=type(error).__name__
                )
            if current.identity != valid.identity:
                return self.journal.transition(
                    transaction.id,
                    FeedState.FAILED,
                    failure_code="target_changed_after_confirmation",
                )
            transaction = self.journal.transition(transaction.id, FeedState.EXECUTING)
            try:
                receipt = self.recycler.recycle(
                    valid.path,
                    transaction.id,
                    expected_identity=valid.identity,
                    timeout_seconds=self.operation_timeout_seconds,
                    cancel_event=cancel_event,
                )
            except (TimeoutError, InterruptedError) as error:
                return self.journal.transition(
                    transaction.id, FeedState.NEEDS_REVIEW, failure_code=type(error).__name__
                )
            except Exception as error:
                return self.journal.transition(
                    transaction.id, FeedState.FAILED, failure_code=type(error).__name__
                )
            if (
                not isinstance(receipt, RecycleReceipt)
                or not receipt.verifies(transaction.id, valid.identity)
            ):
                return self.journal.transition(
                    transaction.id,
                    FeedState.NEEDS_REVIEW,
                    failure_code="unverified_recycle_outcome",
                )
            transaction = self.journal.transition(
                transaction.id,
                FeedState.RECYCLED,
                recycle_credential=receipt.credential,
                recycle_evidence=receipt.evidence,
            )
            return self._finish(transaction)
        finally:
            with self._active_lock:
                self._active_fingerprints.discard(valid.fingerprint)

    def _finish(self, transaction):
        credential = self.reward.commit_once(transaction.id)
        transaction = self.journal.transition(
            transaction.id, FeedState.REWARD_COMMITTED, reward_credential=credential
        )
        interrupted = False
        try:
            self.animator.play_eating(transaction.id)
        except Exception:
            interrupted = True
        return self.journal.transition(
            transaction.id, FeedState.COMPLETED, animation_interrupted=interrupted
        )

    def recover(self):
        results = []
        for transaction in self.journal.all():
            if transaction.state is FeedState.PENDING_CONFIRMATION:
                transaction = self.journal.transition(
                    transaction.id, FeedState.CANCELLED, failure_code="confirmation_interrupted"
                )
            elif transaction.state is FeedState.EXECUTING:
                transaction = self.journal.transition(
                    transaction.id,
                    FeedState.NEEDS_REVIEW,
                    failure_code="uncertain_recycle_outcome",
                )
            elif transaction.state is FeedState.RECYCLED:
                # A persisted receipt is audit evidence, not OS-authenticated proof.
                # Never commit a reward after process restart.
                transaction = self.journal.transition(
                    transaction.id,
                    FeedState.NEEDS_REVIEW,
                    failure_code="recycle_receipt_requires_live_verification",
                )
            elif transaction.state is FeedState.REWARD_COMMITTED:
                if not transaction.reward_credential:
                    transaction = self.journal.transition(
                        transaction.id,
                        FeedState.NEEDS_REVIEW,
                        failure_code="uncertain_reward_outcome",
                    )
                else:
                    transaction = self.journal.transition(
                        transaction.id, FeedState.COMPLETED, animation_interrupted=True
                    )
            results.append(transaction)
        return results

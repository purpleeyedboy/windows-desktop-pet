from __future__ import annotations
from .model import FeedState
class FeedCoordinator:
    def __init__(self,journal,validator,confirmer,recycler,reward,animator):
        self.journal,self.validator,self.confirmer=journal,validator,confirmer
        self.recycler,self.reward,self.animator=recycler,reward,animator
    def handle_explicit_drop(self,path):
        valid=self.validator.validate(path,explicitly_dropped=True)
        tx=self.journal.create(valid.path)
        answer=self.confirmer.confirm(valid.name,f'将“{valid.name}”移入回收站（可从回收站恢复）。')
        if answer is not True: return self.journal.transition(tx.id,FeedState.CANCELLED)
        try:
            current=self.validator.validate(path,explicitly_dropped=True)
        except Exception as error:
            return self.journal.transition(tx.id,FeedState.FAILED,failure_code=type(error).__name__)
        if current.fingerprint != valid.fingerprint:
            return self.journal.transition(tx.id,FeedState.FAILED,failure_code='target_changed_after_confirmation')
        tx=self.journal.transition(tx.id,FeedState.EXECUTING)
        try: success=self.recycler.recycle(valid.path,tx.id)
        except Exception as error:
            return self.journal.transition(tx.id,FeedState.FAILED,failure_code=type(error).__name__)
        if not success: return self.journal.transition(tx.id,FeedState.FAILED,failure_code='operation_not_completed')
        tx=self.journal.transition(tx.id,FeedState.RECYCLED,recycle_credential=f'ifileoperation:{tx.id}')
        return self._finish(tx)
    def _finish(self,tx):
        credential=self.reward.commit_once(tx.id)
        tx=self.journal.transition(tx.id,FeedState.REWARD_COMMITTED,reward_credential=credential)
        interrupted=False
        try: self.animator.play_eating(tx.id)
        except Exception: interrupted=True
        return self.journal.transition(tx.id,FeedState.COMPLETED,animation_interrupted=interrupted)
    def recover(self):
        results=[]
        for tx in self.journal.all():
            if tx.state is FeedState.PENDING_CONFIRMATION:
                tx=self.journal.transition(tx.id,FeedState.CANCELLED,failure_code='confirmation_interrupted')
            elif tx.state is FeedState.EXECUTING:
                tx=self.journal.transition(tx.id,FeedState.NEEDS_REVIEW,failure_code='uncertain_recycle_outcome')
            elif tx.state is FeedState.RECYCLED:
                if not tx.recycle_credential: tx=self.journal.transition(tx.id,FeedState.NEEDS_REVIEW,failure_code='missing_recycle_proof')
                else: tx=self._finish(tx)
            elif tx.state is FeedState.REWARD_COMMITTED:
                if not tx.reward_credential: tx=self.journal.transition(tx.id,FeedState.NEEDS_REVIEW,failure_code='uncertain_reward_outcome')
                else: tx=self.journal.transition(tx.id,FeedState.COMPLETED,animation_interrupted=True)
            results.append(tx)
        return results

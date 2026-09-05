import json
import threading
from pathlib import Path

import pytest

from desktop_pet.feed_core.coordinator import FeedCoordinator
from desktop_pet.feed_core.journal import TransactionJournal
from desktop_pet.feed_core.model import FeedState, RecycleReceipt
from desktop_pet.feed_core.simulation import MemoryRecycleSimulator, run_safe_demo
from desktop_pet.feed_core.validation import FileValidator


class Confirm:
    def __init__(self, answer=True, mutate=None): self.answer=answer; self.mutate=mutate; self.views=[]
    def confirm(self, target, consequence):
        self.views.append((target, consequence))
        if self.mutate: self.mutate()
        return self.answer

class Reward:
    def __init__(self): self.calls=[]
    def commit_once(self, key): self.calls.append(key); return f'reward:{key}'

class Animation:
    def __init__(self): self.calls=[]
    def play_eating(self, key): self.calls.append(key)

class Recycler:
    def __init__(self, outcome): self.outcome=outcome; self.calls=[]
    def recycle(self, path, transaction_id, *, expected_identity, timeout_seconds, cancel_event):
        self.calls.append((path,transaction_id,expected_identity,timeout_seconds,cancel_event))
        if isinstance(self.outcome, BaseException): raise self.outcome
        if self.outcome == 'verified':
            return RecycleReceipt.create(transaction_id, expected_identity, evidence='mock-confirmed')
        return self.outcome


def make_core(tmp_path, recycler, confirmer=None):
    target=tmp_path/'private-parent-name'/'meal.txt'; target.parent.mkdir(parents=True); target.write_text('abc')
    journal=TransactionJournal(tmp_path/'journal'); reward=Reward(); animation=Animation()
    validator=FileValidator(protected_roots=[],application_path=tmp_path/'app.exe',repository_root=tmp_path/'repo')
    core=FeedCoordinator(journal,validator,confirmer or Confirm(),recycler,reward,animation,operation_timeout_seconds=.05)
    return target,journal,reward,animation,core


def receipt(tx, identity):
    return RecycleReceipt.create(tx, identity, evidence='mock-confirmed')


def test_confirmation_identifies_file_without_parent_path(tmp_path):
    recycler=Recycler('verified'); target,_,_,_,core=make_core(tmp_path,recycler)
    result=core.handle_explicit_drop(target)
    shown=core.confirmer.views[0][0]
    assert shown.name=='meal.txt' and shown.size_bytes==3 and shown.modified_ns>0
    assert str(target.parent) not in shown.summary
    assert '移入回收站' in core.confirmer.views[0][1]
    assert result.state is FeedState.COMPLETED


def test_unverified_or_missing_receipt_never_rewards(tmp_path):
    for value in (True, False, None, RecycleReceipt('weak',False,'request-only','wrong','wrong')):
        recycler=Recycler(value); target,journal,reward,animation,core=make_core(tmp_path/str(value),recycler)
        result=core.handle_explicit_drop(target)
        assert result.state is FeedState.NEEDS_REVIEW
        assert reward.calls==[] and animation.calls==[]


def test_timeout_and_cancel_are_reviewable_and_never_reward(tmp_path):
    for error in (TimeoutError('deadline'), InterruptedError('cancelled')):
        recycler=Recycler(error); target,journal,reward,animation,core=make_core(tmp_path/type(error).__name__,recycler)
        result=core.handle_explicit_drop(target,cancel_event=threading.Event())
        assert result.state is FeedState.NEEDS_REVIEW
        assert reward.calls==[] and animation.calls==[]


def test_identity_is_checked_after_confirmation_and_passed_to_adapter(tmp_path):
    recycler=Recycler('verified'); target,journal,reward,animation,core=make_core(tmp_path,recycler)
    original=target.stat()
    confirmer=Confirm(mutate=lambda: (target.unlink(),target.write_text('xyz')))
    core.confirmer=confirmer
    result=core.handle_explicit_drop(target)
    assert result.state is FeedState.FAILED and recycler.calls==[] and reward.calls==[]


def test_simulated_demo_imports_core_and_never_removes_its_temp_file():
    report=run_safe_demo()
    assert report['mode']=='SIMULATION' and report['state']=='Completed'
    assert report['simulator_calls']==1 and report['source_still_exists'] is True
    assert report['reward_commits']==1


def test_simulator_rejects_duplicate_transaction_request(tmp_path):
    target=tmp_path/'owned.txt'; target.write_text('x')
    simulator=MemoryRecycleSimulator()
    identity=FileValidator(protected_roots=[],application_path=tmp_path/'a',repository_root=tmp_path/'repo').validate(target,explicitly_dropped=True).identity
    first=simulator.recycle(target,'same',expected_identity=identity,timeout_seconds=1,cancel_event=None)
    second=simulator.recycle(target,'same',expected_identity=identity,timeout_seconds=1,cancel_event=None)
    assert first.verified and second.verified and simulator.operation_count==1 and target.exists()

def test_concurrent_duplicate_drop_is_rejected_without_second_operation(tmp_path):
    entered=threading.Event(); release=threading.Event()
    class BlockingRecycler(Recycler):
        def recycle(self, path, transaction_id, **kwargs):
            self.calls.append((path,transaction_id,kwargs)); entered.set(); release.wait(timeout=1)
            return receipt(transaction_id, kwargs['expected_identity'])
    recycler=BlockingRecycler(None); target,journal,reward,animation,core=make_core(tmp_path,recycler)
    results=[]
    worker=threading.Thread(target=lambda: results.append(core.handle_explicit_drop(target)))
    worker.start(); assert entered.wait(timeout=1)
    duplicate=core.handle_explicit_drop(target)
    release.set(); worker.join(timeout=1)
    assert duplicate.state is FeedState.FAILED and duplicate.failure_code=='duplicate_request'
    assert len(recycler.calls)==1 and len(reward.calls)==1

def test_recovery_rejects_forged_recycle_credential_without_reward(tmp_path):
    recycler=Recycler('verified'); target,journal,reward,animation,core=make_core(tmp_path,recycler)
    transaction=journal.create(target)
    journal.transition(transaction.id,FeedState.RECYCLED,recycle_credential='forged',recycle_evidence='claimed')
    recovered=core.recover()[0]
    assert recovered.state is FeedState.NEEDS_REVIEW and reward.calls==[]

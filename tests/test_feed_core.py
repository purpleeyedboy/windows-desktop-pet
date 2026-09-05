import json
from pathlib import Path

import pytest

from desktop_pet.feed_core.adapters import DropEventAdapter, IdempotentRewardFake
from desktop_pet.feed_core.coordinator import FeedCoordinator
from desktop_pet.feed_core.journal import TransactionJournal
from desktop_pet.feed_core.model import FeedState, RecycleReceipt
from desktop_pet.feed_core.validation import FileValidator, Rejection


class Recycler:
    def __init__(self, result=True, error=None): self.calls=[]; self.result=result; self.error=error
    def recycle(self, path, transaction_id, **kwargs):
        self.calls.append((path, transaction_id))
        if self.error: raise self.error
        if self.result is True:
            return RecycleReceipt.create(transaction_id, kwargs['expected_identity'], evidence='mock verified')
        return self.result

class Confirmer:
    def __init__(self, answer): self.answer=answer; self.prompts=[]
    def confirm(self, display_name, consequence):
        self.prompts.append((display_name, consequence)); return self.answer

class Animator:
    def __init__(self, error=None): self.calls=[]; self.error=error
    def play_eating(self, transaction_id):
        self.calls.append(transaction_id)
        if self.error: raise self.error


def setup(tmp_path, answer=True, recycle=True, recycle_error=None, animation_error=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    dropped=tmp_path/'drop.txt'; dropped.write_text('owned by test')
    journal=TransactionJournal(tmp_path/'state')
    reward=IdempotentRewardFake(tmp_path/'reward-ledger.json')
    recycler=Recycler(recycle, recycle_error)
    confirm=Confirmer(answer)
    animator=Animator(animation_error)
    validator=FileValidator(protected_roots=[], application_path=tmp_path/'app.exe', repository_root=tmp_path/'repo')
    core=FeedCoordinator(journal, validator, confirm, recycler, reward, animator)
    return dropped, journal, reward, recycler, confirm, animator, core


def test_states_cover_contract():
    assert {s.value for s in FeedState} == {'PendingConfirmation','Cancelled','Executing','Recycled','Failed','RewardCommitted','Completed','NeedsReview'}


def test_validator_accepts_only_explicit_regular_local_file(tmp_path):
    f=tmp_path/'ok.txt'; f.write_text('x')
    validator=FileValidator(protected_roots=[], application_path=tmp_path/'app.exe', repository_root=tmp_path/'repo')
    assert validator.validate(f, explicitly_dropped=True).path == f.resolve()
    with pytest.raises(Rejection): validator.validate(f, explicitly_dropped=False)
    with pytest.raises(Rejection): validator.validate(tmp_path, explicitly_dropped=True)
    with pytest.raises(Rejection): validator.validate(Path(f.anchor), explicitly_dropped=True)
    link=tmp_path/'link'; link.symlink_to(f)
    with pytest.raises(Rejection): validator.validate(link, explicitly_dropped=True)


def test_validator_rejects_app_repository_assets_and_protected(tmp_path):
    app=tmp_path/'app.exe'; app.write_text('x')
    repo=tmp_path/'repo'; (repo/'assets').mkdir(parents=True); target=repo/'assets'/'cat.png'; target.write_text('x')
    protected=tmp_path/'Windows'; protected.mkdir(); sysfile=protected/'system.ini'; sysfile.write_text('x')
    v=FileValidator(protected_roots=[protected], application_path=app, repository_root=repo)
    for item in (app,target,sysfile):
        with pytest.raises(Rejection): v.validate(item, explicitly_dropped=True)


def test_cancel_and_confirmation_close_never_recycle(tmp_path):
    for answer in (False, None):
        dropped,journal,reward,recycler,confirm,animator,core=setup(tmp_path/str(answer), answer=answer)
        result=core.handle_explicit_drop(dropped)
        assert result.state is FeedState.CANCELLED
        assert recycler.calls == [] and reward.commits == [] and animator.calls == []
        assert '移入回收站' in confirm.prompts[0][1]


def test_success_orders_recycle_reward_animation_and_redacts_journal(tmp_path):
    dropped,journal,reward,recycler,confirm,animator,core=setup(tmp_path)
    result=core.handle_explicit_drop(dropped)
    assert result.state is FeedState.COMPLETED
    assert len(recycler.calls)==len(reward.commits)==len(animator.calls)==1
    raw=next((tmp_path/'state').glob('*.json')).read_text()
    assert str(dropped) not in raw and 'owned by test' not in raw
    payload=json.loads(raw); assert payload['schema_version']==2 and payload['target']['name']=='drop.txt'

@pytest.mark.parametrize('recycle,error',[ (False,None), (True,OSError('occupied')), (True,RuntimeError('partial failure'))])
def test_recycle_failures_never_reward_or_animate(tmp_path,recycle,error):
    dropped,journal,reward,recycler,confirm,animator,core=setup(tmp_path,recycle=recycle,recycle_error=error)
    result=core.handle_explicit_drop(dropped)
    assert result.state in {FeedState.FAILED, FeedState.NEEDS_REVIEW}
    assert reward.commits == [] and animator.calls == []


def test_animation_interruption_does_not_repeat_recycle_or_reward(tmp_path):
    dropped,journal,reward,recycler,confirm,animator,core=setup(tmp_path,animation_error=RuntimeError('closed'))
    result=core.handle_explicit_drop(dropped)
    assert result.state is FeedState.COMPLETED and result.animation_interrupted
    assert len(recycler.calls)==len(reward.commits)==1
    core.recover(); assert len(recycler.calls)==len(reward.commits)==1


def test_crash_recovery_marks_uncertain_executing_needs_review_without_retry(tmp_path):
    dropped,journal,reward,recycler,confirm,animator,core=setup(tmp_path)
    tx=journal.create(dropped); journal.transition(tx.id, FeedState.EXECUTING)
    recovered=core.recover()
    assert recovered[0].state is FeedState.NEEDS_REVIEW
    assert recycler.calls == [] and reward.commits == []
    assert core.recover()[0].state is FeedState.NEEDS_REVIEW


def test_recovery_does_not_trust_persisted_recycle_receipt_for_reward(tmp_path):
    dropped,journal,reward,recycler,confirm,animator,core=setup(tmp_path)
    tx=journal.create(dropped)
    identity=core.validator.validate(dropped,explicitly_dropped=True).identity
    proof=RecycleReceipt.create(tx.id,identity,evidence='mock recovered')
    journal.transition(tx.id, FeedState.RECYCLED, recycle_credential=proof.credential, recycle_evidence=proof.evidence)
    assert core.recover()[0].state is FeedState.NEEDS_REVIEW
    assert reward.commits == [] and recycler.calls == []


def test_drop_adapter_is_non_owning_and_forwards_explicit_event(tmp_path):
    dropped,*_,core=setup(tmp_path)
    adapter=DropEventAdapter(core)
    assert not hasattr(adapter,'register_drop_target')
    assert adapter.on_drop([dropped])[0].state is FeedState.COMPLETED

def test_file_changed_during_confirmation_is_not_recycled(tmp_path):
    dropped,journal,reward,recycler,confirm,animator,core=setup(tmp_path)
    def mutate(name, consequence):
        dropped.write_text('changed after initial validation')
        return True
    confirm.confirm=mutate
    result=core.handle_explicit_drop(dropped)
    assert result.state is FeedState.FAILED
    assert recycler.calls == [] and reward.commits == []


def test_restart_cancels_unconfirmed_transaction_without_operation(tmp_path):
    dropped,journal,reward,recycler,confirm,animator,core=setup(tmp_path)
    tx=journal.create(dropped)
    result=core.recover()[0]
    assert result.id==tx.id and result.state is FeedState.CANCELLED
    assert recycler.calls == [] and reward.commits == []


def test_reward_fake_is_idempotent_across_restart(tmp_path):
    ledger=tmp_path/'rewards.json'
    first=IdempotentRewardFake(ledger); first.commit_once('tx-1')
    restarted=IdempotentRewardFake(ledger); restarted.commit_once('tx-1')
    assert restarted.commits == ['tx-1']

def test_recovery_isolates_damaged_and_unsupported_journals(tmp_path):
    dropped,journal,reward,recycler,confirm,animator,core=setup(tmp_path)
    (journal.root/'broken.json').write_text('{broken',encoding='utf-8')
    (journal.root/'future.json').write_text('{"schema_version":99}',encoding='utf-8')
    recovered=core.recover()
    reviews=[tx for tx in recovered if tx.state is FeedState.NEEDS_REVIEW]
    assert len(reviews)==2
    assert (journal.root/'broken.json').exists() and (journal.root/'future.json').exists()

from pathlib import Path
from desktop_pet.feed_core.wiring import FeedRuntime, HungerMeter
from desktop_pet.feed_core.model import FeedState, RecycleReceipt

class Pet:
    def __init__(self): self.messages=[]; self.actions=[]
    def head_feed_contains(self,x,y): return y < 100
    def show_feed_feedback(self,text): self.messages.append(text)
    def play_feed_success(self): self.actions.append('eat')
class Confirm:
    def __init__(self,answer=True): self.answer=answer
    def confirm(self,target,consequence): return self.answer
class Recycler:
    def recycle(self,path,tx,**kw): return RecycleReceipt.create(tx,kw['expected_identity'],evidence='mock')
class Journal:
    pass

def test_hunger_increases_only_for_success_and_extreme_does_not_disable():
    meter=HungerMeter(value=0, reward=20)
    assert meter.can_feed and meter.can_exit
    meter.commit_once('x'); meter.commit_once('x')
    assert meter.value==20

def test_runtime_drag_copy_only_and_visible_states(tmp_path):
    pet=Pet(); meter=HungerMeter(10,20)
    runtime=FeedRuntime.create_for_test(pet,tmp_path,Confirm(),Recycler(),meter)
    f=tmp_path/'meal.txt'; f.write_text('x')
    assert runtime.drag_enter([f],10,10)=='copy'
    assert pet.messages[-1]=='期待投喂：松开后将先确认'
    result=runtime.drop([f],10,10)
    assert result.state is FeedState.COMPLETED and meter.value==30
    assert pet.actions==['eat'] and '投喂成功' in pet.messages[-1]

def test_runtime_rejects_multiple_or_outside_and_cancel_no_reward(tmp_path):
    pet=Pet(); meter=HungerMeter(0,20)
    runtime=FeedRuntime.create_for_test(pet,tmp_path,Confirm(False),Recycler(),meter)
    f=tmp_path/'meal.txt'; f.write_text('x')
    assert runtime.drag_enter([f,f],10,10)=='none'
    assert runtime.drag_enter([f],10,200)=='none'
    result=runtime.drop([f],10,10)
    assert result.state is FeedState.CANCELLED and meter.value==0

def test_validator_rejects_over_one_gib_and_cloud_placeholder(tmp_path,monkeypatch):
    from desktop_pet.feed_core.validation import FileValidator, Rejection
    import pytest
    f=tmp_path/'large.bin'; f.write_text('x')
    v=FileValidator(protected_roots=[],application_path=tmp_path/'a',repository_root=tmp_path/'repo')
    real=f.lstat()
    class Info:
        st_mode=real.st_mode; st_dev=real.st_dev; st_ino=real.st_ino; st_size=1024**3+1; st_mtime_ns=real.st_mtime_ns; st_ctime_ns=real.st_ctime_ns; st_file_attributes=0
    monkeypatch.setattr(Path,'lstat',lambda self:Info())
    with pytest.raises(Rejection,match='1 GiB'):v.validate(f,explicitly_dropped=True)

def test_head_feed_zone_and_feedback_methods_exist():
    from desktop_pet.window import PetWindow
    assert callable(PetWindow.head_feed_contains)
    assert callable(PetWindow.show_feed_feedback)
    assert callable(PetWindow.play_feed_success)

def test_windows_runtime_recovers_before_accepting_new_feed(tmp_path):
    from desktop_pet.feed_core.journal import TransactionJournal
    from desktop_pet.feed_core.model import FeedState
    pet=Pet(); source=tmp_path/'source.txt'; source.write_text('x')
    journal=TransactionJournal(tmp_path/'transactions'); tx=journal.create(source); journal.transition(tx.id,FeedState.EXECUTING)
    runtime=FeedRuntime.create_windows(object(),pet,tmp_path)
    assert runtime.coordinator.journal.load(tx.id).state is FeedState.NEEDS_REVIEW
    assert runtime.coordinator.recycler._needs_review is True
    assert '人工复核' in pet.messages[-1]
    assert runtime.drag_enter([source],0,0)=='none'

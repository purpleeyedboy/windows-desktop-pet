from __future__ import annotations
import json
import os
from pathlib import Path
from tkinter import messagebox

from .coordinator import FeedCoordinator
from .journal import TransactionJournal
from .model import FeedState
from .validation import FileValidator, Rejection
from .windows_recycle import IFileOperationRecycler

class HungerMeter:
    def __init__(self,value=0,reward=20,ledger_path=None):
        self.value=max(0,min(100,int(value))); self.reward=int(reward); self.ledger_path=Path(ledger_path) if ledger_path else None; self._committed=set()
        if self.ledger_path and self.ledger_path.exists():
            data=json.loads(self.ledger_path.read_text(encoding='utf-8')); self.value=int(data['value']); self._committed=set(data['transactions'])
    @property
    def can_feed(self): return True
    @property
    def can_exit(self): return True
    def commit_once(self,transaction_id):
        if transaction_id not in self._committed:
            self._committed.add(transaction_id); self.value=min(100,self.value+self.reward); self._save()
        return f'hunger-v1:{transaction_id}'
    def _save(self):
        if not self.ledger_path:return
        self.ledger_path.parent.mkdir(parents=True,exist_ok=True); temp=self.ledger_path.with_suffix('.tmp')
        temp.write_text(json.dumps({'value':self.value,'transactions':sorted(self._committed)}),encoding='utf-8'); os.replace(temp,self.ledger_path)

class TkFeedConfirmation:
    def __init__(self,root): self.root=root
    def confirm(self,target,consequence):
        return messagebox.askyesnocancel('确认文件喂食',f'{target.summary}\n\n{consequence}\n\n只有回收成功才增加饥饿值。',parent=self.root)

class FeedAnimation:
    def __init__(self,pet): self.pet=pet
    def play_eating(self,transaction_id): del transaction_id; self.pet.play_feed_success()

class FeedRuntime:
    def __init__(self,pet,coordinator): self.pet=pet; self.coordinator=coordinator
    @classmethod
    def create_for_test(cls,pet,state_root,confirmer,recycler,hunger):
        validator=FileValidator(protected_roots=[],application_path=Path(state_root)/'app.exe',repository_root=Path(state_root)/'repo')
        return cls(pet,FeedCoordinator(TransactionJournal(Path(state_root)/'journal'),validator,confirmer,recycler,hunger,FeedAnimation(pet)))
    @classmethod
    def create_windows(cls,root,pet,state_root):
        state_root=Path(state_root)
        hunger=HungerMeter(0,20,state_root/'hunger.json')
        recycler=IFileOperationRecycler()
        coordinator=FeedCoordinator(TransactionJournal(state_root/'transactions'),FileValidator(),TkFeedConfirmation(root),recycler,hunger,FeedAnimation(pet))
        runtime=cls(pet,coordinator)
        recovered=coordinator.recover()
        if any(item.state is FeedState.NEEDS_REVIEW for item in recovered):
            recycler.block_for_review()
            pet.show_feed_feedback('发现未完成的旧投喂事务，已停止新操作并等待人工复核')
        return runtime
    def close(self):
        close=getattr(self.coordinator.recycler,'close',None)
        if callable(close):close()
    def drag_enter(self,paths,x,y):
        if getattr(self.coordinator.recycler,'available',True) is False:
            self.pet.show_feed_feedback('存在待人工复核事务，当前禁止继续投喂'); return 'none'
        if len(paths)!=1 or not self.pet.head_feed_contains(x,y): return 'none'
        try:self.coordinator.validator.validate(paths[0],explicitly_dropped=True)
        except Rejection as error:self.pet.show_feed_feedback(f'不能投喂：{error}'); return 'none'
        self.pet.show_feed_feedback('期待投喂：松开后将先确认'); return 'copy'
    def drag_leave(self): self.pet.show_feed_feedback('已取消投喂')
    def drop(self,paths,x,y):
        if self.drag_enter(paths,x,y)!='copy': return None
        try:result=self.coordinator.handle_explicit_drop(paths[0])
        except Rejection as error:self.pet.show_feed_feedback(f'投喂失败：{error}'); return None
        if result.state is FeedState.COMPLETED:self.pet.show_feed_feedback('投喂成功，饥饿值已增加')
        elif result.state is FeedState.CANCELLED:self.pet.show_feed_feedback('已取消，文件未操作')
        elif result.state is FeedState.NEEDS_REVIEW:self.pet.show_feed_feedback('结果不确定，已停止操作并等待人工复核')
        else:self.pet.show_feed_feedback('投喂失败，饥饿值未改变')
        return result

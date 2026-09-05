from __future__ import annotations
import hashlib, json, os, secrets, threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from .model import FeedState, FeedTransaction
from .validation import FileValidator

class TransactionJournal:
    SCHEMA_VERSION=2
    def __init__(self, root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self._lock=threading.RLock()
    def _path(self, txid): return self.root/f'{txid}.json'
    def _write(self, tx, event):
        with self._lock:
            path=self._path(tx.id); history=[]
            if path.exists(): history=json.loads(path.read_text(encoding='utf-8')).get('history',[])
            history.append({'at':datetime.now(timezone.utc).isoformat(),'state':tx.state.value,'event':event})
            data={'schema_version':self.SCHEMA_VERSION,'id':tx.id,'state':tx.state.value,
                  'target':{'name':tx.target_name,'fingerprint':tx.target_fingerprint},
                  'recycle_credential':tx.recycle_credential,'recycle_evidence':tx.recycle_evidence,'reward_credential':tx.reward_credential,
                  'animation_interrupted':tx.animation_interrupted,'failure_code':tx.failure_code,'history':history}
            temp=path.with_suffix('.tmp'); temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); os.replace(temp,path)
            return tx
    def create(self, path):
        p=Path(path); fp=FileValidator._identity(p,p.lstat()).fingerprint
        return self._write(FeedTransaction(secrets.token_hex(16),FeedState.PENDING_CONFIRMATION,p.name,fp),'created')
    def transition(self, txid, state, **changes):
        with self._lock:
            old=self.load(txid); values=asdict(old); values.update(changes); values['state']=state
            return self._write(FeedTransaction(**values),'transition')
    def load(self, txid):
        with self._lock:
            d=json.loads(self._path(txid).read_text(encoding='utf-8'))
            if d.get('schema_version') != self.SCHEMA_VERSION: raise ValueError('unsupported journal schema')
            t=d['target']
            return FeedTransaction(d['id'],FeedState(d['state']),t['name'],t['fingerprint'],d.get('recycle_credential'),d.get('recycle_evidence'),d.get('reward_credential'),d.get('animation_interrupted',False),d.get('failure_code'))
    def all(self):
        transactions=[]
        originals=[p for p in sorted(self.root.glob('*.json')) if not p.stem.startswith('review-')]
        for path in originals:
            try: transactions.append(self.load(path.stem))
            except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):
                digest=hashlib.sha256(path.name.encode()).hexdigest(); review_id=f'review-{digest[:24]}'
                review_path=self._path(review_id)
                if review_path.exists(): transactions.append(self.load(review_id))
                else:
                    tx=FeedTransaction(review_id,FeedState.NEEDS_REVIEW,'<unreadable-journal>',digest,f'audit-retained:{digest[:12]}','invalid-journal-retained',None,False,'invalid_or_unsupported_journal')
                    transactions.append(self._write(tx,'recovery-isolated'))
        return transactions

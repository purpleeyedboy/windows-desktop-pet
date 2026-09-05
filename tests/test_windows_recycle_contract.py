from pathlib import Path
import inspect
import os
import pytest
from desktop_pet.feed_core.windows_recycle import IFileOperationRecycler, RECYCLE_FLAGS

def test_contract_uses_sta_ifileoperation_and_no_delete_fallback():
    source=inspect.getsource(__import__('desktop_pet.feed_core.windows_recycle',fromlist=['x']))
    assert 'COINIT_APARTMENTTHREADED' in source and 'IFileOperation' in source
    assert 'FOFX_RECYCLEONDELETE' in source and 'FOF_ALLOWUNDO' in source
    for forbidden in ('DeleteFile', 'SHFileOperation', 'subprocess', 'os.remove', 'unlink('): assert forbidden not in source

def test_non_windows_refuses_instead_of_falling_back(tmp_path):
    if os.name=='nt': pytest.skip('non-Windows contract')
    f=tmp_path/'owned.txt'; f.write_text('x')
    recycler=IFileOperationRecycler()
    with pytest.raises(OSError): recycler.recycle(f,'tx',expected_identity=None)
    assert f.exists()
    recycler.close()

def test_adapter_contract_has_bounded_wait_cancel_identity_and_receipt():
    source=inspect.getsource(__import__('desktop_pet.feed_core.windows_recycle',fromlist=['x']))
    assert 'DEFAULT_OPERATION_TIMEOUT_SECONDS' in source
    assert 'cancel_event' in source and 'expected_identity' in source
    assert 'RecycleReceipt.create' in source and 'source-absent:undo-required' in source
    assert '.wait()' not in source

def test_timeout_opens_circuit_and_refuses_later_destructive_requests(monkeypatch, tmp_path):
    import desktop_pet.feed_core.windows_recycle as module
    from desktop_pet.feed_core.model import FileIdentity, RecycleReceipt
    monkeypatch.setattr(module.os,'name','nt')
    identity=FileIdentity(1,2,3,1,4,5,'fingerprint')
    calls=[]
    def fake_run(self,job):
        calls.append(job.transaction_id)
        import time; time.sleep(.1)
        job.result=RecycleReceipt.create(job.transaction_id,identity,evidence='mock')
        job.done.set()
    monkeypatch.setattr(module.IFileOperationRecycler,'_run_job',fake_run)
    recycler=module.IFileOperationRecycler()
    with pytest.raises(TimeoutError):
        recycler.recycle(tmp_path/'x','slow',expected_identity=identity,timeout_seconds=.01)
    with pytest.raises(InterruptedError,match='NeedsReview'):
        recycler.recycle(tmp_path/'x','refused',expected_identity=identity,timeout_seconds=.05)
    assert calls==['slow']
    recycler.close(timeout_seconds=.2)

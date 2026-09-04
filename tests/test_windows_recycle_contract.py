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
    with pytest.raises(OSError): recycler.recycle(f,'tx')
    assert f.exists()
    recycler.close()

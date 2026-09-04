"""Destructive adapter smoke test: skipped unless a developer explicitly opts in."""
import os, tempfile
from pathlib import Path
import pytest
from desktop_pet.feed_core.windows_recycle import IFileOperationRecycler

@pytest.mark.skipif(os.name!='nt' or os.environ.get('DESKTOP_PET_RUN_RECYCLE_E2E')!='1', reason='explicit Windows opt-in only')
def test_recycles_only_a_test_created_temporary_file():
    with tempfile.TemporaryDirectory(prefix='desktop-pet-feed-e2e-') as owned:
        root=Path(owned).resolve(); target=root/'owned-by-feed-core-test.txt'; target.write_text('test data')
        assert target.parent==root
        recycler=IFileOperationRecycler()
        try: assert recycler.recycle(target,'e2e-owned-transaction') and not target.exists()
        finally: recycler.close()
        # IFileOperation used FOF_ALLOWUNDO + FOFX_RECYCLEONDELETE, so the item remains user-restorable.

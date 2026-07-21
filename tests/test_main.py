import os
from uuid import uuid4

import pytest

from desktop_pet.main import SingleInstanceMutex, build_mutex_name


def test_mutex_name_is_stable_and_user_scoped(monkeypatch):
    monkeypatch.setenv("USERNAME", "pet-tester")
    assert build_mutex_name() == r"Local\DesktopCatPet-pet-tester"


@pytest.mark.skipif(os.name != "nt", reason="Windows mutex contract")
def test_mutex_excludes_second_holder():
    name = rf"Local\DesktopCatPet-test-{uuid4()}"
    first = SingleInstanceMutex(name)
    second = SingleInstanceMutex(name)
    try:
        assert first.acquire() is True
        assert second.acquire() is False
    finally:
        second.close()
        first.close()

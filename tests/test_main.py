import importlib
import os
from uuid import uuid4

import pytest

from desktop_pet.main import SingleInstanceMutex, build_mutex_name


def test_main_enables_dpi_awareness_before_creating_tk(monkeypatch):
    main_module = importlib.import_module("desktop_pet.main")
    calls: list[str] = []

    class FakeMutex:
        def __init__(self, _name):
            pass

        def acquire(self):
            return True

        def close(self):
            pass

    class FakeRoot:
        def __init__(self):
            calls.append("tk")

        def withdraw(self):
            pass

        def mainloop(self):
            pass

        def winfo_exists(self):
            return False

    monkeypatch.setattr(
        main_module,
        "enable_per_monitor_dpi_awareness",
        lambda: calls.append("dpi"),
        raising=False,
    )
    monkeypatch.setattr(main_module, "SingleInstanceMutex", FakeMutex)
    monkeypatch.setattr(main_module.tk, "Tk", FakeRoot)
    monkeypatch.setattr(main_module, "load_frames", lambda: {"jump": ()})
    monkeypatch.setattr(main_module, "PetWindow", lambda *_args: None)

    assert main_module.main() == 0
    assert calls == ["dpi", "tk"]


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

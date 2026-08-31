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
    frames = {"jump": ()}
    compositor = object()
    cursor = object()
    monkeypatch.setattr(
        main_module,
        "load_frames",
        lambda: calls.append("frames") or frames,
    )
    monkeypatch.setattr(
        main_module,
        "load_head_neck_compositor",
        lambda: calls.append("compositor") or compositor,
        raising=False,
    )
    monkeypatch.setattr(
        main_module,
        "Win32CursorProvider",
        lambda: calls.append("cursor") or cursor,
        raising=False,
    )
    monkeypatch.setattr(
        main_module,
        "PetWindow",
        lambda root, actual_frames, **kwargs: calls.append(
            (
                "pet",
                root,
                actual_frames,
                kwargs.get("compositor"),
                kwargs.get("cursor_provider"),
                kwargs.get("head_follow"),
            )
        ),
    )

    assert main_module.main() == 0
    assert calls[:5] == ["dpi", "tk", "frames", "compositor", "cursor"]
    assert calls[5][0] == "pet"
    assert calls[5][2:] == (frames, compositor, cursor, True)


def test_main_routes_compositor_failure_through_fatal_startup(
    monkeypatch,
) -> None:
    main_module = importlib.import_module("desktop_pet.main")
    fatal: list[tuple[str, object]] = []
    pet_calls: list[object] = []

    class FakeMutex:
        def __init__(self, _name):
            pass

        def acquire(self):
            return True

        def close(self):
            pass

    class FakeRoot:
        def withdraw(self):
            pass

        def winfo_exists(self):
            return False

    monkeypatch.setattr(main_module, "enable_per_monitor_dpi_awareness", lambda: None)
    monkeypatch.setattr(main_module, "SingleInstanceMutex", FakeMutex)
    monkeypatch.setattr(main_module.tk, "Tk", FakeRoot)
    monkeypatch.setattr(main_module, "load_frames", lambda: {"jump": ()})
    monkeypatch.setattr(
        main_module,
        "load_head_neck_compositor",
        lambda: (_ for _ in ()).throw(ValueError("bad compositor")),
        raising=False,
    )
    monkeypatch.setattr(main_module, "PetWindow", lambda *_a, **_k: pet_calls.append(1))
    monkeypatch.setattr(
        main_module,
        "show_fatal_error",
        lambda message, root=None: fatal.append((message, root)),
    )

    assert main_module.main() == 1
    assert pet_calls == []
    assert len(fatal) == 1
    assert fatal[0][0] == "bad compositor"
    assert isinstance(fatal[0][1], FakeRoot)


def test_main_finally_uses_pet_close_before_direct_root_cleanup(monkeypatch) -> None:
    main_module = importlib.import_module("desktop_pet.main")
    calls: list[str] = []

    class FakeMutex:
        def __init__(self, _name):
            pass

        def acquire(self):
            return True

        def close(self):
            calls.append("mutex-close")

    class FakeRoot:
        def __init__(self):
            self.destroyed = False

        def withdraw(self):
            pass

        def mainloop(self):
            calls.append("mainloop")

        def winfo_exists(self):
            return not self.destroyed

        def destroy(self):
            calls.append("direct-root-destroy")
            self.destroyed = True

    class FakePet:
        def __init__(self, root, *_args, **_kwargs):
            self.root = root

        def close(self):
            calls.append("pet-close")
            self.root.destroyed = True

    monkeypatch.setattr(main_module, "enable_per_monitor_dpi_awareness", lambda: None)
    monkeypatch.setattr(main_module, "SingleInstanceMutex", FakeMutex)
    monkeypatch.setattr(main_module.tk, "Tk", FakeRoot)
    monkeypatch.setattr(main_module, "load_frames", lambda: {"jump": ()})
    monkeypatch.setattr(main_module, "load_head_neck_compositor", object)
    monkeypatch.setattr(main_module, "Win32CursorProvider", object)
    monkeypatch.setattr(main_module, "PetWindow", FakePet)

    assert main_module.main() == 0
    assert calls == ["mainloop", "pet-close", "mutex-close"]


def test_main_constructor_failure_reports_fatal_then_destroys_root(monkeypatch) -> None:
    main_module = importlib.import_module("desktop_pet.main")
    calls: list[str] = []

    class FakeMutex:
        def __init__(self, _name):
            pass

        def acquire(self):
            return True

        def close(self):
            calls.append("mutex-close")

    class FakeRoot:
        def __init__(self):
            self.destroyed = False

        def withdraw(self):
            pass

        def winfo_exists(self):
            return not self.destroyed

        def destroy(self):
            calls.append("root-destroy")
            self.destroyed = True

    monkeypatch.setattr(main_module, "enable_per_monitor_dpi_awareness", lambda: None)
    monkeypatch.setattr(main_module, "SingleInstanceMutex", FakeMutex)
    monkeypatch.setattr(main_module.tk, "Tk", FakeRoot)
    monkeypatch.setattr(main_module, "load_frames", lambda: {"jump": ()})
    monkeypatch.setattr(main_module, "load_head_neck_compositor", object)
    monkeypatch.setattr(main_module, "Win32CursorProvider", object)
    monkeypatch.setattr(
        main_module,
        "PetWindow",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("partial constructor failed")
        ),
    )
    monkeypatch.setattr(
        main_module,
        "show_fatal_error",
        lambda message, _root=None: calls.append(f"fatal:{message}"),
    )

    assert main_module.main() == 1
    assert calls == [
        "fatal:partial constructor failed",
        "root-destroy",
        "mutex-close",
    ]


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

import sys
import types

from desktop_pet.feed_core import foundation_contract


def test_loader_uses_published_services_entry_and_passes_build_info(monkeypatch):
    calls = []
    services_module = types.ModuleType("desktop_pet.foundation.services")
    services_module.create_application_services = lambda build_info: calls.append(build_info) or "services"
    runtime_module = types.ModuleType("desktop_pet.foundation.runtime")
    runtime_module.RuntimeContext = type("RuntimeContext", (), {})
    package = types.ModuleType("desktop_pet.foundation")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "desktop_pet.foundation", package)
    monkeypatch.setitem(sys.modules, "desktop_pet.foundation.services", services_module)
    monkeypatch.setitem(sys.modules, "desktop_pet.foundation.runtime", runtime_module)

    build_info = {"version": "2.1.0"}
    assert foundation_contract.load_foundation_services(build_info) == "services"
    assert foundation_contract.load_runtime_context_type() is runtime_module.RuntimeContext
    assert calls == [build_info]


def test_loader_fails_closed_when_published_foundation_files_are_absent(monkeypatch):
    monkeypatch.delitem(sys.modules, "desktop_pet.foundation.services", raising=False)
    monkeypatch.delitem(sys.modules, "desktop_pet.foundation.runtime", raising=False)
    assert foundation_contract.load_foundation_services({}) is None
    assert foundation_contract.load_runtime_context_type() is None

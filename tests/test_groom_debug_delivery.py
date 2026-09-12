import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from desktop_pet.main import load_groom_debug_enabled
from desktop_pet.window import PetWindow


def test_debug_requires_explicit_test_build_and_boolean_flag(tmp_path: Path) -> None:
    path = tmp_path / "build-info.json"
    assert load_groom_debug_enabled(path) is False
    for data in (
        {},
        {"version": "2.1-LICK", "debug_menu": True},
        {"version": "2.1-LICK", "test_build": False, "debug_menu": True},
        {"version": "2.1-LICK", "test_build": True, "debug_menu": "false"},
        {"version": "other", "test_build": True, "debug_menu": True},
    ):
        path.write_text(json.dumps(data))
        assert load_groom_debug_enabled(path) is False
    path.write_text(json.dumps({"version": "2.1-LICK", "test_build": True, "debug_menu": True}))
    assert load_groom_debug_enabled(path) is True


class FakeMenu:
    def __init__(self, *_args, **_kwargs):
        self.commands = []
        self.cascades = []

    def add_command(self, **kwargs):
        self.commands.append(kwargs)

    def add_cascade(self, **kwargs):
        self.cascades.append(kwargs)

    def add_separator(self):
        pass

    def add_checkbutton(self, **_kwargs):
        pass


def test_debug_submenu_only_requests_current_groom_action() -> None:
    requests = []
    pet = PetWindow.__new__(PetWindow)
    pet.root = object()
    pet._groom_debug_menu = True
    pet.eye_session = SimpleNamespace(request_groom_debug=lambda count: requests.append(count))
    pet._topmost_var = object()
    pet.trigger_blink = lambda: requests.append("unexpected-blink")
    pet.close = lambda: requests.append("unexpected-close")
    with patch("desktop_pet.window.tk.Menu", FakeMenu):
        menu = pet._create_menu()
        assert len(menu.cascades) == 1
        assert menu.cascades[0]["label"] == "调试"
        debug = menu.cascades[0]["menu"]
        assert len(debug.commands) == 1
        assert debug.commands[0]["label"] == "左前爪舔手（3次）"
        debug.commands[0]["command"]()
        assert requests == [3]
        pet._groom_debug_menu = False
        assert pet._create_menu().cascades == []

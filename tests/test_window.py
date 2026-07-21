from types import SimpleNamespace

import pytest
from PIL import Image

from desktop_pet import configure_tk_environment

configure_tk_environment()

import tkinter as tk

from desktop_pet.bubble import BubbleWindow
from desktop_pet.model import Rect
from desktop_pet.window import PetWindow, SIZE_PRESETS, format_position


@pytest.fixture(scope="module")
def base_tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    if root.winfo_exists():
        root.destroy()


@pytest.fixture
def tk_root(base_tk_root):
    for child in base_tk_root.winfo_children():
        child.destroy()
    base_tk_root.withdraw()
    yield base_tk_root
    for child in base_tk_root.winfo_children():
        child.destroy()
    base_tk_root.withdraw()


@pytest.fixture
def loaded_frames():
    frame = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    for x in range(128, 384):
        for y in range(96, 736):
            frame.putpixel((x, y), (255, 255, 255, 255))
    return {
        action: tuple(frame.copy() for _ in range(6))
        for action in ("jump", "squash", "shake")
    }


def test_format_position_supports_negative_monitor_coordinates():
    assert format_position(-1920, 20) == "-1920+20"
    assert format_position(50, -100) == "+50-100"


def test_bubble_is_opaque_and_placed_outside_pet(tk_root):
    bubble = BubbleWindow(tk_root)
    pet = Rect(500, 500, 200, 300)
    screen = Rect(0, 0, 1200, 900)
    bubble.show_message("看我起飞！", pet, screen)
    tk_root.update_idletasks()
    assert bubble.last_rect is not None
    assert not bubble.last_rect.intersects(pet)
    assert screen.contains(bubble.last_rect)
    assert bubble.canvas.itemcget(bubble.body_item, "fill") == "#ffffff"
    bubble.destroy()


def test_window_contract_and_menu(tk_root, loaded_frames):
    window = PetWindow(tk_root, loaded_frames)
    tk_root.update_idletasks()
    assert bool(tk_root.overrideredirect()) is True
    assert window.always_on_top is True
    assert window.display_height == 280
    labels = [
        window.menu.entrycget(index, "label")
        for index in range(window.menu.index("end") + 1)
        if window.menu.type(index) != "separator"
    ]
    assert {"小", "中", "大", "始终置顶", "退出"}.issubset(labels)


def test_size_clamp_presets_wheel_and_topmost(tk_root, loaded_frames):
    window = PetWindow(tk_root, loaded_frames)
    window.set_display_height(40)
    assert window.display_height == 120
    window.set_display_height(900)
    assert window.display_height == 520
    window.set_display_height(SIZE_PRESETS["中"])
    window._on_wheel(SimpleNamespace(delta=-120))
    assert window.display_height == 256
    window.set_always_on_top(False)
    assert window.always_on_top is False


def test_click_cycles_actions_but_drag_does_not(tk_root, loaded_frames, monkeypatch):
    window = PetWindow(tk_root, loaded_frames)
    played: list[str] = []
    monkeypatch.setattr(window.animation, "play", lambda action: played.append(action) or True)
    monkeypatch.setattr(window.bubble, "show_message", lambda *_: None)
    window.handle_left_release((100, 100), (102, 102))
    window.handle_left_release((100, 100), (150, 150))
    window.handle_left_release((100, 100), (101, 101))
    assert played == ["jump", "squash"]

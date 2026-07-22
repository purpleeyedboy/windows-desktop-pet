from types import SimpleNamespace

import pytest
from PIL import Image

from desktop_pet import configure_tk_environment

configure_tk_environment()

import tkinter as tk

from desktop_pet.bubble import BubbleWindow
from desktop_pet.model import Rect
from desktop_pet.window import PetWindow, SIZE_PRESETS, format_position
from tests.fakes import FakeRenderer


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


def make_window(tk_root, loaded_frames):
    renderer = FakeRenderer(tk_root.winfo_id())
    window = PetWindow(
        tk_root,
        loaded_frames,
        renderer_factory=lambda _hwnd: renderer,
    )
    return window, renderer


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


def test_bubble_has_no_transparent_color_key(tk_root):
    bubble = BubbleWindow(tk_root)

    assert bubble.window.cget("background") == "#ffffff"
    assert bubble.canvas.cget("background") == "#ffffff"
    bubble.destroy()


def test_window_contract_and_menu(tk_root, loaded_frames):
    window, _renderer = make_window(tk_root, loaded_frames)
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
    window, _renderer = make_window(tk_root, loaded_frames)
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
    window, _renderer = make_window(tk_root, loaded_frames)
    played: list[str] = []
    monkeypatch.setattr(window.animation, "play", lambda action: played.append(action) or True)
    monkeypatch.setattr(window.bubble, "show_message", lambda *_: None)
    window.handle_left_release((100, 100), (102, 102))
    window.handle_left_release((100, 100), (150, 150))
    window.handle_left_release((100, 100), (101, 101))
    assert played == ["jump", "squash"]


def test_window_uses_rgba_renderer_without_character_label(tk_root, loaded_frames):
    window, renderer = make_window(tk_root, loaded_frames)

    rendered, x, y = renderer.calls[-1]
    assert rendered.mode == "RGBA"
    assert rendered.height == 280
    assert (x, y) == (window._window_rect.x, window._window_rect.y)
    assert not hasattr(window, "label")


def test_bindings_are_on_root(tk_root, loaded_frames):
    make_window(tk_root, loaded_frames)

    for event_name in (
        "<ButtonPress-1>",
        "<B1-Motion>",
        "<ButtonRelease-1>",
        "<Button-3>",
        "<MouseWheel>",
    ):
        assert tk_root.bind(event_name)


def test_wheel_resize_preserves_foot_center(tk_root, loaded_frames):
    window, _renderer = make_window(tk_root, loaded_frames)
    before = window._anchor()

    window._on_wheel(SimpleNamespace(delta=120))

    assert window._anchor() == before


def test_drag_moves_authoritative_rect_and_rerenders(tk_root, loaded_frames):
    window, renderer = make_window(tk_root, loaded_frames)
    before = window.pet_rect()
    call_count = len(renderer.calls)
    window._on_left_press(SimpleNamespace(x_root=100, y_root=100))

    window._on_left_motion(SimpleNamespace(x_root=124, y_root=136))

    assert window.pet_rect().x == before.x + 24
    assert window.pet_rect().y == before.y + 36
    assert len(renderer.calls) == call_count + 1
    _image, x, y = renderer.calls[-1]
    assert (x, y) == (window.pet_rect().x, window.pet_rect().y)


def test_topmost_updates_renderer_and_bubble(tk_root, loaded_frames):
    window, renderer = make_window(tk_root, loaded_frames)

    window.set_always_on_top(False)

    assert renderer.topmost is False
    assert window.always_on_top is False
    assert bool(window.bubble.window.attributes("-topmost")) is False

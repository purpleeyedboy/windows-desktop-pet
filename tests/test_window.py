from types import SimpleNamespace
from collections.abc import Callable

import pytest
from PIL import Image

from desktop_pet import configure_tk_environment

configure_tk_environment()

import tkinter as tk

from desktop_pet.bubble import BubbleWindow
from desktop_pet import window as window_module
from desktop_pet.eye_follow import CursorPoint
from desktop_pet.eye_runtime import ActionFailure
from desktop_pet.model import ACTIONS, Rect
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
        legacy_mode=True,
    )
    return window, renderer


class HeadlessClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class HeadlessRoot:
    def __init__(self, clock: HeadlessClock) -> None:
        self.clock = clock
        self.pending: list[tuple[str, int, Callable[[], None]]] = []
        self.cancelled: list[str] = []
        self.events: list[str] = []
        self.geometries: list[str] = []
        self.current_geometry: str | None = None
        self.geometry_failures: list[bool] = []
        self.after_raises_after_queue = False
        self.cancel_error: Exception | None = None
        self.bindings: dict[str, object] = {}
        self.protocols: dict[str, object] = {}
        self.attribute_values = {"-topmost": True}
        self.destroyed = False
        self.hidden = True
        self._next_token = 0

    def title(self, _value):
        pass

    def overrideredirect(self, _value=None):
        return True

    def configure(self, **_kwargs):
        pass

    def attributes(self, name, value=None):
        if value is None:
            return self.attribute_values.get(name)
        self.attribute_values[name] = value

    def update_idletasks(self):
        pass

    def winfo_x(self):
        return -120

    def winfo_y(self):
        return 40

    def winfo_id(self):
        return 42

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def geometry(self, value):
        self.events.append("geometry")
        self.geometries.append(value)
        self.current_geometry = value
        fail = self.geometry_failures.pop(0) if self.geometry_failures else False
        if fail:
            raise RuntimeError("injected geometry failure")

    def deiconify(self):
        self.events.append("deiconify")
        self.hidden = False

    def lift(self):
        self.events.append("lift")

    def bind(self, event, callback):
        self.bindings[event] = callback

    def protocol(self, name, callback):
        self.protocols[name] = callback

    def after(self, delay_ms, callback):
        self.events.append("after")
        self._next_token += 1
        token = f"headless-after-{self._next_token}"
        self.pending.append((token, delay_ms, callback))
        if self.after_raises_after_queue:
            self.after_raises_after_queue = False
            raise RuntimeError("injected scheduler failure after queue")
        return token

    def after_cancel(self, token):
        self.cancelled.append(token)
        if self.cancel_error is not None:
            raise self.cancel_error

    def live(self):
        return [entry for entry in self.pending if entry[0] not in self.cancelled]

    def run_next(self, advance_ms: int | None = None):
        while self.pending:
            token, delay_ms, callback = self.pending.pop(0)
            if token in self.cancelled:
                continue
            self.clock.value += (delay_ms if advance_ms is None else advance_ms) / 1000
            callback()
            return callback
        raise AssertionError("no live headless callback")

    def withdraw(self):
        pass

    def destroy(self):
        self.events.append("root-destroy")
        self.destroyed = True

    def winfo_exists(self):
        return not self.destroyed


class HeadlessVariable:
    def __init__(self, _root, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class HeadlessMenu:
    def __init__(self, _root, tearoff=False) -> None:
        self.commands: dict[str, object] = {}

    def add_command(self, *, label, command):
        self.commands[label] = command

    def add_separator(self):
        pass

    def add_checkbutton(self, *, label, variable, command):
        self.commands[label] = command

    def tk_popup(self, _x, _y):
        pass

    def grab_release(self):
        pass


class HeadlessBubble:
    def __init__(self, root, renderer_factory=None) -> None:
        self.events = root.events
        self.messages: list[tuple[str, Rect, Rect]] = []
        self.repositions: list[tuple[Rect, Rect]] = []
        self.destroyed = False

    def show_message(self, text, pet, screen):
        if not self.destroyed:
            self.messages.append((text, pet, screen))

    def reposition(self, pet, screen):
        if not self.destroyed:
            self.repositions.append((pet, screen))

    def set_always_on_top(self, _enabled):
        pass

    def destroy(self):
        self.events.append("bubble-destroy")
        self.destroyed = True


class HeadlessRenderer:
    def __init__(self) -> None:
        self.attempts: list[tuple[Image.Image, int, int]] = []
        self.successes: list[tuple[Image.Image, int, int]] = []
        self.failures: list[bool] = []
        self.topmost = True
        self.events: list[str] | None = None

    def render(self, image, x, y):
        if self.events is not None:
            self.events.append("render")
        self.attempts.append((image, x, y))
        fail = self.failures.pop(0) if self.failures else False
        if fail:
            raise RuntimeError("injected renderer failure")
        self.successes.append((image, x, y))

    def set_topmost(self, enabled):
        self.topmost = bool(enabled)


class HeadlessCompositor:
    source_size = (512, 768)
    eye_midpoint = (122.5, 349.0)

    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []
        self.fail_next = False
        self.events: list[str] | None = None

    def compose(self, eye_x, eye_y):
        if self.events is not None:
            self.events.append("compose")
        self.calls.append((eye_x, eye_y))
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("injected composition failure")
        color = (round((eye_x + 3) * 30), round((eye_y + 2) * 40), 70, 255)
        return Image.new("RGBA", self.source_size, color)


class HeadlessHeadCompositor:
    source_size = (512, 768)
    eye_midpoint = (122.5, 349.0)

    def __init__(self) -> None:
        self.calls: list[tuple[float, float, float, float]] = []
        self.events: list[str] | None = None

    def compose(self, eye_x, eye_y, head_pose):
        if self.events is not None:
            self.events.append("compose")
        call = (eye_x, eye_y, head_pose.x, head_pose.y)
        self.calls.append(call)
        color = (
            round((eye_x + 3) * 30),
            round((eye_y + 2) * 40),
            round((head_pose.x + 1) * 80),
            255,
        )
        return Image.new("RGBA", self.source_size, color)


class HeadlessCursor:
    def __init__(self, point=CursorPoint(1900, 100)) -> None:
        self.point = point

    def position(self):
        return self.point


def headless_frames():
    return {
        action: tuple(
            Image.new("RGBA", (512, 768), (30 + action_index * 50, index, 90, 255))
            for index in range(6)
        )
        for action_index, action in enumerate(ACTIONS)
    }


def prepare_headless(monkeypatch, *, compositor=None, cursor=None):
    clock = HeadlessClock()
    root = HeadlessRoot(clock)
    renderer = HeadlessRenderer()
    renderer.events = root.events
    bubble_holder: list[HeadlessBubble] = []
    reports: list[str] = []

    class RecordingBubble(HeadlessBubble):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            bubble_holder.append(self)

    monkeypatch.setattr(window_module.tk, "BooleanVar", HeadlessVariable)
    monkeypatch.setattr(window_module.tk, "Menu", HeadlessMenu)
    monkeypatch.setattr(window_module, "BubbleWindow", RecordingBubble)
    monkeypatch.setattr(
        window_module,
        "load_phrase_pools",
        lambda: {action: (f"phrase:{action}",) for action in ACTIONS},
    )
    frames = headless_frames()
    compositor = compositor or HeadlessCompositor()
    compositor.events = root.events
    cursor = cursor or HeadlessCursor()
    return root, renderer, bubble_holder, reports, frames, compositor, cursor, clock


def make_headless_window(monkeypatch, *, compositor=None, cursor=None):
    (
        root,
        renderer,
        bubble_holder,
        reports,
        frames,
        compositor,
        cursor,
        clock,
    ) = prepare_headless(monkeypatch, compositor=compositor, cursor=cursor)
    window = PetWindow(
        root,
        frames,
        renderer_factory=lambda _hwnd: renderer,
        compositor=compositor,
        cursor_provider=cursor,
        runtime_failure_reporter=reports.append,
        clock=clock,
    )
    return window, root, renderer, bubble_holder[0], compositor, cursor, frames, reports


def test_format_position_supports_negative_monitor_coordinates():
    assert format_position(-1920, 20) == "-1920+20"
    assert format_position(50, -100) == "+50-100"


def test_constrain_rect_to_area_keeps_the_whole_pet_visible():
    area = Rect(-1920, 0, 1920, 1040)

    constrained = window_module.constrain_rect_to_area(
        Rect(-2300, -120, 200, 300), area
    )

    assert constrained == Rect(-1920, 0, 200, 300)


def test_constrain_rect_to_area_handles_bottom_right_overflow():
    area = Rect(0, 0, 1920, 1040)

    constrained = window_module.constrain_rect_to_area(
        Rect(1900, 1000, 200, 300), area
    )

    assert constrained == Rect(1720, 740, 200, 300)


def test_bubble_window_uses_rgba_renderer_without_canvas(tk_root):
    renderer = FakeRenderer(tk_root.winfo_id())
    bubble = BubbleWindow(tk_root, renderer_factory=lambda _hwnd: renderer)
    pet = Rect(500, 500, 200, 300)
    screen = Rect(0, 0, 1200, 900)
    bubble.show_message("猫猫今天要起飞", pet, screen)
    tk_root.update_idletasks()

    assert bubble.last_rect is not None
    assert not bubble.last_rect.intersects(pet)
    assert screen.contains(bubble.last_rect)
    assert not hasattr(bubble, "canvas")
    assert renderer.calls[-1][0].mode == "RGBA"
    assert renderer.calls[-1][1:] == (bubble.last_rect.x, bubble.last_rect.y)
    bubble.destroy()


def test_bubble_window_has_no_color_key_or_rectangular_background(tk_root):
    renderer = FakeRenderer(tk_root.winfo_id())
    bubble = BubbleWindow(tk_root, renderer_factory=lambda _hwnd: renderer)

    bubble.show_message(
        "猫猫今天要起飞",
        Rect(500, 500, 200, 300),
        Rect(0, 0, 1200, 900),
    )
    image = renderer.calls[-1][0]

    assert image.getpixel((0, 0))[3] == 0
    assert image.getchannel("A").getextrema() == (0, 255)
    assert not hasattr(bubble, "canvas")
    bubble.destroy()


def test_bubble_window_scales_the_image_for_small_screen_fallback(tk_root):
    renderer = FakeRenderer(tk_root.winfo_id())
    bubble = BubbleWindow(tk_root, renderer_factory=lambda _hwnd: renderer)
    pet = Rect(226, 40, 347, 520)
    screen = Rect(0, 0, 800, 600)

    bubble.show_message("本喵压扁也回弹", pet, screen)
    tk_root.update_idletasks()

    assert bubble.last_rect is not None
    rendered = renderer.calls[-1][0]
    assert rendered.size == (bubble.last_rect.width, bubble.last_rect.height)
    assert not bubble.last_rect.intersects(pet)
    assert screen.contains(bubble.last_rect)
    bubble.destroy()


def test_bubble_stays_hidden_when_screen_has_no_safe_area(tk_root):
    renderer = FakeRenderer(tk_root.winfo_id())
    bubble = BubbleWindow(tk_root, renderer_factory=lambda _hwnd: renderer)
    occupied = Rect(0, 0, 200, 200)

    bubble.show_message("这里太挤啦！", occupied, occupied)
    tk_root.update_idletasks()

    assert bubble.visible is False
    assert bubble.last_rect is None
    bubble.destroy()


def test_hiding_for_no_space_cancels_the_old_hide_timer(
    tk_root, monkeypatch
):
    renderer = FakeRenderer(tk_root.winfo_id())
    bubble = BubbleWindow(tk_root, renderer_factory=lambda _hwnd: renderer)
    jobs: dict[str, object] = {}
    next_job = 0

    def schedule(_delay, callback):
        nonlocal next_job
        next_job += 1
        job = f"after-{next_job}"
        jobs[job] = callback
        return job

    def cancel(job):
        jobs.pop(job, None)

    monkeypatch.setattr(bubble.window, "after", schedule)
    monkeypatch.setattr(bubble.window, "after_cancel", cancel)
    safe_screen = Rect(0, 0, 1200, 900)
    pet = Rect(500, 500, 200, 300)
    bubble.show_message("第一句话", pet, safe_screen)
    old_job = bubble._hide_job

    bubble.show_message("这里太挤啦！", Rect(0, 0, 200, 200), Rect(0, 0, 200, 200))
    bubble.show_message("第二句话", pet, safe_screen)
    if old_job in jobs:
        jobs.pop(old_job)()

    assert bubble.visible is True
    assert bubble._text == "第二句话"
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
    assert {
        "动作：跳跃",
        "动作：压扁",
        "动作：抖动",
        "眨眼",
        "歪头：向左",
        "歪头：向右",
        "歪头：左到右",
        "小",
        "中",
        "大",
        "始终置顶",
        "退出",
    }.issubset(labels)


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


def test_each_successful_action_uses_its_matching_dialogue_pool(
    tk_root,
    loaded_frames,
    monkeypatch,
):
    window, _renderer = make_window(tk_root, loaded_frames)
    chosen: list[str] = []
    shown: list[str] = []
    monkeypatch.setattr(
        window.animation,
        "play",
        lambda action: True,
    )
    monkeypatch.setattr(
        window.dialogue,
        "choose",
        lambda action: chosen.append(action) or f"{action}猫猫台词",
    )
    monkeypatch.setattr(
        window.bubble,
        "show_message",
        lambda text, *_args: shown.append(text),
    )

    window.trigger_next_action()
    window.trigger_next_action()
    window.trigger_next_action()

    assert chosen == ["jump", "squash", "shake"]
    assert shown == ["jump猫猫台词", "squash猫猫台词", "shake猫猫台词"]


def test_failed_action_start_does_not_choose_or_show_dialogue(
    tk_root,
    loaded_frames,
    monkeypatch,
):
    window, _renderer = make_window(tk_root, loaded_frames)
    chosen: list[str] = []
    shown: list[str] = []
    monkeypatch.setattr(window.animation, "play", lambda _action: False)
    monkeypatch.setattr(
        window.dialogue,
        "choose",
        lambda action: chosen.append(action) or "不该显示的台词",
    )
    monkeypatch.setattr(
        window.bubble,
        "show_message",
        lambda text, *_args: shown.append(text),
    )

    window.trigger_next_action()

    assert chosen == []
    assert shown == []


def test_finished_animation_keeps_its_last_frame(tk_root, loaded_frames):
    final_frame = Image.new("RGBA", (512, 768), (17, 34, 51, 255))
    loaded_frames["squash"] = (*loaded_frames["squash"][:-1], final_frame)
    window, renderer = make_window(tk_root, loaded_frames)
    window.show_frame("squash", 5)
    rendered_before_finish = len(renderer.calls)

    window._animation_finished("squash")

    assert window._current_image is final_frame
    assert len(renderer.calls) == rendered_before_finish


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
        "<FocusOut>",
        "<Leave>",
    ):
        assert tk_root.bind(event_name)


def test_headless_ear_press_release_is_independent_from_actions_and_restores(monkeypatch):
    window, root, renderer, bubble, _compositor, _cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )
    baseline = renderer.successes[-1][0].tobytes()
    render_count = len(renderer.successes)
    rect = window.pet_rect()
    point = SimpleNamespace(
        x_root=rect.x + round(50 * rect.width / 512),
        y_root=rect.y + round(240 * rect.height / 768),
    )

    window._on_left_press(point)
    assert window._ear_motion.active_side == "left"
    assert window.animation.busy is False
    assert bubble.messages == []
    assert len(renderer.successes) == render_count + 1

    window._on_left_release(point)
    while window._ear_motion.active_side is not None:
        root.run_next()
    assert window._ear_amount == 0.0
    assert window._current_image is window._latest_composed_frame
    assert window.eye_session.state == "following"


def test_headless_ear_pointer_leave_focus_loss_and_close_restore_neutral(monkeypatch):
    window, _root, renderer, _bubble, _compositor, _cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )
    baseline = renderer.successes[-1][0].tobytes()
    rect = window.pet_rect()
    point = SimpleNamespace(
        x_root=rect.x + round(220 * rect.width / 512),
        y_root=rect.y + round(240 * rect.height / 768),
    )

    window._on_left_press(point)
    window._on_pointer_leave(None)
    assert renderer.successes[-1][0].tobytes() == baseline
    window._on_left_press(point)
    window._on_focus_lost(None)
    assert renderer.successes[-1][0].tobytes() == baseline
    window._on_left_press(point)
    window.close()
    assert window._ear_motion.active_side is None


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


def test_drag_is_clamped_to_the_nearest_work_area(
    tk_root, loaded_frames, monkeypatch
):
    window, _renderer = make_window(tk_root, loaded_frames)
    area = Rect(0, 0, 800, 600)
    monkeypatch.setattr(window, "work_area_for", lambda _rect: area)
    window._move_to(200, 200)
    window._on_left_press(SimpleNamespace(x_root=250, y_root=250))

    window._on_left_motion(SimpleNamespace(x_root=-500, y_root=-500))

    assert area.contains(window.pet_rect())


def test_resize_is_clamped_to_the_nearest_work_area(
    tk_root, loaded_frames, monkeypatch
):
    window, _renderer = make_window(tk_root, loaded_frames)
    area = Rect(0, 0, 800, 600)
    monkeypatch.setattr(window, "work_area_for", lambda _rect: area)
    window._move_to(740, 500)

    window.set_display_height(520)

    assert area.contains(window.pet_rect())


@pytest.mark.parametrize(
    ("area", "expected_height"),
    (
        (Rect(0, 0, 800, 300), 300),
        (Rect(0, 0, 180, 600), 270),
    ),
)
def test_resize_shrinks_to_fit_a_smaller_work_area(
    tk_root, loaded_frames, monkeypatch, area, expected_height
):
    window, _renderer = make_window(tk_root, loaded_frames)
    monkeypatch.setattr(window, "work_area_for", lambda _rect: area)

    window.set_display_height(520)

    assert window.display_height == expected_height
    assert area.contains(window.pet_rect())


def test_topmost_updates_renderer_and_bubble(tk_root, loaded_frames):
    window, renderer = make_window(tk_root, loaded_frames)

    window.set_always_on_top(False)

    assert renderer.topmost is False
    assert window.always_on_top is False
    assert bool(window.bubble.window.attributes("-topmost")) is False


def test_headless_probe_initialization_displays_cached_center_then_starts_one_loop(
    monkeypatch,
):
    window, root, renderer, _bubble, compositor, _cursor, _frames, reports = (
        make_headless_window(monkeypatch)
    )

    assert compositor.calls == [(0.0, 0.0)]
    assert window.eye_session.state == "following"
    assert window.eye_session.last_displayed_pose == (0.0, 0.0)
    assert window._current_image is window._neutral_center_frame
    assert len(root.live()) == 1
    assert root.live()[0][1] == 33
    assert renderer.successes[-1][1:] == (
        window._window_rect.x,
        window._window_rect.y,
    )
    assert reports == []


def test_headless_continuous_head_mode_wires_one_coordinated_runtime_loop(
    monkeypatch,
) -> None:
    compositor = HeadlessHeadCompositor()
    root, renderer, bubbles, reports, frames, compositor, cursor, clock = (
        prepare_headless(monkeypatch, compositor=compositor)
    )
    window = PetWindow(
        root,
        frames,
        renderer_factory=lambda _hwnd: renderer,
        compositor=compositor,
        cursor_provider=cursor,
        runtime_failure_reporter=reports.append,
        clock=clock,
        head_follow=True,
    )

    assert compositor.calls == [(0.0, 0.0, 0.0, 0.0)]
    root.run_next(advance_ms=33)

    assert len(compositor.calls) == 2
    assert compositor.calls[-1] != (0.0, 0.0, 0.0, 0.0)
    assert window.eye_session.last_displayed_head_pose != (0.0, 0.0)
    assert len(root.live()) == 1
    assert len(renderer.successes) == 2
    assert bubbles[0].destroyed is False
    assert reports == []


def test_headless_continuous_head_action_recenters_to_literal_cached_center(
    monkeypatch,
) -> None:
    compositor = HeadlessHeadCompositor()
    root, renderer, _bubbles, reports, frames, compositor, cursor, clock = (
        prepare_headless(monkeypatch, compositor=compositor)
    )
    window = PetWindow(
        root,
        frames,
        renderer_factory=lambda _hwnd: renderer,
        compositor=compositor,
        cursor_provider=cursor,
        runtime_failure_reporter=reports.append,
        clock=clock,
        head_follow=True,
    )
    center = window._neutral_center_frame
    root.run_next(advance_ms=33)
    calls_before_recenter = len(compositor.calls)

    window.trigger_next_action()
    root.run_next(advance_ms=132)

    assert window._current_image is center
    assert len(compositor.calls) == calls_before_recenter
    assert window.eye_session.last_displayed_pose == (0.0, 0.0)
    assert window.eye_session.last_displayed_head_pose == (0.0, 0.0)
    assert window.animation.busy is True
    assert reports == []


def test_headless_follow_uses_live_drag_resize_and_negative_geometry(monkeypatch):
    window, root, renderer, _bubble, compositor, cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )
    window._window_rect = Rect(-450, -120, 341, 512)
    window.display_height = 512
    monkeypatch.setattr(
        window,
        "work_area_for",
        lambda _rect: Rect(-1920, -1080, 3840, 2160),
    )
    cursor.point = CursorPoint(900, -80)
    calls_before = len(renderer.attempts)

    root.run_next(advance_ms=33)

    assert len(compositor.calls) == 2
    assert compositor.calls[-1] != (0.0, 0.0)
    assert len(renderer.attempts) == calls_before + 1
    assert renderer.successes[-1][1:] == (-450, -120)
    assert window._window_rect == Rect(-450, -120, 341, 512)
    assert window._resized_image.size == (341, 512)


def test_headless_normal_action_uses_literal_center_noop_and_real_middle_frames(
    monkeypatch,
):
    window, root, renderer, bubble, _compositor, _cursor, frames, _reports = (
        make_headless_window(monkeypatch)
    )
    center = window._current_image
    renders_before = len(renderer.attempts)

    window.trigger_next_action()

    assert window._current_image is center
    assert len(renderer.attempts) == renders_before
    assert window.action_cycle.peek() == "squash"
    assert len(bubble.messages) == 1

    displayed: list[Image.Image] = []
    for _ in range(5):
        root.run_next(advance_ms=90)
        displayed.append(window._current_image)

    assert displayed[:4] == list(frames["jump"][1:5])
    assert all(
        actual is expected
        for actual, expected in zip(displayed[:4], frames["jump"][1:5], strict=True)
    )
    assert displayed[4] is center
    assert len(renderer.attempts) == renders_before + 5

    renders_before_finish = len(renderer.attempts)
    root.run_next(advance_ms=90)
    assert window.eye_session.state == "following"
    assert len(root.live()) == 1
    assert len(renderer.attempts) == renders_before_finish


def test_headless_recenter_reuses_literal_center_before_frame_zero_noop(
    monkeypatch,
):
    window, root, renderer, _bubble, _compositor, cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )
    center = window._neutral_center_frame
    cursor.point = CursorPoint(1900, 0)
    root.run_next(advance_ms=33)
    assert window._current_image is not center
    window.trigger_next_action()
    renders_before_center = len(renderer.attempts)

    root.run_next(advance_ms=132)

    assert window._current_image is center
    assert len(renderer.attempts) == renders_before_center + 1
    assert window.animation.busy is True


def test_headless_resize_failure_during_action_cancels_owner_before_fallback(
    monkeypatch,
):
    window, _root, renderer, _bubble, _compositor, _cursor, frames, _reports = (
        make_headless_window(monkeypatch)
    )
    window.trigger_next_action()
    assert window.animation.busy is True
    renderer.failures.append(True)

    window.set_display_height(420)

    assert window.animation.busy is False
    assert window.eye_session.state == "stopped"
    assert window._legacy_fallback is True
    window.trigger_next_action()
    assert window._current_image is frames["squash"][0]


def test_headless_transient_renderer_failure_rolls_back_without_stopping_follow(
    monkeypatch,
):
    window, _root, renderer, bubble, _compositor, _cursor, frames, reports = (
        make_headless_window(monkeypatch)
    )
    snapshot = (
        window._current_image,
        window._resized_image,
        window._window_rect,
        window.display_height,
        window.root.geometries[-1],
    )
    candidate = Image.new("RGBA", (512, 768), (250, 10, 20, 255))
    renderer.failures.append(True)

    with pytest.raises(RuntimeError, match="injected renderer failure"):
        window._apply_image(candidate, (210, 730), requested_height=420)

    assert window._current_image is snapshot[0]
    assert window._resized_image is snapshot[1]
    assert window._window_rect == snapshot[2]
    assert window.display_height == snapshot[3]
    assert window.root.geometries[-1] == snapshot[4]
    assert window._consecutive_renderer_failures == 1
    assert window._legacy_fallback is False
    assert window.eye_session.state == "following"
    assert reports == []

    window._apply_image(frames["jump"][0])

    assert window._consecutive_renderer_failures == 0
    assert window.eye_session.state == "following"
    assert bubble.messages == []


def test_headless_success_resets_renderer_failure_streak(monkeypatch):
    window, _root, renderer, _bubble, _compositor, _cursor, frames, _reports = (
        make_headless_window(monkeypatch)
    )
    renderer.failures.append(True)
    with pytest.raises(RuntimeError):
        window._apply_image(frames["jump"][1])
    assert window._consecutive_renderer_failures == 1

    window._apply_image(frames["jump"][2])
    assert window._consecutive_renderer_failures == 0

    renderer.failures.append(True)
    with pytest.raises(RuntimeError):
        window._apply_image(frames["jump"][3])
    assert window._consecutive_renderer_failures == 1
    assert window._rendering_available is True


def test_headless_second_consecutive_renderer_failure_blocks_future_attempts_but_close_works(
    monkeypatch,
):
    window, root, renderer, _bubble, _compositor, _cursor, frames, reports = (
        make_headless_window(monkeypatch)
    )
    renderer.failures.extend([True, True])
    with pytest.raises(RuntimeError):
        window._apply_image(frames["jump"][1])
    attempts_after_first = len(renderer.attempts)

    root.run_next(advance_ms=33)

    assert len(renderer.attempts) == attempts_after_first + 1
    assert window._consecutive_renderer_failures == 2
    assert window._rendering_available is False
    assert window.eye_session.state == "stopped"
    assert window.animation.busy is False
    assert len(reports) == 1

    window.trigger_next_action()
    assert len(renderer.attempts) == attempts_after_first + 1
    window.close()
    assert window.root.destroyed is True


def test_headless_transient_composition_failure_skips_one_frame_then_recovers(
    monkeypatch,
):
    window, root, renderer, bubble, compositor, cursor, frames, reports = (
        make_headless_window(monkeypatch)
    )
    compositor.fail_next = True
    cursor.point = CursorPoint(1900, 0)
    calls_before = len(renderer.attempts)

    root.run_next(advance_ms=33)

    assert window._legacy_fallback is False
    assert window.eye_session.state == "following"
    assert len(renderer.attempts) == calls_before
    assert reports == []

    root.run_next(advance_ms=33)

    assert window.eye_session.state == "following"
    assert len(renderer.attempts) == calls_before + 1
    assert reports == []
    assert bubble.messages == []


def test_default_runtime_failure_reporter_is_non_modal(monkeypatch):
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        "desktop_pet.window.messagebox.showwarning",
        lambda *args, **kwargs: calls.append((*args, kwargs)),
    )
    window = object.__new__(PetWindow)

    window._show_runtime_failure("injected failure")

    assert calls == []


def test_headless_later_action_callback_failure_aborts_owner_before_fallback(
    monkeypatch,
):
    window, root, renderer, bubble, _compositor, _cursor, frames, reports = (
        make_headless_window(monkeypatch)
    )
    window.trigger_next_action()
    assert window.eye_session.state == "playing"
    assert window.animation.busy is True
    renderer.failures.append(True)

    root.run_next(advance_ms=90)

    assert window.animation.busy is False
    assert window.eye_session.state == "stopped"
    assert window._legacy_fallback is True
    assert len(reports) == 1
    window.trigger_next_action()
    assert window._current_image is frames["squash"][0]
    assert window.action_cycle.peek() == "shake"
    assert len(bubble.messages) == 2


def test_headless_cancel_failure_is_routed_to_conservative_terminal_stop(
    monkeypatch,
):
    window, _root, renderer, _bubble, _compositor, _cursor, _frames, reports = (
        make_headless_window(monkeypatch)
    )
    attempts = len(renderer.attempts)

    window._on_action_failed("jump", ActionFailure.CANCEL_REJECTED)

    assert window.eye_session.state == "stopped"
    assert window.animation.busy is False
    assert window._action_ownership_failed is True
    assert len(reports) == 1
    window.trigger_next_action()
    assert len(renderer.attempts) == attempts


def test_headless_close_is_idempotent_ordered_and_stale_callbacks_are_inert(
    monkeypatch,
):
    window, root, renderer, bubble, compositor, _cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )
    window.trigger_next_action()
    stale = root.live()[0][2]
    log: list[str] = []
    eye_stop = window.eye_session.stop
    animation_stop = window.animation.stop
    bubble_destroy = bubble.destroy
    root_destroy = root.destroy
    window.eye_session.stop = lambda: (log.append("eye"), eye_stop())[-1]
    window.animation.stop = lambda: (log.append("animation"), animation_stop())[-1]
    bubble.destroy = lambda: (log.append("bubble"), bubble_destroy())[-1]
    root.destroy = lambda: (log.append("root"), root_destroy())[-1]
    compose_count = len(compositor.calls)
    render_count = len(renderer.attempts)
    phrase_count = len(bubble.messages)

    window.close()
    window.close()
    stale()

    assert log == ["eye", "animation", "bubble", "root"]
    assert root.destroyed is True
    assert len(compositor.calls) == compose_count
    assert len(renderer.attempts) == render_count
    assert len(bubble.messages) == phrase_count
    assert root.live() == []


def test_headless_menu_and_window_protocol_share_close_path(monkeypatch):
    window, root, _renderer, _bubble, _compositor, _cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )

    assert window.menu.commands["退出"].__self__ is window
    assert window.menu.commands["退出"].__func__ is window.close.__func__
    assert root.protocols["WM_DELETE_WINDOW"].__self__ is window
    assert root.protocols["WM_DELETE_WINDOW"].__func__ is window.close.__func__


def test_headless_menu_routes_all_seven_commands_to_exact_runtime_requests(
    monkeypatch,
):
    window, _root, _renderer, _bubble, _compositor, _cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )
    requests: list[tuple[str, str | None]] = []

    class RecordingSession:
        def request_named_action(self, action):
            requests.append(("action", action))
            return window_module.SessionResult.ACCEPTED

        def request_blink(self):
            requests.append(("blink", None))
            return window_module.SessionResult.ACCEPTED

        def request_idle_tilt(self, mode):
            requests.append(("tilt", mode))
            return window_module.SessionResult.ACCEPTED

    window.eye_session = RecordingSession()
    for label in (
        "动作：跳跃",
        "动作：压扁",
        "动作：抖动",
        "眨眼",
        "歪头：向左",
        "歪头：向右",
        "歪头：左到右",
    ):
        window.menu.commands[label]()

    assert requests == [
        ("action", "jump"),
        ("action", "squash"),
        ("action", "shake"),
        ("blink", None),
        ("tilt", "left"),
        ("tilt", "right"),
        ("tilt", "left_arc_right"),
    ]


def test_headless_named_legacy_action_does_not_advance_click_cycle(monkeypatch):
    window, _root, _renderer, _bubble, _compositor, _cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )
    window.eye_session.stop()
    window._legacy_fallback = True
    played: list[str] = []
    monkeypatch.setattr(
        window.animation,
        "play",
        lambda action: played.append(action) or True,
    )

    window.trigger_named_action("shake")

    assert played == ["shake"]
    assert window.action_cycle.peek() == "jump"


def test_headless_probe_presents_center_while_hidden_before_show_and_eye_timer(
    monkeypatch,
):
    window, root, _renderer, _bubble, _compositor, _cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )

    relevant = [
        event
        for event in root.events
        if event in {"compose", "render", "geometry", "deiconify", "lift", "after"}
    ]
    assert relevant == [
        "compose",
        "render",
        "geometry",
        "deiconify",
        "lift",
        "after",
    ]
    assert root.hidden is False
    assert window._current_image is window._neutral_center_frame
    assert len(root.live()) == 1


def test_headless_initial_composition_failure_explicitly_presents_physical_fallback(
    monkeypatch,
):
    compositor = HeadlessCompositor()
    compositor.fail_next = True
    window, root, renderer, _bubble, _compositor, _cursor, frames, reports = (
        make_headless_window(monkeypatch, compositor=compositor)
    )

    assert root.events[:5] == [
        "compose",
        "render",
        "geometry",
        "deiconify",
        "lift",
    ]
    assert window._current_image is frames["jump"][0]
    assert renderer.successes[-1][0] is window._resized_image
    assert window.eye_session.state == "disabled"
    assert root.live() == []
    assert len(reports) == 1


def test_headless_first_renderer_failure_without_snapshot_aborts_hidden_startup(
    monkeypatch,
):
    root, renderer, bubbles, _reports, frames, compositor, cursor, clock = (
        prepare_headless(monkeypatch)
    )
    renderer.failures.append(True)

    with pytest.raises(RuntimeError, match="injected renderer failure"):
        PetWindow(
            root,
            frames,
            renderer_factory=lambda _hwnd: renderer,
            compositor=compositor,
            cursor_provider=cursor,
            runtime_failure_reporter=lambda _message: None,
            clock=clock,
        )

    assert root.hidden is True
    assert "deiconify" not in root.events
    assert bubbles[0].destroyed is True
    assert renderer.successes == []


def test_headless_partial_init_failure_cleans_animation_then_bubble(monkeypatch):
    root, renderer, bubbles, _reports, frames, _compositor, cursor, clock = (
        prepare_headless(monkeypatch)
    )
    real_animation = window_module.AnimationController

    class RecordingAnimation(real_animation):
        def stop(self):
            root.events.append("animation-stop")
            super().stop()

    class InvalidCompositor(HeadlessCompositor):
        source_size = (0, 768)

    invalid = InvalidCompositor()
    invalid.events = root.events
    monkeypatch.setattr(window_module, "AnimationController", RecordingAnimation)

    with pytest.raises(ValueError, match="source size must be positive"):
        PetWindow(
            root,
            frames,
            renderer_factory=lambda _hwnd: renderer,
            compositor=invalid,
            cursor_provider=cursor,
            runtime_failure_reporter=lambda _message: None,
            clock=clock,
        )

    assert root.events[-2:] == ["animation-stop", "bubble-destroy"]
    assert bubbles[0].destroyed is True


def test_headless_initial_scheduler_failure_uses_fallback_and_stale_callback_is_inert(
    monkeypatch,
):
    root, renderer, bubbles, reports, frames, compositor, cursor, clock = (
        prepare_headless(monkeypatch)
    )
    real_animation = window_module.AnimationController
    real_runtime = window_module.RuntimeEyeSession

    class RecordingAnimation(real_animation):
        def stop(self):
            root.events.append("animation-stop")
            super().stop()

    class RecordingRuntime(real_runtime):
        def stop(self):
            root.events.append("eye-stop")
            super().stop()

    monkeypatch.setattr(window_module, "AnimationController", RecordingAnimation)
    monkeypatch.setattr(window_module, "RuntimeEyeSession", RecordingRuntime)
    root.after_raises_after_queue = True

    window = PetWindow(
        root,
        frames,
        renderer_factory=lambda _hwnd: renderer,
        compositor=compositor,
        cursor_provider=cursor,
        runtime_failure_reporter=reports.append,
        clock=clock,
    )

    assert window.eye_session.state == "disabled"
    assert window._current_image is frames["jump"][0]
    assert root.hidden is False
    assert len(reports) == 1
    assert bubbles[0].destroyed is False
    stale = root.pending[-1][2]
    render_count = len(renderer.attempts)
    compose_count = len(compositor.calls)
    stale()
    assert len(renderer.attempts) == render_count
    assert len(compositor.calls) == compose_count

    window.close()
    assert root.events[-4:] == [
        "eye-stop",
        "animation-stop",
        "bubble-destroy",
        "root-destroy",
    ]
    assert bubbles[0].destroyed is True


@pytest.mark.parametrize("operation", ["apply", "move"])
def test_headless_geometry_failure_restores_exact_last_presentation(
    monkeypatch, operation,
):
    window, root, renderer, _bubble, _compositor, _cursor, frames, _reports = (
        make_headless_window(monkeypatch)
    )
    snapshot = (
        window._current_image,
        window._resized_image,
        window._window_rect,
        window.display_height,
        root.current_geometry,
    )
    root.geometry_failures.extend([True, False])

    with pytest.raises(RuntimeError, match="injected geometry failure"):
        if operation == "apply":
            window._apply_image(frames["jump"][2], requested_height=420)
        else:
            window._move_to(250, 180)

    assert window._current_image is snapshot[0]
    assert window._resized_image is snapshot[1]
    assert window._window_rect == snapshot[2]
    assert window.display_height == snapshot[3]
    assert root.current_geometry == snapshot[4]
    restored, x, y = renderer.attempts[-1]
    assert restored is snapshot[1]
    assert (x, y) == (snapshot[2].x, snapshot[2].y)
    assert window._legacy_fallback is True


@pytest.mark.parametrize("restore_site", ["renderer", "geometry"])
def test_headless_geometry_rollback_failure_immediately_disables_rendering(
    monkeypatch, restore_site,
):
    window, root, renderer, _bubble, _compositor, _cursor, frames, _reports = (
        make_headless_window(monkeypatch)
    )
    root.geometry_failures.append(True)
    if restore_site == "renderer":
        renderer.failures.extend([False, True])
    else:
        renderer.failures.extend([False, False])
        root.geometry_failures.append(True)

    with pytest.raises(RuntimeError):
        window._apply_image(frames["jump"][2])

    assert window._rendering_available is False
    assert window.eye_session.state == "stopped"
    assert window.animation.busy is False
    attempts = len(renderer.attempts)
    window.trigger_next_action()
    assert len(renderer.attempts) == attempts


def test_headless_geometry_rollback_does_not_reset_renderer_failure_streak(
    monkeypatch,
):
    window, root, renderer, _bubble, _compositor, _cursor, frames, _reports = (
        make_headless_window(monkeypatch)
    )
    renderer.failures.append(True)
    with pytest.raises(RuntimeError):
        window._apply_image(frames["jump"][1])
    assert window._consecutive_renderer_failures == 1
    root.geometry_failures.extend([True, False])
    renderer.failures.extend([False, False])
    with pytest.raises(RuntimeError, match="geometry"):
        window._apply_image(frames["jump"][2])
    assert window._consecutive_renderer_failures == 1

    renderer.failures.append(True)
    with pytest.raises(RuntimeError):
        window._apply_image(frames["jump"][3])
    assert window._consecutive_renderer_failures == 2
    assert window._rendering_available is False


def test_headless_action_geometry_failure_restores_then_allows_physical_fallback(
    monkeypatch,
):
    window, root, renderer, _bubble, _compositor, _cursor, frames, _reports = (
        make_headless_window(monkeypatch)
    )
    snapshot = (
        window._current_image,
        window._resized_image,
        window._window_rect,
        window.display_height,
        root.current_geometry,
    )
    window.trigger_next_action()
    root.geometry_failures.extend([True, False])

    root.run_next(advance_ms=90)

    assert window.animation.busy is False
    assert window.eye_session.state == "stopped"
    assert window._legacy_fallback is True
    assert window._current_image is snapshot[0]
    assert window._resized_image is snapshot[1]
    assert window._window_rect == snapshot[2]
    assert window.display_height == snapshot[3]
    assert root.current_geometry == snapshot[4]
    assert renderer.attempts[-1][0] is snapshot[1]
    window.trigger_next_action()
    assert window._current_image is frames["squash"][0]


def test_headless_real_cancel_exception_is_terminal_and_never_enters_fallback(
    monkeypatch,
):
    window, root, renderer, _bubble, _compositor, _cursor, frames, reports = (
        make_headless_window(monkeypatch)
    )
    window.trigger_next_action()
    assert window.animation.busy is True
    root.cancel_error = RuntimeError("injected after_cancel failure")
    renderer.failures.append(True)

    window.set_display_height(420)

    assert window.animation.busy is False
    assert window.eye_session.state == "stopped"
    assert window._action_ownership_failed is True
    assert window._legacy_fallback is False
    assert reports == ["动作播放已安全停止；请重启桌面宠物。"]
    attempts = len(renderer.attempts)
    window.trigger_next_action()
    assert len(renderer.attempts) == attempts
    assert window._current_image is not frames["squash"][0]


def test_headless_legacy_commit_mismatch_clears_active_action_adapter_state(
    monkeypatch,
):
    window, _root, _renderer, _bubble, _compositor, _cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )
    window.eye_session.stop()
    window._legacy_fallback = True

    def reject_commit(_expected):
        raise ValueError("injected commit mismatch")

    monkeypatch.setattr(window.action_cycle, "commit", reject_commit)
    window.trigger_next_action()

    assert window.animation.busy is False
    assert window._active_animation_action is None


def test_headless_public_drag_and_resize_preserve_negative_monitor_geometry(
    monkeypatch,
):
    window, _root, renderer, _bubble, _compositor, _cursor, _frames, _reports = (
        make_headless_window(monkeypatch)
    )
    area = Rect(-1920, -1080, 3840, 2160)
    monkeypatch.setattr(window, "work_area_for", lambda _rect: area)
    before = window.pet_rect()
    window._on_left_press(SimpleNamespace(x_root=100, y_root=100))

    window._on_left_motion(SimpleNamespace(x_root=-2100, y_root=-1000))
    dragged = window.pet_rect()
    window.set_display_height(520)

    assert dragged.x == before.x - 2200
    assert dragged.y == before.y - 1100
    assert dragged.x < 0 and dragged.y < 0
    assert window.pet_rect().x < 0 and window.pet_rect().y < 0
    assert window.display_height == 520
    assert renderer.successes[-1][1:] == (
        window.pet_rect().x,
        window.pet_rect().y,
    )

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from random import Random
import tkinter as tk
from typing import Callable, Protocol, Sequence

from PIL import Image

from .animation import AnimationController
from .bubble import BubbleWindow
from .layered_window import LayeredWindowRenderer
from .model import ActionCycle, Rect, choose_phrase, clamp_height, format_position


SIZE_PRESETS = {"小": 180, "中": 280, "大": 420}
CLICK_THRESHOLD = 8
MONITOR_DEFAULTTONEAREST = 2


class WinRect(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", WinRect),
        ("rcWork", WinRect),
        ("dwFlags", wintypes.DWORD),
    ]


def constrain_rect_to_area(rect: Rect, area: Rect) -> Rect:
    if rect.width >= area.width:
        x = area.x
    else:
        x = min(max(rect.x, area.x), area.right - rect.width)
    if rect.height >= area.height:
        y = area.y
    else:
        y = min(max(rect.y, area.y), area.bottom - rect.height)
    return Rect(x, y, rect.width, rect.height)


def _monitor_work_area(user32, monitor: int, fallback: Rect) -> Rect:
    if not monitor:
        return fallback
    get_monitor_info = user32.GetMonitorInfoW
    get_monitor_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    get_monitor_info.restype = wintypes.BOOL
    info = MonitorInfo()
    info.cbSize = ctypes.sizeof(MonitorInfo)
    if not get_monitor_info(monitor, ctypes.byref(info)):
        return fallback
    work = info.rcWork
    return Rect(work.left, work.top, work.right - work.left, work.bottom - work.top)


class Renderer(Protocol):
    def render(self, image: Image.Image, x: int, y: int) -> None: ...

    def set_topmost(self, enabled: bool) -> None: ...


RendererFactory = Callable[[int], Renderer]


def screen_work_area(window_id: int, fallback: Rect) -> Rect:
    if os.name != "nt":
        return fallback
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    monitor_from_window = user32.MonitorFromWindow
    monitor_from_window.argtypes = [wintypes.HWND, wintypes.DWORD]
    monitor_from_window.restype = wintypes.HANDLE
    monitor = monitor_from_window(window_id, MONITOR_DEFAULTTONEAREST)
    return _monitor_work_area(user32, monitor, fallback)


def screen_work_area_for_rect(rect: Rect, fallback: Rect) -> Rect:
    if os.name != "nt":
        return fallback
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    monitor_from_rect = user32.MonitorFromRect
    monitor_from_rect.argtypes = [ctypes.POINTER(WinRect), wintypes.DWORD]
    monitor_from_rect.restype = wintypes.HANDLE
    native_rect = WinRect(rect.x, rect.y, rect.right, rect.bottom)
    monitor = monitor_from_rect(
        ctypes.byref(native_rect), MONITOR_DEFAULTTONEAREST
    )
    return _monitor_work_area(user32, monitor, fallback)


class PetWindow:
    def __init__(
        self,
        root: tk.Tk,
        frames: dict[str, Sequence[Image.Image]],
        renderer_factory: RendererFactory = LayeredWindowRenderer,
    ) -> None:
        self.root = root
        self.frames = frames
        self.display_height = 280
        self.always_on_top = True
        self.action_cycle = ActionCycle()
        self._rng = Random()
        self._current_image = frames["jump"][0]
        self._resized_image = self._current_image
        self._press_pointer: tuple[int, int] | None = None
        self._press_window: tuple[int, int] | None = None

        root.title("桌面宠物")
        root.overrideredirect(True)
        root.configure(cursor="hand2")
        root.attributes("-topmost", True)
        root.update_idletasks()
        self._window_rect = Rect(
            root.winfo_x(),
            root.winfo_y(),
            1,
            self.display_height,
        )
        self.renderer = renderer_factory(root.winfo_id())
        self.renderer.set_topmost(True)
        self.bubble = BubbleWindow(root)
        self.animation = AnimationController(
            {action: len(action_frames) for action, action_frames in frames.items()},
            root.after,
            self.show_frame,
            self._animation_finished,
        )
        self._topmost_var = tk.BooleanVar(root, value=True)
        self.menu = self._create_menu()
        self._bind_events()
        self._apply_image(self._current_image)
        self.show_at_default_position()

    def _create_menu(self) -> tk.Menu:
        menu = tk.Menu(self.root, tearoff=False)
        for label, height in SIZE_PRESETS.items():
            menu.add_command(
                label=label,
                command=lambda value=height: self.set_display_height(value),
            )
        menu.add_separator()
        menu.add_checkbutton(
            label="始终置顶",
            variable=self._topmost_var,
            command=lambda: self.set_always_on_top(self._topmost_var.get()),
        )
        menu.add_separator()
        menu.add_command(label="退出", command=self.root.destroy)
        return menu

    def _bind_events(self) -> None:
        self.root.bind("<ButtonPress-1>", self._on_left_press)
        self.root.bind("<B1-Motion>", self._on_left_motion)
        self.root.bind("<ButtonRelease-1>", self._on_left_release)
        self.root.bind("<Button-3>", self._on_context_menu)
        self.root.bind("<MouseWheel>", self._on_wheel)

    def _anchor(self) -> tuple[int, int]:
        return (
            self._window_rect.x + self._window_rect.width // 2,
            self._window_rect.y + self._window_rect.height,
        )

    def _apply_image(
        self,
        image: Image.Image,
        anchor: tuple[int, int] | None = None,
    ) -> None:
        width = max(1, round(image.width * self.display_height / image.height))
        if anchor is None:
            x, y = self._window_rect.x, self._window_rect.y
        else:
            x = anchor[0] - width // 2
            y = anchor[1] - self.display_height
        proposed = Rect(x, y, width, self.display_height)
        area = self.work_area_for(proposed)
        max_height_by_width = max(
            1, area.width * image.height // image.width
        )
        fitted_height = max(
            1,
            min(
                self.display_height,
                max(1, area.height),
                max_height_by_width,
            ),
        )
        if fitted_height != self.display_height:
            self.display_height = fitted_height
            width = max(1, round(image.width * fitted_height / image.height))
            if anchor is not None:
                x = anchor[0] - width // 2
                y = anchor[1] - fitted_height
            proposed = Rect(x, y, width, fitted_height)
        self._resized_image = image.convert("RGBA").resize(
            (width, self.display_height), Image.Resampling.LANCZOS
        )
        self._window_rect = constrain_rect_to_area(
            proposed, area
        )
        x, y = self._window_rect.x, self._window_rect.y
        self.root.geometry(
            f"{width}x{self.display_height}{format_position(x, y)}"
        )
        self.renderer.render(self._resized_image, x, y)

    def _move_to(self, x: int, y: int) -> None:
        proposed = Rect(x, y, self._window_rect.width, self._window_rect.height)
        self._window_rect = constrain_rect_to_area(
            proposed, self.work_area_for(proposed)
        )
        x, y = self._window_rect.x, self._window_rect.y
        self.root.geometry(
            f"{self._window_rect.width}x{self._window_rect.height}"
            f"{format_position(x, y)}"
        )
        self.renderer.render(self._resized_image, x, y)

    def _fallback_screen(self) -> Rect:
        return Rect(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def current_screen(self) -> Rect:
        self.root.update_idletasks()
        return screen_work_area(self.root.winfo_id(), self._fallback_screen())

    def work_area_for(self, rect: Rect) -> Rect:
        return screen_work_area_for_rect(rect, self._fallback_screen())

    def pet_rect(self) -> Rect:
        return self._window_rect

    def show_at_default_position(self) -> None:
        area = self.current_screen()
        x = area.right - self._window_rect.width - 36
        y = area.bottom - self._window_rect.height - 36
        self._move_to(x, y)
        self.root.deiconify()
        self.root.lift()

    def set_display_height(self, value: int) -> None:
        anchor = self._anchor()
        self.display_height = clamp_height(value)
        self._apply_image(self._current_image, anchor)
        self.bubble.reposition(self.pet_rect(), self.current_screen())

    def set_always_on_top(self, enabled: bool) -> None:
        self.always_on_top = bool(enabled)
        self._topmost_var.set(self.always_on_top)
        self.root.attributes("-topmost", self.always_on_top)
        self.renderer.set_topmost(self.always_on_top)
        self.bubble.set_always_on_top(self.always_on_top)
        self.root.lift()

    def handle_left_release(
        self,
        press: tuple[int, int],
        release: tuple[int, int],
    ) -> None:
        distance = abs(release[0] - press[0]) + abs(release[1] - press[1])
        if distance < CLICK_THRESHOLD:
            self.trigger_next_action()

    def trigger_next_action(self) -> None:
        if self.animation.busy:
            return
        action = self.action_cycle.next()
        if not self.animation.play(action):
            return
        phrase = choose_phrase(action, self._rng)
        self.bubble.show_message(phrase, self.pet_rect(), self.current_screen())

    def show_frame(self, action: str, index: int) -> None:
        self._current_image = self.frames[action][index]
        self._apply_image(self._current_image, self._anchor())

    def _animation_finished(self, _action: str) -> None:
        return

    def _on_left_press(self, event: tk.Event) -> None:
        self._press_pointer = (event.x_root, event.y_root)
        self._press_window = (self._window_rect.x, self._window_rect.y)

    def _on_left_motion(self, event: tk.Event) -> None:
        if self._press_pointer is None or self._press_window is None:
            return
        delta_x = event.x_root - self._press_pointer[0]
        delta_y = event.y_root - self._press_pointer[1]
        if abs(delta_x) + abs(delta_y) < CLICK_THRESHOLD:
            return
        self._move_to(
            self._press_window[0] + delta_x,
            self._press_window[1] + delta_y,
        )
        self.bubble.reposition(self.pet_rect(), self.current_screen())

    def _on_left_release(self, event: tk.Event) -> None:
        if self._press_pointer is not None:
            self.handle_left_release(
                self._press_pointer,
                (event.x_root, event.y_root),
            )
        self._press_pointer = None
        self._press_window = None

    def _on_context_menu(self, event: tk.Event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _on_wheel(self, event: tk.Event) -> None:
        delta = 24 if event.delta > 0 else -24
        self.set_display_height(self.display_height + delta)

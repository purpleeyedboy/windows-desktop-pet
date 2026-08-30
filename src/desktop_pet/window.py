from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from random import Random
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Protocol, Sequence

from PIL import Image

from .animation import AnimationController
from .bubble import BubbleWindow
from .dialogue import DialogueChooser, load_phrase_pools
from .eye_follow import CursorProvider
from .eye_runtime import (
    ActionFailure,
    Compositor,
    RuntimeEyeSession,
    SessionResult,
)
from .layered_window import LayeredWindowRenderer
from .model import ActionCycle, Rect, clamp_height, format_position


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
RuntimeFailureReporter = Callable[[str], None]


class _CachedCenterCompositor:
    """Keep one literal center object while delegating every moving pose."""

    def __init__(self, compositor: Compositor) -> None:
        self._compositor = compositor
        self.source_size = compositor.source_size
        self.eye_midpoint = compositor.eye_midpoint
        self.center_frame: object | None = None

    def compose(self, eye_x: float, eye_y: float) -> object:
        if eye_x == 0.0 and eye_y == 0.0:
            if self.center_frame is None:
                self.center_frame = self._compositor.compose(0.0, 0.0)
            return self.center_frame
        return self._compositor.compose(eye_x, eye_y)


@dataclass(frozen=True)
class _PresentationSnapshot:
    source_image: Image.Image
    resized_image: Image.Image
    rect: Rect
    display_height: int
    geometry: str


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
        *,
        compositor: Compositor | None = None,
        cursor_provider: CursorProvider | None = None,
        legacy_mode: bool = False,
        runtime_failure_reporter: RuntimeFailureReporter | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if legacy_mode:
            if compositor is not None or cursor_provider is not None:
                raise ValueError("legacy mode cannot accept eye-follow dependencies")
        elif compositor is None or cursor_provider is None:
            raise ValueError(
                "source-probe construction requires compositor and cursor provider"
            )

        self.root = root
        self.frames = frames
        self.display_height = 280
        self.always_on_top = True
        self.action_cycle = ActionCycle()
        self._rng = Random()
        self.dialogue = DialogueChooser(load_phrase_pools(), self._rng)
        self._current_image = frames["jump"][0]
        self._resized_image = self._current_image
        self._press_pointer: tuple[int, int] | None = None
        self._press_window: tuple[int, int] | None = None
        self._closed = False
        self._legacy_fallback = bool(legacy_mode)
        self._rendering_available = True
        self._consecutive_renderer_failures = 0
        self._runtime_failure_reported = False
        self._action_ownership_failed = False
        self._active_animation_action: str | None = None
        self._runtime_failure_reporter = (
            runtime_failure_reporter or self._show_runtime_failure
        )
        self._neutral_center_frame: object | None = None
        self.eye_session: RuntimeEyeSession | None = None
        self._presentation_snapshot: _PresentationSnapshot | None = None
        self._startup_presentation_error: Exception | None = None
        self._constructing = True
        self._pending_runtime_failure = False
        self._window_shown = False
        self._window_rect = Rect(
            root.winfo_x(),
            root.winfo_y(),
            1,
            self.display_height,
        )

        try:
            root.title("桌面宠物")
            root.overrideredirect(True)
            root.configure(cursor="hand2")
            root.attributes("-topmost", True)
            root.update_idletasks()
            self.renderer = renderer_factory(root.winfo_id())
            self.renderer.set_topmost(True)
            self.bubble = BubbleWindow(root, renderer_factory=renderer_factory)
            self.animation = AnimationController(
                {
                    action: len(action_frames)
                    for action, action_frames in frames.items()
                },
                self._schedule_animation,
                self._show_animation_frame,
                self._animation_finished,
                cancel=self._cancel_after,
            )
            self._topmost_var = tk.BooleanVar(root, value=True)
            self.menu = self._create_menu()
            self._bind_events()
            root.protocol("WM_DELETE_WINDOW", self.close)
            self._prepare_default_rect(self._current_image)

            cached_compositor: _CachedCenterCompositor | None = None
            if not legacy_mode:
                cached_compositor = _CachedCenterCompositor(compositor)
                self.eye_session = RuntimeEyeSession(
                    compositor=cached_compositor,
                    cursor_provider=cursor_provider,
                    rect_provider=lambda: self._window_rect,
                    display=self._display_eye_frame,
                    scheduler=root.after,
                    cancel=self._cancel_after,
                    clock=clock,
                    on_disabled=self._on_eye_disabled,
                    action_cycle=self.action_cycle,
                    physical_frames=frames,
                    play_action=self._play_action,
                    cancel_action=self._cancel_action,
                    choose_phrase=self.dialogue.choose,
                    present_phrase=self._present_phrase,
                    on_action_failed=self._on_action_failed,
                )
                result = self.eye_session.start()
                self._neutral_center_frame = cached_compositor.center_frame
                if self._startup_presentation_error is not None:
                    raise self._startup_presentation_error
                if result is SessionResult.FALLBACK:
                    self._apply_image(self.frames["jump"][0])
                    self._show_window()
            else:
                self._apply_image(self._current_image)
                self._show_window()

            self._constructing = False
            if self._pending_runtime_failure:
                self._report_runtime_failure_once()
        except Exception:
            self._cleanup_partial_construction()
            raise

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
        menu.add_command(label="退出", command=self.close)
        return menu

    def _bind_events(self) -> None:
        self.root.bind("<ButtonPress-1>", self._on_left_press)
        self.root.bind("<B1-Motion>", self._on_left_motion)
        self.root.bind("<ButtonRelease-1>", self._on_left_release)
        self.root.bind("<Button-3>", self._on_context_menu)
        self.root.bind("<MouseWheel>", self._on_wheel)

    def _prepare_default_rect(self, image: Image.Image) -> None:
        area = self.current_screen()
        width = max(
            1,
            round(image.width * self.display_height / image.height),
        )
        self._window_rect = Rect(
            area.right - width - 36,
            area.bottom - self.display_height - 36,
            width,
            self.display_height,
        )

    def _show_window(self) -> None:
        if self._window_shown:
            return
        self.root.deiconify()
        self.root.lift()
        self._window_shown = True

    def _cleanup_partial_construction(self) -> None:
        self._closed = True
        session = self.eye_session
        if session is not None:
            try:
                session.stop()
            except Exception:
                pass
        animation = getattr(self, "animation", None)
        if animation is not None:
            try:
                animation.stop()
            except Exception:
                pass
        bubble = getattr(self, "bubble", None)
        if bubble is not None:
            try:
                bubble.destroy()
            except Exception:
                pass

    def _anchor(self) -> tuple[int, int]:
        return (
            self._window_rect.x + self._window_rect.width // 2,
            self._window_rect.y + self._window_rect.height,
        )

    def _apply_image(
        self,
        image: Image.Image,
        anchor: tuple[int, int] | None = None,
        *,
        requested_height: int | None = None,
    ) -> None:
        if self._closed or not self._rendering_available:
            raise RuntimeError("pet rendering is unavailable")
        target_height = (
            self.display_height
            if requested_height is None
            else clamp_height(requested_height)
        )
        width = max(1, round(image.width * target_height / image.height))
        if anchor is None:
            x, y = self._window_rect.x, self._window_rect.y
        else:
            x = anchor[0] - width // 2
            y = anchor[1] - target_height
        proposed = Rect(x, y, width, target_height)
        area = self.work_area_for(proposed)
        max_height_by_width = max(
            1, area.width * image.height // image.width
        )
        fitted_height = max(
            1,
            min(
                target_height,
                max(1, area.height),
                max_height_by_width,
            ),
        )
        if fitted_height != target_height:
            width = max(1, round(image.width * fitted_height / image.height))
            if anchor is not None:
                x = anchor[0] - width // 2
                y = anchor[1] - fitted_height
            proposed = Rect(x, y, width, fitted_height)
        resized_image = image.convert("RGBA").resize(
            (width, fitted_height), Image.Resampling.LANCZOS
        )
        window_rect = constrain_rect_to_area(proposed, area)
        self._present_candidate(
            image,
            resized_image,
            window_rect,
            fitted_height,
        )

    def _move_to(self, x: int, y: int) -> None:
        if self._closed or not self._rendering_available:
            raise RuntimeError("pet rendering is unavailable")
        proposed = Rect(x, y, self._window_rect.width, self._window_rect.height)
        window_rect = constrain_rect_to_area(
            proposed, self.work_area_for(proposed)
        )
        self._present_candidate(
            self._current_image,
            self._resized_image,
            window_rect,
            self.display_height,
        )

    def _present_candidate(
        self,
        source_image: Image.Image,
        resized_image: Image.Image,
        rect: Rect,
        display_height: int,
    ) -> None:
        geometry = (
            f"{rect.width}x{rect.height}"
            f"{format_position(rect.x, rect.y)}"
        )
        self._render_candidate(resized_image, rect.x, rect.y)
        try:
            self.root.geometry(geometry)
        except Exception as error:
            self._handle_geometry_failure(error)
            raise
        self._current_image = source_image
        self._resized_image = resized_image
        self._window_rect = rect
        self.display_height = display_height
        self._presentation_snapshot = _PresentationSnapshot(
            source_image,
            resized_image,
            rect,
            display_height,
            geometry,
        )
        self._consecutive_renderer_failures = 0

    def _render_candidate(self, image: Image.Image, x: int, y: int) -> None:
        if self._closed or not self._rendering_available:
            raise RuntimeError("pet rendering is unavailable")
        try:
            self.renderer.render(image, x, y)
        except Exception as error:
            self._consecutive_renderer_failures += 1
            if self._presentation_snapshot is None:
                self._startup_presentation_error = error
            elif self._consecutive_renderer_failures >= 2:
                self._mark_rendering_unavailable()
            else:
                self._activate_legacy_fallback()
            if not self._constructing:
                self._report_runtime_failure_once()
            raise

    def _handle_geometry_failure(self, error: Exception) -> None:
        snapshot = self._presentation_snapshot
        if snapshot is None:
            self._startup_presentation_error = error
            self._mark_rendering_unavailable()
            return
        try:
            self.renderer.render(
                snapshot.resized_image,
                snapshot.rect.x,
                snapshot.rect.y,
            )
            self.root.geometry(snapshot.geometry)
        except Exception:
            self._consecutive_renderer_failures = max(
                2, self._consecutive_renderer_failures
            )
            self._mark_rendering_unavailable()
        else:
            self._activate_legacy_fallback()
        if not self._constructing:
            self._report_runtime_failure_once()

    def _mark_rendering_unavailable(self) -> None:
        if not self._rendering_available:
            return
        self._rendering_available = False
        if self.eye_session is not None:
            self.eye_session.stop()
        animation = getattr(self, "animation", None)
        if animation is not None:
            animation.stop()

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
        if self._closed or not self._rendering_available:
            return
        anchor = self._anchor()
        try:
            self._apply_image(
                self._current_image,
                anchor,
                requested_height=clamp_height(value),
            )
        except Exception:
            return
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
        if (
            self._closed
            or not self._rendering_available
            or self._action_ownership_failed
            or self.animation.busy
        ):
            return
        if self.eye_session is not None and not self._legacy_fallback:
            result = self.eye_session.request_action()
            if result is not SessionResult.FALLBACK:
                return
            self._activate_legacy_fallback()
        self._trigger_legacy_action()

    def _trigger_legacy_action(self) -> None:
        if self.animation.busy:
            return
        action = self.action_cycle.peek()
        try:
            accepted = self._play_action(action)
        except Exception:
            self._handle_action_callback_failure()
            return
        if accepted is not True:
            return
        try:
            self.action_cycle.commit(action)
        except Exception:
            if self._cancel_action(action) is not True:
                self._on_action_failed(action, ActionFailure.CANCEL_REJECTED)
            return
        try:
            phrase = self.dialogue.choose(action)
            self._present_phrase(phrase)
        except Exception:
            pass

    def show_frame(self, action: str, index: int) -> None:
        self._show_animation_frame(action, index)

    def _show_animation_frame(self, action: str, index: int) -> None:
        if self._closed or not self._rendering_available:
            raise RuntimeError("pet rendering is unavailable")
        self._active_animation_action = action
        if self._legacy_fallback or self.eye_session is None:
            image = self.frames[action][index]
        else:
            image = self.eye_session.logical_frame(action, index)
        if (
            index == 0
            and self._presentation_snapshot is not None
            and image is self._current_image
        ):
            return
        self._apply_image(image, self._anchor())

    def _animation_finished(self, action: str) -> None:
        self._active_animation_action = None
        if self._closed or self._legacy_fallback or self.eye_session is None:
            return
        self.eye_session.animation_finished(action)

    def _play_action(self, action: str) -> bool:
        try:
            accepted = self.animation.play(action)
        except Exception:
            if not self.animation.busy:
                self._active_animation_action = None
            raise
        if accepted is not True and not self.animation.busy:
            self._active_animation_action = None
        return accepted

    def _cancel_action(self, action: str) -> bool:
        cancelled = self.animation.cancel_current(action)
        if cancelled is True:
            self._active_animation_action = None
        return cancelled

    def _display_eye_frame(self, frame: object) -> None:
        if not isinstance(frame, Image.Image):
            raise TypeError("eye compositor must return a Pillow image")
        self._apply_image(frame, self._anchor())
        if self._neutral_center_frame is None:
            self._neutral_center_frame = frame
        if self._constructing and not self._window_shown:
            try:
                self._show_window()
            except Exception as error:
                self._startup_presentation_error = error
                raise

    def _present_phrase(self, phrase: str) -> None:
        if self._closed:
            return
        self.bubble.show_message(
            phrase,
            self.pet_rect(),
            self.current_screen(),
        )

    def _schedule_animation(
        self, delay_ms: int, callback: Callable[[], None]
    ) -> object:
        def guarded_callback() -> None:
            if self._closed:
                return
            try:
                callback()
            except Exception:
                self._handle_action_callback_failure()

        return self.root.after(delay_ms, guarded_callback)

    def _cancel_after(self, token: object) -> None:
        try:
            self.root.after_cancel(token)
        except tk.TclError:
            pass

    def _on_eye_disabled(self) -> None:
        self._legacy_fallback = True
        if self._constructing:
            self._pending_runtime_failure = True
        else:
            self._report_runtime_failure_once()

    def _activate_legacy_fallback(self) -> None:
        if self._closed or not self._rendering_available:
            return
        if self.animation.busy:
            action = self._active_animation_action
            try:
                cancelled = (
                    action is not None and self._cancel_action(action)
                )
            except Exception:
                cancelled = False
            if cancelled is not True:
                self._on_action_failed(
                    action or "unknown",
                    ActionFailure.CANCEL_REJECTED,
                )
                return
        self._legacy_fallback = True
        if self.eye_session is not None and self.eye_session.state not in (
            "disabled",
            "stopped",
        ):
            self.eye_session.stop()

    def _handle_action_callback_failure(self) -> None:
        if self._closed or not self._rendering_available:
            return
        if not self.animation.busy:
            self._active_animation_action = None
        if self.eye_session is not None:
            self.eye_session.stop()
        self._legacy_fallback = True
        self._report_runtime_failure_once()

    def _on_action_failed(
        self, _action: str, _failure: ActionFailure
    ) -> None:
        if self._closed:
            return
        self._action_ownership_failed = True
        if self.eye_session is not None:
            self.eye_session.stop()
        self.animation.stop()
        self._report_runtime_failure_once(
            "动作播放已安全停止；请重启桌面宠物。"
        )

    def _show_runtime_failure(self, message: str) -> None:
        messagebox.showwarning(
            "桌面宠物提示",
            message,
            parent=self.root,
        )

    def _report_runtime_failure_once(
        self,
        message: str = "眼睛跟随已停用，点击动作仍可继续。",
    ) -> None:
        if self._runtime_failure_reported:
            return
        self._runtime_failure_reported = True
        try:
            self._runtime_failure_reporter(message)
        except Exception:
            pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.eye_session is not None:
            self.eye_session.stop()
        self.animation.stop()
        self.bubble.destroy()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

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
        try:
            self._move_to(
                self._press_window[0] + delta_x,
                self._press_window[1] + delta_y,
            )
        except Exception:
            return
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

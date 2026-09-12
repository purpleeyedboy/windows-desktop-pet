from __future__ import annotations

import ctypes
import os
import json
from datetime import date
from pathlib import Path
import sys
import traceback
import tkinter as tk
from tkinter import messagebox

from .assets import load_frames, load_head_neck_compositor, load_playback_sequences
from .eye_follow import Win32CursorProvider
from .foundation.config import BuildInfo, FeatureConfig
from .foundation.services import DEFAULT_STATE, ApplicationServices, create_application_services
from .foundation.runtime import Activity
from .window import PetWindow
from .expectation_window import ExpectationWindow
from .drag_runtime import ExpectationDragDropService
from .foundation_contract import SharedHungerState
from .hunger import HungerService


def load_expectation_build_info():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    data = json.loads((root / "DRAG_EXPECTATION_BUILD_INFO.json").read_text(encoding="utf-8"))
    return BuildInfo(data["version"], date.fromisoformat(data["date"]), data["git_short_hash"],
                     data["foundation_commit"], FeatureConfig(
                         enabled_features=tuple(data["enabled_features"]),
                         test_build=bool(data["test_build"]),
                         debug_enabled=bool(data["test_build"]),
                         debug_menu_enabled=bool(data["debug_menu"])))


ERROR_ALREADY_EXISTS = 183


def build_mutex_name() -> str:
    username = os.environ.get("USERNAME", "user")
    return rf"Local\DesktopCatPet-{username}"


class SingleInstanceMutex:
    def __init__(self, name: str) -> None:
        self.name = name
        self._handle: int | None = None
        self._kernel32 = None

    def acquire(self) -> bool:
        if os.name != "nt":
            self._handle = -1
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        create_mutex.restype = ctypes.c_void_p
        ctypes.set_last_error(0)
        handle = create_mutex(None, False, self.name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._kernel32 = kernel32
        self._handle = int(handle)
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS

    def close(self) -> None:
        if self._handle is None:
            return
        if os.name == "nt" and self._handle != -1 and self._kernel32 is not None:
            self._kernel32.CloseHandle(ctypes.c_void_p(self._handle))
        self._handle = None


def notify_existing_instance(build_info: BuildInfo) -> None:
    if os.name == "nt":
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        hwnd = user32.FindWindowW(None, "桌面宠物")
        existing = "未知旧实例"
        if not hwnd:
            found: list[int] = []
            callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows.argtypes = [callback_type, ctypes.c_void_p]
            user32.EnumWindows.restype = ctypes.c_bool

            def visit(candidate, _parameter):
                buffer = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(candidate, buffer, len(buffer))
                if buffer.value.startswith("桌面宠物 V2.1-"):
                    found.append(int(candidate))
                    return False
                return True

            user32.EnumWindows(callback_type(visit), None)
            hwnd = found[0] if found else None
        if hwnd:
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buffer, len(buffer))
            existing = buffer.value or existing
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
        message = (
            f"桌面宠物已在运行：{existing}\n"
            f"请求版本：{build_info.product_version} ({build_info.git_short_hash})\n"
            "本次新版本未启动。"
        )
        user32.MessageBoxW(None, message, "桌面宠物正在运行", 0x40)


def enable_per_monitor_dpi_awareness() -> bool:
    if os.name != "nt":
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    set_context = getattr(user32, "SetProcessDpiAwarenessContext", None)
    if set_context is not None:
        set_context.argtypes = [ctypes.c_void_p]
        set_context.restype = ctypes.c_bool
        ctypes.set_last_error(0)
        if set_context(ctypes.c_void_p(-4)):
            return True
    set_legacy = getattr(user32, "SetProcessDPIAware", None)
    if set_legacy is None:
        return False
    set_legacy.argtypes = []
    set_legacy.restype = ctypes.c_bool
    ctypes.set_last_error(0)
    return bool(set_legacy())


def show_fatal_error(message: str, root: tk.Tk | None = None) -> None:
    if root is not None:
        messagebox.showerror("桌面宠物无法启动", message, parent=root)
        return
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, "桌面宠物无法启动", 0x10)


def main() -> int:
    enable_per_monitor_dpi_awareness()
    build_info = load_expectation_build_info()
    mutex = SingleInstanceMutex(build_mutex_name())
    root: tk.Tk | None = None
    pet_window: PetWindow | None = None
    services: ApplicationServices | None = None
    state = dict(DEFAULT_STATE)
    try:
        if not mutex.acquire():
            notify_existing_instance(build_info)
            return 0
        services = create_application_services(build_info)
        state = services.load_state()
        if state.get("pending_transaction") is not None:
            services.runtime.post("transaction.review", source="startup")
            services.runtime.drain()
        root = tk.Tk()
        if os.environ.get("DESKTOP_PET_STARTUP_DIAGNOSTICS"):
            def report_callback_error(kind, error, trace):
                destination = Path(os.environ["DESKTOP_PET_STARTUP_DIAGNOSTICS"])
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("a", encoding="utf-8") as stream:
                    stream.write("".join(traceback.format_exception(kind, error, trace)))
                root.quit()
            root.report_callback_exception = report_callback_error
        root.withdraw()
        frames = load_frames()
        animation_sequences = load_playback_sequences()
        compositor = load_head_neck_compositor()
        cursor_provider = Win32CursorProvider()
        hunger = HungerService(SharedHungerState(services), utc_clock=lambda: int(services.runtime.clock.utc_now().timestamp()))
        services.dragdrop.close()
        services.dragdrop = ExpectationDragDropService()
        from .expectation_assets import load_expectation_frames
        expectation_frames = load_expectation_frames(expected_size=compositor.source_size)
        pet_window = ExpectationWindow(
            root,
            frames,
            compositor=compositor,
            cursor_provider=cursor_provider,
            head_follow=True,
            services=services,
            persisted_state=state,
            animation_sequences=animation_sequences,
            hunger=hunger,
            expectation_frames=expectation_frames,
        )
        if os.environ.get("DESKTOP_PET_SMOKE_CHECK") == "1" and build_info.feature_config.test_build:
            def report_smoke_ready():
                with (services.paths.root / "smoke-ready.json").open("x", encoding="utf-8") as stream:
                    json.dump({"ready": pet_window._window_shown,
                               "expectation_frames": len(expectation_frames),
                               "same_runtime": pet_window.expectation.services is services,
                               "git_short_hash": build_info.git_short_hash}, stream)
            root.after_idle(report_smoke_ready)
        root.mainloop()
        return 0
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError, tk.TclError) as error:
        if os.environ.get("DESKTOP_PET_STARTUP_DIAGNOSTICS"):
            Path(os.environ["DESKTOP_PET_STARTUP_DIAGNOSTICS"]).write_text(traceback.format_exc(), encoding="utf-8")
        show_fatal_error(str(error), root)
        return 1
    finally:
        if pet_window is not None:
            try:
                pet_window.close()
            except tk.TclError:
                pass
        else:
            if services is not None:
                try:
                    services.close()
                except (OSError, RuntimeError):
                    pass
            if root is not None:
                try:
                    if root.winfo_exists():
                        root.destroy()
                except tk.TclError:
                    pass
        mutex.close()


if __name__ == "__main__":
    raise SystemExit(main())

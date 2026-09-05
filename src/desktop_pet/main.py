from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timezone
import json

from .assets import load_frames, load_head_neck_compositor
from .eye_follow import Win32CursorProvider
from .window import PetWindow
from .hunger import HungerStore, MutableUtcClock, system_utc_seconds
from .hunger_runtime import (
    HungerRuntime,
    default_hunger_path,
    enable_debug_time_simulation,
)
from .paths import asset_path


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


def is_test_build() -> bool:
    try:
        metadata = json.loads(asset_path("build_metadata.json").read_text("utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return False
    return metadata.get("test_build") is True and metadata.get("debug_menu") is True


def main() -> int:
    enable_per_monitor_dpi_awareness()
    mutex = SingleInstanceMutex(build_mutex_name())
    root: tk.Tk | None = None
    pet_window: PetWindow | None = None
    try:
        if not mutex.acquire():
            return 0
        root = tk.Tk()
        root.withdraw()
        frames = load_frames()
        compositor = load_head_neck_compositor()
        cursor_provider = Win32CursorProvider()
        pet_window = PetWindow(
            root,
            frames,
            compositor=compositor,
            cursor_provider=cursor_provider,
            head_follow=True,
        )
        attach_hunger = getattr(pet_window, "attach_hunger_runtime", None)
        present_hunger = getattr(pet_window, "present_hunger", None)
        if callable(attach_hunger) and callable(present_hunger):
            debug_clock = (
                MutableUtcClock(datetime.now(timezone.utc)) if is_test_build() else None
            )
            hunger_runtime = HungerRuntime(
                store=HungerStore(default_hunger_path()),
                utc_clock=debug_clock.utc_seconds if debug_clock else system_utc_seconds,
                schedule=root.after,
                cancel=root.after_cancel,
                on_frame=present_hunger,
            )
            attach_hunger(hunger_runtime)
            if debug_clock is not None:
                add_debug_menu = getattr(pet_window, "add_debug_time_menu", None)
                if callable(add_debug_menu):
                    add_debug_menu(
                        lambda seconds: enable_debug_time_simulation(
                            test_build=True, clock=debug_clock, seconds=seconds
                        )
                    )
            hunger_runtime.start()
        root.mainloop()
        return 0
    except (OSError, RuntimeError, ValueError, tk.TclError) as error:
        show_fatal_error(str(error), root)
        return 1
    finally:
        if pet_window is not None:
            try:
                pet_window.close()
            except tk.TclError:
                pass
        elif root is not None:
            try:
                if root.winfo_exists():
                    root.destroy()
            except tk.TclError:
                pass
        mutex.close()


if __name__ == "__main__":
    raise SystemExit(main())

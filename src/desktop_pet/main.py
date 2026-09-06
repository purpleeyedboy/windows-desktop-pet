from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import messagebox
import json

from .assets import load_frames, load_head_neck_compositor
from .eye_follow import Win32CursorProvider
from .window import PetWindow
from .hunger import HungerService, OffsetUtcClock
from .hunger_runtime import (
    HungerRuntime,
)
from .paths import asset_path
from .foundation_contract import load_foundation_services


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


def build_metadata() -> dict[str, object]:
    try:
        value = json.loads(asset_path("build_metadata.json").read_text("utf-8-sig"))
    except (OSError, ValueError, TypeError) as error:
        raise RuntimeError("Missing V2.1-HUNGER build identity; refusing to show an unidentified cat") from error
    required = ("version", "git_short_hash", "baseline_commit", "foundation_commit", "enabled_features", "test_build")
    if not isinstance(value, dict) or any(key not in value for key in required):
        raise RuntimeError("Incomplete V2.1-HUNGER build identity")
    return value


def notify_existing_instance(metadata: dict[str, object]) -> None:
    message = (
        f"桌面宠物已有实例正在运行。\n"
        f"本次 V{metadata['version']} ({metadata['git_short_hash']}) 未启动。"
    )
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, "桌面宠物版本提示", 0x40)


def main() -> int:
    enable_per_monitor_dpi_awareness()
    mutex = SingleInstanceMutex(build_mutex_name())
    root: tk.Tk | None = None
    pet_window: PetWindow | None = None
    try:
        metadata = build_metadata()
        if not mutex.acquire():
            notify_existing_instance(metadata)
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
        foundation = load_foundation_services(root)
        if metadata["foundation_commit"] != foundation.foundation_commit:
            raise RuntimeError("Build metadata and loaded PR5 foundation commit do not match")
        activity = foundation.activity
        utc_clock = OffsetUtcClock(foundation.utc_clock.utc_seconds)
        service = HungerService(
            foundation.state_store,
            utc_clock.utc_seconds,
        )
        hunger_runtime = HungerRuntime(
            service=service,
            activity=activity,
            schedule=root.after,
            cancel=root.after_cancel,
            on_frame=pet_window.present_hunger,
        )
        pet_window.attach_hunger_runtime(hunger_runtime, activity)
        pet_window.add_hunger_menus(
            hunger_runtime,
            utc_clock,
            metadata,
        )
        pet_window.show_build_identity(metadata)
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

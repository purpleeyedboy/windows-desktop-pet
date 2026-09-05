from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import messagebox

from .assets import load_frames, load_head_neck_compositor
from .eye_follow import Win32CursorProvider
from .window import PetWindow
from .feed_core.wiring import FeedRuntime
from .feed_core.windows_drop import NativeFileDropTarget


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



def install_feed_runtime(root: tk.Tk, pet_window: PetWindow):
    if os.name != "nt":
        return None
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is unavailable for feed transaction state")
    runtime = FeedRuntime.create_windows(
        root, pet_window, os.path.join(local_app_data, "DesktopPet", "feed-core")
    )
    hwnd = int(getattr(pet_window.renderer, "hwnd", root.winfo_id()))
    target = NativeFileDropTarget(hwnd, runtime)
    target.register()
    return target


def main() -> int:
    enable_per_monitor_dpi_awareness()
    mutex = SingleInstanceMutex(build_mutex_name())
    root: tk.Tk | None = None
    pet_window: PetWindow | None = None
    feed_drop_target = None
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
        feed_drop_target = install_feed_runtime(root, pet_window)
        root.mainloop()
        return 0
    except (OSError, RuntimeError, ValueError, tk.TclError) as error:
        show_fatal_error(str(error), root)
        return 1
    finally:
        if feed_drop_target is not None:
            try:
                feed_drop_target.close()
            except (OSError, RuntimeError):
                pass
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

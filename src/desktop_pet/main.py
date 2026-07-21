from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import messagebox

from .assets import load_frames
from .window import PetWindow


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


def show_fatal_error(message: str, root: tk.Tk | None = None) -> None:
    if root is not None:
        messagebox.showerror("桌面宠物无法启动", message, parent=root)
        return
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, "桌面宠物无法启动", 0x10)


def main() -> int:
    mutex = SingleInstanceMutex(build_mutex_name())
    root: tk.Tk | None = None
    try:
        if not mutex.acquire():
            return 0
        root = tk.Tk()
        root.withdraw()
        frames = load_frames()
        PetWindow(root, frames)
        root.mainloop()
        return 0
    except (OSError, RuntimeError, tk.TclError) as error:
        show_fatal_error(str(error), root)
        return 1
    finally:
        if root is not None:
            try:
                if root.winfo_exists():
                    root.destroy()
            except tk.TclError:
                pass
        mutex.close()


if __name__ == "__main__":
    raise SystemExit(main())

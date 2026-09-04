"""Windows physical-pointer adapter. Never instantiate this adapter in tests."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from .paw_press import PointerBounds, PointerPoint

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
VK_LBUTTON, VK_RBUTTON = 0x01, 0x02


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class Win32PointerInputAdapter:
    """All coordinates are physical virtual-desktop pixels, including negatives."""

    def __init__(self, hwnd: int, user32=None) -> None:
        if os.name != "nt" and user32 is None:
            raise OSError("Win32 pointer control requires Windows")
        self.hwnd = hwnd
        self.user32 = user32 or ctypes.WinDLL("user32", use_last_error=True)

    def cursor_position(self) -> PointerPoint:
        point = POINT()
        if not self.user32.GetCursorPos(ctypes.byref(point)):
            raise OSError("GetCursorPos failed")
        return PointerPoint(point.x, point.y)

    def virtual_bounds(self) -> PointerBounds:
        metric = self.user32.GetSystemMetrics
        return PointerBounds(metric(SM_XVIRTUALSCREEN), metric(SM_YVIRTUALSCREEN),
                             metric(SM_CXVIRTUALSCREEN), metric(SM_CYVIRTUALSCREEN))

    def current_clip(self) -> PointerBounds:
        rect = RECT()
        if not self.user32.GetClipCursor(ctypes.byref(rect)):
            raise OSError("GetClipCursor failed")
        return PointerBounds(rect.left, rect.top, rect.right - rect.left,
                             rect.bottom - rect.top)

    def button_down(self, name: str) -> bool:
        key = VK_LBUTTON if name == "left" else VK_RBUTTON
        return bool(self.user32.GetAsyncKeyState(key) & 0x8000)

    def capture(self) -> None:
        self.user32.SetCapture(self.hwnd)

    def release_capture(self) -> None:
        self.user32.ReleaseCapture()

    def set_clip(self, bounds: PointerBounds | None) -> None:
        native = None if bounds is None else RECT(bounds.x, bounds.y,
            bounds.right, bounds.bottom)
        argument = None if native is None else ctypes.byref(native)
        if not self.user32.ClipCursor(argument):
            raise OSError("ClipCursor failed")

    def move(self, point: PointerPoint) -> None:
        if not self.user32.SetCursorPos(point.x, point.y):
            raise OSError("SetCursorPos failed")

    def press_left(self) -> None:
        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

    def release_left(self) -> None:
        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

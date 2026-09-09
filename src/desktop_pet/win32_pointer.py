"""Read/set-only Windows cursor service and read-only physical button state."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from .paw_press import PointerBounds, PointerPoint

SM_CYCURSOR = 14
SM_CXDRAG, SM_CYDRAG = 68, 69
VK_MOUSE_BUTTONS = (0x01, 0x02, 0x04, 0x05, 0x06)
MONITOR_DEFAULTTONEAREST = 2


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


class Win32CursorMovementService:
    """Foundation-compatible service; it can only read or set cursor position."""

    def __init__(self, user32=None) -> None:
        if os.name != "nt" and user32 is None:
            raise OSError("Win32 cursor service requires Windows")
        self.user32 = user32 or ctypes.WinDLL("user32", use_last_error=True)
        if user32 is None:
            # HMONITOR is pointer-sized on x64; ctypes' implicit int return
            # truncates it and can make GetMonitorInfoW reject every press.
            self.user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
            self.user32.GetCursorPos.restype = wintypes.BOOL
            self.user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
            self.user32.SetCursorPos.restype = wintypes.BOOL
            self.user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            self.user32.GetSystemMetrics.restype = ctypes.c_int
            self.user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
            self.user32.MonitorFromPoint.restype = wintypes.HANDLE
            self.user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
            self.user32.GetMonitorInfoW.restype = wintypes.BOOL
            self.user32.GetClipCursor.argtypes = [ctypes.POINTER(RECT)]
            self.user32.GetClipCursor.restype = wintypes.BOOL

    def position(self) -> PointerPoint:
        point = POINT()
        if not self.user32.GetCursorPos(ctypes.byref(point)):
            raise OSError("GetCursorPos failed")
        return PointerPoint(point.x, point.y)

    def set_position(self, point: PointerPoint) -> None:
        if not self.user32.SetCursorPos(point.x, point.y):
            raise OSError("SetCursorPos failed")

    def pointer_nominal_height(self) -> int:
        return int(self.user32.GetSystemMetrics(SM_CYCURSOR))

    def monitor_bounds_for(self, point: PointerPoint) -> PointerBounds:
        native_point = POINT(point.x, point.y)
        monitor = self.user32.MonitorFromPoint(native_point, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO(); info.cbSize = ctypes.sizeof(MONITORINFO)
        if not monitor or not self.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            raise OSError("monitor bounds unavailable")
        rect = info.rcMonitor
        return PointerBounds(rect.left, rect.top, rect.right - rect.left,
                             rect.bottom - rect.top)

    def current_clip(self) -> PointerBounds:
        rect = RECT()
        if not self.user32.GetClipCursor(ctypes.byref(rect)):
            raise OSError("GetClipCursor failed")
        return PointerBounds(rect.left, rect.top, rect.right - rect.left,
                             rect.bottom - rect.top)


class Win32ButtonState:
    """Read-only InputRouter adapter; it never synthesizes an input event."""

    def __init__(self, user32=None) -> None:
        if os.name != "nt" and user32 is None:
            raise OSError("Win32 button state requires Windows")
        self.user32 = user32 or ctypes.WinDLL("user32", use_last_error=True)

    def any_button_down(self) -> bool:
        return any(self.user32.GetAsyncKeyState(key) & 0x8000
                   for key in VK_MOUSE_BUTTONS)

    def drag_threshold(self) -> tuple[int, int]:
        return (
            max(1, int(self.user32.GetSystemMetrics(SM_CXDRAG))),
            max(1, int(self.user32.GetSystemMetrics(SM_CYDRAG))),
        )

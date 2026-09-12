import ctypes

import pytest

from desktop_pet.paw_press import PointerBounds, PointerPoint
from desktop_pet.win32_pointer import Win32CursorMovementService


class FakeUser32:
    def GetCursorPos(self, target):
        point = target._obj
        point.x, point.y = -1920, -200
        return 1

    def SetCursorPos(self, x, y):
        self.set_point = (x, y)
        return 1

    def GetSystemMetrics(self, _metric):
        return 64

    def MonitorFromPoint(self, point, _fallback):
        self.monitor_point = (point.x, point.y)
        return 7

    def GetMonitorInfoW(self, _monitor, target):
        info = target._obj
        info.rcMonitor.left, info.rcMonitor.top = -2560, -1440
        info.rcMonitor.right, info.rcMonitor.bottom = 0, 0
        return 1

    def GetClipCursor(self, target):
        rect = target._obj
        rect.left, rect.top, rect.right, rect.bottom = -2500, -1300, -100, -100
        return 1


def test_win32_cursor_service_preserves_physical_negative_desktop_coordinates():
    user32 = FakeUser32()
    service = Win32CursorMovementService(user32)

    assert service.position() == PointerPoint(-1920, -200)
    service.set_position(PointerPoint(-1919, -199))
    assert user32.set_point == (-1919, -199)
    assert service.pointer_nominal_height() == 64
    assert service.monitor_bounds_for(PointerPoint(-1920, -200)) == PointerBounds(
        -2560, -1440, 2560, 1440
    )
    assert user32.monitor_point == (-1920, -200)
    assert service.current_clip() == PointerBounds(-2500, -1300, 2400, 1200)


def test_win32_cursor_service_rejects_empty_native_bounds():
    user32 = FakeUser32()
    user32.GetClipCursor = lambda target: (
        setattr(target._obj, "left", 10),
        setattr(target._obj, "right", 10),
        1,
    )[-1]

    with pytest.raises(OSError, match="invalid cursor clip bounds"):
        Win32CursorMovementService(user32).current_clip()


def test_win32_cursor_service_rejects_inverted_monitor_bounds():
    user32 = FakeUser32()

    def inverted(_monitor, target):
        rect = target._obj.rcMonitor
        rect.left, rect.top, rect.right, rect.bottom = 100, 50, -100, 40
        return 1

    user32.GetMonitorInfoW = inverted

    with pytest.raises(OSError, match="invalid monitor bounds"):
        Win32CursorMovementService(user32).monitor_bounds_for(PointerPoint(0, 0))

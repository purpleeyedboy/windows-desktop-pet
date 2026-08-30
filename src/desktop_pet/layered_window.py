"""Win32 per-pixel Alpha rendering for the Tk-owned pet window."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from PIL import Image, ImageChops


WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
GWL_EXSTYLE = -20
GA_ROOT = 2
BI_RGB = 0
DIB_RGB_COLORS = 0
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
ULW_ALPHA = 0x00000002
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
HGDI_ERROR = ctypes.c_void_p(-1).value


def _last_error() -> int:
    get_last_error = getattr(ctypes, "get_last_error", None)
    return get_last_error() if get_last_error is not None else 0


def _win32_error(error_code: int | None = None) -> OSError:
    if error_code is None:
        error_code = _last_error()
    win_error = getattr(ctypes, "WinError", None)
    if win_error is not None:
        return win_error(error_code)
    return OSError(error_code, os.strerror(error_code))


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", wintypes.BYTE),
        ("BlendFlags", wintypes.BYTE),
        ("SourceConstantAlpha", wintypes.BYTE),
        ("AlphaFormat", wintypes.BYTE),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", wintypes.BYTE),
        ("rgbGreen", wintypes.BYTE),
        ("rgbRed", wintypes.BYTE),
        ("rgbReserved", wintypes.BYTE),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", RGBQUAD * 1),
    ]


def rgba_to_premultiplied_bgra(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA")
    red, green, blue, alpha = rgba.split()
    premultiplied = Image.merge(
        "RGBA",
        (
            ImageChops.multiply(red, alpha),
            ImageChops.multiply(green, alpha),
            ImageChops.multiply(blue, alpha),
            alpha,
        ),
    )
    return premultiplied.tobytes("raw", "BGRA")


class LayeredWindowRenderer:
    def __init__(self, hwnd: int) -> None:
        if os.name != "nt":
            raise OSError("LayeredWindowRenderer requires Windows")
        self.hwnd = hwnd
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        self._configure_functions()
        top_level = self._user32.GetAncestor(self.hwnd, GA_ROOT)
        if top_level:
            self.hwnd = int(top_level)
        self._apply_layered_style()

    def _configure_functions(self) -> None:
        self._user32.GetDC.argtypes = [wintypes.HWND]
        self._user32.GetDC.restype = wintypes.HDC
        self._user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        self._user32.ReleaseDC.restype = ctypes.c_int
        self._user32.UpdateLayeredWindow.argtypes = [
            wintypes.HWND,
            wintypes.HDC,
            ctypes.POINTER(POINT),
            ctypes.POINTER(SIZE),
            wintypes.HDC,
            ctypes.POINTER(POINT),
            wintypes.COLORREF,
            ctypes.POINTER(BLENDFUNCTION),
            wintypes.DWORD,
        ]
        self._user32.UpdateLayeredWindow.restype = wintypes.BOOL
        self._user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self._user32.GetAncestor.restype = wintypes.HWND
        self._user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        self._user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self._user32.SetWindowLongPtrW.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_ssize_t,
        ]
        self._user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        self._user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self._user32.SetWindowPos.restype = wintypes.BOOL

        self._gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        self._gdi32.CreateCompatibleDC.restype = wintypes.HDC
        self._gdi32.DeleteDC.argtypes = [wintypes.HDC]
        self._gdi32.DeleteDC.restype = wintypes.BOOL
        self._gdi32.CreateDIBSection.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(BITMAPINFO),
            wintypes.UINT,
            ctypes.POINTER(wintypes.LPVOID),
            wintypes.HANDLE,
            wintypes.DWORD,
        ]
        self._gdi32.CreateDIBSection.restype = wintypes.HBITMAP
        self._gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        self._gdi32.SelectObject.restype = wintypes.HGDIOBJ
        self._gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        self._gdi32.DeleteObject.restype = wintypes.BOOL

    def _get_extended_style(self) -> int:
        ctypes.set_last_error(0)
        style = self._user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        error = _last_error()
        if style == 0 and error:
            raise _win32_error(error)
        return int(style)

    def _apply_layered_style(self) -> None:
        current = self._get_extended_style()
        updated = (current | WS_EX_LAYERED | WS_EX_TOOLWINDOW) & ~WS_EX_TRANSPARENT
        if updated == current:
            return
        ctypes.set_last_error(0)
        previous = self._user32.SetWindowLongPtrW(
            self.hwnd, GWL_EXSTYLE, updated
        )
        error = _last_error()
        if previous == 0 and error:
            raise _win32_error(error)

    def is_layered(self) -> bool:
        return bool(self._get_extended_style() & WS_EX_LAYERED)

    def set_topmost(self, enabled: bool) -> None:
        insert_after = HWND_TOPMOST if enabled else HWND_NOTOPMOST
        if not self._user32.SetWindowPos(
            self.hwnd,
            insert_after,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        ):
            raise _win32_error()

    def _create_top_down_dib(
        self, screen_dc: wintypes.HDC, size: tuple[int, int]
    ) -> tuple[wintypes.HBITMAP, wintypes.LPVOID]:
        width, height = size
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB
        info.bmiHeader.biSizeImage = width * height * 4
        bits = wintypes.LPVOID()
        bitmap = self._gdi32.CreateDIBSection(
            screen_dc,
            ctypes.byref(info),
            DIB_RGB_COLORS,
            ctypes.byref(bits),
            None,
            0,
        )
        if not bitmap or not bits:
            if bitmap:
                self._gdi32.DeleteObject(bitmap)
            raise _win32_error()
        return bitmap, bits

    def render(self, image: Image.Image, x: int, y: int) -> None:
        pixels = rgba_to_premultiplied_bgra(image)
        screen_dc = self._user32.GetDC(None)
        if not screen_dc:
            raise _win32_error()
        memory_dc = None
        bitmap = None
        old_bitmap = None
        try:
            memory_dc = self._gdi32.CreateCompatibleDC(screen_dc)
            if not memory_dc:
                raise _win32_error()
            bitmap, bits = self._create_top_down_dib(screen_dc, image.size)
            ctypes.memmove(bits, pixels, len(pixels))
            old_bitmap = self._gdi32.SelectObject(memory_dc, bitmap)
            if not old_bitmap or old_bitmap == HGDI_ERROR:
                old_bitmap = None
                raise _win32_error()

            destination = POINT(x, y)
            size = SIZE(*image.size)
            source = POINT(0, 0)
            blend = BLENDFUNCTION(
                AC_SRC_OVER,
                0,
                255,
                AC_SRC_ALPHA,
            )
            if not self._user32.UpdateLayeredWindow(
                self.hwnd,
                screen_dc,
                ctypes.byref(destination),
                ctypes.byref(size),
                memory_dc,
                ctypes.byref(source),
                0,
                ctypes.byref(blend),
                ULW_ALPHA,
            ):
                raise _win32_error()
        finally:
            if old_bitmap and memory_dc:
                self._gdi32.SelectObject(memory_dc, old_bitmap)
            if bitmap:
                self._gdi32.DeleteObject(bitmap)
            if memory_dc:
                self._gdi32.DeleteDC(memory_dc)
            self._user32.ReleaseDC(None, screen_dc)

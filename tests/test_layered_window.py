import ctypes
import os
from ctypes import wintypes
from time import perf_counter

import pytest
from PIL import Image

from desktop_pet import configure_tk_environment

configure_tk_environment()

import tkinter as tk

from desktop_pet.layered_window import (
    LayeredWindowRenderer,
    WS_EX_LAYERED,
    WS_EX_TRANSPARENT,
    rgba_to_premultiplied_bgra,
)


def test_rgba_to_premultiplied_bgra_uses_integer_rounding():
    image = Image.new("RGBA", (2, 1))
    image.putdata([(200, 100, 50, 128), (9, 8, 7, 0)])

    assert rgba_to_premultiplied_bgra(image) == bytes(
        (25, 50, 100, 128, 0, 0, 0, 0)
    )


def test_premultiply_keeps_max_pet_size_realtime():
    image = Image.new("RGBA", (347, 520), (200, 100, 50, 128))

    started = perf_counter()
    for _ in range(3):
        rgba_to_premultiplied_bgra(image)

    assert perf_counter() - started < 0.25


@pytest.mark.skipif(os.name != "nt", reason="Windows layered window contract")
def test_renderer_applies_layered_toolwindow_style():
    root = tk.Tk()
    root.withdraw()
    try:
        renderer = LayeredWindowRenderer(root.winfo_id())
        assert renderer.is_layered() is True
        renderer.set_topmost(False)
        renderer.set_topmost(True)
    finally:
        root.destroy()


@pytest.mark.skipif(os.name != "nt", reason="Windows layered window contract")
def test_renderer_targets_the_real_tk_top_level_window():
    root = tk.Tk()
    root.withdraw()
    try:
        root.update_idletasks()
        tk_child = root.winfo_id()
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        top_level = user32.GetAncestor(tk_child, 2)

        renderer = LayeredWindowRenderer(tk_child)

        assert top_level
        assert int(renderer.hwnd) == int(top_level)
        style = user32.GetWindowLongPtrW(top_level, -20)
        assert style & WS_EX_LAYERED
        assert not style & WS_EX_TRANSPARENT
    finally:
        root.destroy()


def test_partial_dib_creation_deletes_returned_bitmap():
    deleted: list[int] = []

    class PartialGdi:
        @staticmethod
        def CreateDIBSection(*_args):
            return 73

        @staticmethod
        def DeleteObject(handle):
            deleted.append(handle)
            return True

    renderer = object.__new__(LayeredWindowRenderer)
    renderer._gdi32 = PartialGdi()

    with pytest.raises(OSError):
        renderer._create_top_down_dib(wintypes.HDC(), (2, 2))

    assert deleted == [73]

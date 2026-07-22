import os
from ctypes import wintypes

import pytest
from PIL import Image

from desktop_pet import configure_tk_environment

configure_tk_environment()

import tkinter as tk

from desktop_pet.layered_window import (
    LayeredWindowRenderer,
    rgba_to_premultiplied_bgra,
)


def test_rgba_to_premultiplied_bgra_uses_integer_rounding():
    image = Image.new("RGBA", (2, 1))
    image.putdata([(200, 100, 50, 128), (9, 8, 7, 0)])

    assert rgba_to_premultiplied_bgra(image) == bytes(
        (25, 50, 100, 128, 0, 0, 0, 0)
    )


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

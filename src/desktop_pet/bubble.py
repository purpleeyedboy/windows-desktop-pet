from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from .model import Rect, format_position, place_bubble


TRANSPARENT_KEY = "#ff00ff"


class BubbleWindow:
    def __init__(self, parent: tk.Misc) -> None:
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.configure(background=TRANSPARENT_KEY)
        self.window.attributes("-topmost", True)
        try:
            self.window.attributes("-toolwindow", True)
            self.window.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(
            self.window,
            background=TRANSPARENT_KEY,
            borderwidth=0,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.font = tkfont.Font(
            root=self.window,
            family="Microsoft YaHei UI",
            size=11,
            weight="bold",
        )
        self.body_item = 0
        self.last_rect: Rect | None = None
        self._text = ""
        self._hide_job: str | None = None
        self.visible = False

    def _draw_rounded_body(self, width: int, height: int) -> None:
        self.canvas.delete("all")
        radius = 16
        left, top, right, bottom = 2, 2, width - 2, height - 14
        points = (
            left + radius,
            top,
            right - radius,
            top,
            right,
            top,
            right,
            top + radius,
            right,
            bottom - radius,
            right,
            bottom,
            right - radius,
            bottom,
            left + radius,
            bottom,
            left,
            bottom,
            left,
            bottom - radius,
            left,
            top + radius,
            left,
            top,
        )
        self.body_item = self.canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill="#ffffff",
            outline="#333333",
            width=1,
        )
        center = width // 2
        self.canvas.create_polygon(
            center - 8,
            bottom - 1,
            center + 9,
            bottom - 1,
            center,
            height - 2,
            fill="#ffffff",
            outline="#333333",
            width=1,
        )
        self.canvas.create_text(
            center,
            (top + bottom) // 2,
            text=self._text,
            fill="#222222",
            font=self.font,
            anchor="center",
        )

    def show_message(self, text: str, pet_rect: Rect, screen_rect: Rect) -> None:
        self._text = text
        width = max(132, min(260, self.font.measure(text) + 40))
        height = 76
        rect = place_bubble(pet_rect, (width, height), screen_rect)
        self.last_rect = rect
        self.window.geometry(
            f"{rect.width}x{rect.height}{format_position(rect.x, rect.y)}"
        )
        self.canvas.configure(width=rect.width, height=rect.height)
        self._draw_rounded_body(rect.width, rect.height)
        self.window.deiconify()
        self.window.lift()
        self.visible = True
        if self._hide_job is not None:
            self.window.after_cancel(self._hide_job)
        self._hide_job = self.window.after(1800, self.hide)

    def reposition(self, pet_rect: Rect, screen_rect: Rect) -> None:
        if not self.visible or self.last_rect is None:
            return
        rect = place_bubble(
            pet_rect,
            (self.last_rect.width, self.last_rect.height),
            screen_rect,
        )
        self.last_rect = rect
        self.window.geometry(
            f"{rect.width}x{rect.height}{format_position(rect.x, rect.y)}"
        )

    def set_always_on_top(self, enabled: bool) -> None:
        self.window.attributes("-topmost", enabled)

    def hide(self) -> None:
        self.window.withdraw()
        self.visible = False
        self._hide_job = None

    def destroy(self) -> None:
        self.window.destroy()

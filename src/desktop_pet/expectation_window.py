"""Expectation feature window, retaining the shared foundation window."""
from __future__ import annotations

from PIL import Image, ImageDraw
from .drag_runtime import DragExpectationRuntime
from .window import PetWindow


class ExpectationWindow(PetWindow):
    def __init__(self, *args, hunger, expectation_frames, **kwargs):
        self.expectation = None
        self._particle_phase = 0
        self._hunger = hunger
        super().__init__(*args, **kwargs)
        self.expectation = DragExpectationRuntime(
            self.services, hunger=hunger, frames=expectation_frames,
            show_frame=self._show_expectation_frame,
            restore=self._restore_expectation,
            schedule=self.root.after, cancel=self._cancel_after,
        )
        self.services.dragdrop.handler = self.expectation
        self.root.title(f"桌面宠物 V2.1-EXPECT | {self.services.build_info.product_version} | git:{self.services.build_info.git_short_hash}")
        self.root.bind("<Escape>", lambda _event: self.expectation.leave("escape"), add="+")
        self.root.bind("<FocusOut>", lambda _event: self.expectation.leave("focus-lost"), add="+")
        if self.services.build_info.feature_config.debug_menu_enabled:
            self.services.debug.register("期待动画预览（3秒，不改变饥饿）", self.expectation.debug_preview)
            self.services.debug.register("停止期待预览", self.expectation.leave)

    def _show_expectation_frame(self, frame):
        if self.eye_session is not None:
            self.eye_session.interrupt_idle()
        if self.expectation is not None and self.expectation.active:
            phase = self._particle_phase
            self._particle_phase = (phase + 1) % 24
            overlay = Image.new("RGBA", frame.size)
            draw = ImageDraw.Draw(overlay)
            # Independent particles use the approved head anchor on the 640px canvas.
            left, top, right, bottom = 88, 204, 318, 445
            points = ((left + phase * 9 % (right - left), top - 5),
                      (right + 5, top + phase * 11 % (bottom - top)),
                      (left - 5, bottom - phase * 7 % (bottom - top)))
            for x, y in points:
                draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 244, 150, 220))
            frame = Image.alpha_composite(frame, overlay)
        self._apply_image(frame, self._anchor())

    def _display_eye_frame(self, frame):
        if self.expectation is not None and self.expectation.showing:
            return
        super()._display_eye_frame(frame)

    def _restore_expectation(self):
        self._particle_phase = 0
        if not self._closed:
            self._recover_body_channel()

    def close(self):
        if self._closed:
            return
        if self.expectation is not None:
            self.expectation.close()
        try:
            self._hunger.close()
        finally:
            super().close()

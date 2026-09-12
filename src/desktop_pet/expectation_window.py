"""Expectation feature window, retaining the shared foundation window."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from .drag_runtime import DragExpectationRuntime
from .window import PetWindow
from .drag_expectation import DragVisualConfig, decorate_drag_expectation


class FollowingExpectationCompositor:
    """Recompose pupil offsets through the SAME full head mesh and rotation.

    No eye crops are moved in post-render screen coordinates. Tracking is kept
    here (before display callbacks) so the displayed pose is never one tick old.
    """
    def __init__(self, compositor):
        self.source = compositor
        self.last = None
        self.center = None
        self.center_pose = None

    def __getattr__(self, name):
        return getattr(self.source, name)

    def compose(self, eye_x, eye_y, *pose):
        self.last = (eye_x, eye_y, pose)
        frame = self.source.compose(eye_x, eye_y, *pose)
        if eye_x == eye_y == 0 and (not pose or all(getattr(pose[0], field, 0) == 0 for field in ("x", "y", "rotation_degrees", "arc"))):
            self.center, self.center_pose = frame, self.last
        return frame

    def compose_head(self, eye_x, eye_y, pose):
        return self.compose(eye_x, eye_y, pose)

    def compose_head_blink(self, eye_x, eye_y, pose, closure):
        self.last = (eye_x, eye_y, (pose,))
        return self.source.compose_head_blink(eye_x, eye_y, pose, closure)

    def feedback(self, phase, base_frame=None):
        if self.last is None:
            return None
        eye_x, eye_y, pose = self.center_pose if base_frame is self.center and self.center_pose is not None else self.last
        offset = 0.18 * min(1.0, max(0.0, phase / 3)) * (-1 if phase % 2 else 1)
        return self.source.compose(max(-3.0, min(3.0, eye_x + offset)), eye_y, *pose)


class ExpectationWindow(PetWindow):
    def __init__(self, *args, hunger, expectation_frames, **kwargs):
        self.expectation = None
        self._particle_phase = 0
        self._expectation_phase = 0
        self._following_frame = None
        self._hunger = hunger
        source = kwargs.get("compositor")
        self._expectation_compositor = FollowingExpectationCompositor(source) if source is not None else None
        if self._expectation_compositor is not None:
            kwargs["compositor"] = self._expectation_compositor
        super().__init__(*args, **kwargs)
        # Explicit center of the approved canonical head, not the eye midpoint.
        self._region_anchors["head-center"] = (203, 324)
        self.expectation = DragExpectationRuntime(
            self.services, hunger=hunger, frames=expectation_frames,
            show_frame=self._show_expectation_frame,
            restore=self._restore_expectation,
            schedule=self.root.after, cancel=self._cancel_after,
            pointer_state=self._passive_pointer_state if os.name == "nt" else None,
        )
        self.services.dragdrop.handler = self.expectation
        self.root.title(f"桌面宠物 V2.1-EXPECT | {self.services.build_info.product_version} | git:{self.services.build_info.git_short_hash}")
        self.root.bind("<Escape>", lambda _event: self.expectation.leave("escape"), add="+")
        self.root.bind("<FocusOut>", lambda _event: self.expectation.leave("focus-lost"), add="+")
        if self.services.build_info.feature_config.debug_menu_enabled:
            self.services.debug.register("期待动画预览（3秒，不改变饥饿）", self.expectation.debug_preview)
            self.services.debug.register("停止期待预览", self.expectation.leave)

    def _show_expectation_frame(self, frame):
        self._expectation_phase = self.expectation._frame_index if self.expectation is not None else 0
        self._particle_phase = (self._particle_phase + 1) % 8
        # Never replace a live following frame with a static neutral-direction pose.
        base = self._following_frame if self._following_frame is not None else self._neutral_center_frame
        self._apply_image(self._compose_expectation(base), self._anchor())

    @staticmethod
    def _passive_pointer_state():
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            raise OSError("GetCursorPos failed")
        held = bool(user32.GetAsyncKeyState(1) & 0x8000)
        cancelled = bool(user32.GetAsyncKeyState(0x1B) & 0x8000)
        return (point.x, point.y), held and not cancelled

    def _compose_expectation(self, frame):
        compositor = getattr(self, "_expectation_compositor", None)
        if compositor is not None:
            following = compositor.feedback(self._expectation_phase, frame)
            if following is not None:
                frame = following
        config = DragVisualConfig(eye_boxes=(), head_box=(88, 204, 318, 445))
        return decorate_drag_expectation(frame, self._particle_phase, config)

    def _display_eye_frame(self, frame):
        self._following_frame = frame
        if self.expectation is not None and self.expectation.showing:
            self._apply_image(self._compose_expectation(frame), self._anchor())
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

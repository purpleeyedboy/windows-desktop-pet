"""Hunger UI layered on the unchanged shared window and graphic-frame player."""
from __future__ import annotations

from tkinter import messagebox
from PIL import Image

from .foundation.runtime import Activity
from .hunger import HungerLevel
from .window import PetWindow


class HungerWindow(PetWindow):
    def __init__(self, *args, **kwargs):
        self.hunger_runtime = None
        self._critical_art = None
        self._critical_frames = ()
        self._critical_durations = ()
        self._critical_index = None
        self._hunger_snapshot = None
        self._critical_visible = False
        super().__init__(*args, **kwargs)

    def attach_hunger(self, runtime, artwork, utc_clock) -> None:
        self.hunger_runtime = runtime
        for name, (frames, sequence) in artwork.clips.items():
            self.register_graphic_clip(name, frames, sequence)
        self._critical_frames = artwork.critical_frames
        self._critical_durations = artwork.critical_durations
        self._critical_art = self._critical_frames[0]
        if self.services.build_info.feature_config.debug_menu_enabled:
            debug = self.services.debug
            # The foundation has no unregister API; remove only its stale,
            # disabled hunger placeholder after this feature is attached.
            placeholder = debug._commands.get("饥饿（未接入）")
            if placeholder is not None and not placeholder[1]:
                debug._commands.pop("饥饿（未接入）")
            for label, units in (
                ("饥饿值 100%", 100_000), ("饥饿值 20%", 20_000),
                ("饥饿值 19.9%", 19_900), ("饥饿值 10%", 10_000),
                ("饥饿值 9.9%", 9_900), ("饥饿值 1%", 1_000),
                ("饥饿值 0.9%", 900), ("饥饿值 0%", 0),
            ):
                debug.register(label, lambda value=units: runtime.set_debug_units(value))
            for label, seconds in (("时间 +30 分钟", 1800), ("时间 +60 分钟", 3600), ("时间 +120 分钟", 7200)):
                debug.register(label, lambda value=seconds: utc_clock.advance(value))
            debug.register("重播当前饥饿动画", runtime.replay)
            debug.register("饥饿内部状态", lambda: messagebox.showinfo("饥饿运行状态", runtime.status_text(), parent=self.root))

    def _consume_blink(self, event) -> None:
        if self._hunger_snapshot is not None and self._hunger_snapshot.level is HungerLevel.CRITICAL_HUNGRY:
            return
        super()._consume_blink(event)

    def refresh_hunger_presentation(self, snapshot) -> None:
        self._hunger_snapshot = snapshot
        visible = (
            snapshot.level is HungerLevel.CRITICAL_HUNGRY
            and self.services.runtime.snapshot().activity is Activity.IDLE
            and self._critical_art is not None
        )
        index = None
        if visible:
            position = int(self.services.runtime.clock.monotonic() * 1000) % sum(self._critical_durations)
            for candidate, duration in enumerate(self._critical_durations):
                if position < duration:
                    index = candidate
                    break
                position -= duration
            self._critical_art = self._critical_frames[index]
        if visible != self._critical_visible or index != self._critical_index:
            self._critical_visible = visible
            self._critical_index = index
            # Use an immutable accepted neutral source on every transition. The
            # critical full frame is display-only and never becomes a new base.
            if isinstance(self._neutral_center_frame, Image.Image):
                self._apply_image(self._neutral_center_frame, self._anchor())

    def _present_candidate(self, source_image, resized_image, rect, display_height):
        if (
            self._critical_visible
            and self.services.runtime.snapshot().activity is Activity.IDLE
            and self._critical_art is not None
        ):
            resized_image = self._critical_art.resize(resized_image.size, Image.Resampling.LANCZOS)
        super()._present_candidate(source_image, resized_image, rect, display_height)

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self.hunger_runtime is not None:
                self.hunger_runtime.stop()
        except (OSError, RuntimeError, ValueError) as error:
            self.services.logger.error("hunger checkpoint failed during close: %s", type(error).__name__)
        finally:
            # Shared close saves the latest owner state, never the startup copy.
            super().close()

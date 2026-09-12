from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from random import Random
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Mapping, Protocol, Sequence

from PIL import Image

from .animation import AnimationController
from .animation import AnimationSequence
from .bubble import BubbleWindow
from .dialogue import DialogueChooser, load_phrase_pools
from .eye_follow import CursorProvider
from .foundation.platform import Point, Rect as FoundationRect
from .foundation.runtime import Activity, ActivityToken, RuntimeEvent
from .foundation.services import ApplicationServices
from .eye_runtime import (
    ActionFailure,
    Compositor,
    RuntimeEyeSession,
    SessionResult,
)
from .head_neck_deformation import HeadPose
from .idle_head_tilt import TILT_MODES, TiltMode
from .layered_window import LayeredWindowRenderer
from .model import ACTIONS, ActionCycle, Rect, clamp_height, format_position
from .paw_compositor import PawCompositor
from .paw_press import (
    FoundationPawActivityAdapter,
    CursorMovementService,
    LocalPawActivityAdapter,
    PawActivityService,
    PawPressController,
    PawMotionConfig,
    PawPose,
    PawSide,
    PawState,
)
from .release_status import release_status_text


SIZE_PRESETS = {"小": 180, "中": 280, "大": 420}
ACTION_MENU_ITEMS = (
    ("动作：跳跃", "jump"),
    ("动作：压扁", "squash"),
    ("动作：抖动", "shake"),
)
TILT_MENU_ITEMS = (
    ("歪头：向左", "left"),
    ("歪头：向右", "right"),
    ("歪头：左到右", "left_arc_right"),
)
GRAPHIC_ACTIVITIES = frozenset({
    Activity.BODY_ACTION,
    Activity.GROOM,
    Activity.NORMAL_HUNGER_ANIMATION,
    Activity.SEVERE_HUNGER_ANIMATION,
    Activity.FEED_ANIMATION,
})
CLICK_THRESHOLD = 8
MONITOR_DEFAULTTONEAREST = 2


class WinRect(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", WinRect),
        ("rcWork", WinRect),
        ("dwFlags", wintypes.DWORD),
    ]


def constrain_rect_to_area(rect: Rect, area: Rect) -> Rect:
    if rect.width >= area.width:
        x = area.x
    else:
        x = min(max(rect.x, area.x), area.right - rect.width)
    if rect.height >= area.height:
        y = area.y
    else:
        y = min(max(rect.y, area.y), area.bottom - rect.height)
    return Rect(x, y, rect.width, rect.height)


def _monitor_work_area(user32, monitor: int, fallback: Rect) -> Rect:
    if not monitor:
        return fallback
    get_monitor_info = user32.GetMonitorInfoW
    get_monitor_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    get_monitor_info.restype = wintypes.BOOL
    info = MonitorInfo()
    info.cbSize = ctypes.sizeof(MonitorInfo)
    if not get_monitor_info(monitor, ctypes.byref(info)):
        return fallback
    work = info.rcWork
    return Rect(work.left, work.top, work.right - work.left, work.bottom - work.top)


class Renderer(Protocol):
    def render(self, image: Image.Image, x: int, y: int) -> None: ...

    def set_topmost(self, enabled: bool) -> None: ...


RendererFactory = Callable[[int], Renderer]
RuntimeFailureReporter = Callable[[str], None]


class _CachedCenterCompositor:
    """Keep one literal center object while delegating every moving pose."""

    def __init__(self, compositor: Compositor) -> None:
        self._compositor = compositor
        self.source_size = compositor.source_size
        self.eye_midpoint = compositor.eye_midpoint
        self.eye_interaction_boxes = tuple(
            getattr(compositor, "eye_interaction_boxes", ())
        )
        self.center_frame: object | None = None

    def compose(self, eye_x: float, eye_y: float) -> object:
        if eye_x == 0.0 and eye_y == 0.0:
            if self.center_frame is None:
                self.center_frame = self._compositor.compose(0.0, 0.0)
            return self.center_frame
        return self._compositor.compose(eye_x, eye_y)

    def compose_head(
        self,
        eye_x: float,
        eye_y: float,
        head_pose: HeadPose,
    ) -> object:
        if (
            eye_x == 0.0
            and eye_y == 0.0
            and head_pose.x == 0.0
            and head_pose.y == 0.0
            and head_pose.rotation_degrees == 0.0
            and head_pose.arc == 0.0
        ):
            if self.center_frame is None:
                self.center_frame = self._compositor.compose(
                    0.0,
                    0.0,
                    head_pose,
                )
            return self.center_frame
        return self._compositor.compose(eye_x, eye_y, head_pose)

    def __getattr__(self, name: str) -> object:
        if name == "compose_blink" and callable(
            getattr(self._compositor, name, None)
        ):
            return self._compose_blink
        if name == "compose_head_blink" and callable(
            getattr(self._compositor, name, None)
        ):
            return self._compose_head_blink
        raise AttributeError(name)

    def _compose_blink(
        self,
        eye_x: float,
        eye_y: float,
        closure: float,
    ) -> object:
        if eye_x == 0.0 and eye_y == 0.0 and closure == 0.0:
            return self.compose(0.0, 0.0)
        compose_blink = getattr(self._compositor, "compose_blink")
        return compose_blink(eye_x, eye_y, closure)

    def _compose_head_blink(
        self,
        eye_x: float,
        eye_y: float,
        head_pose: HeadPose,
        closure: float,
    ) -> object:
        if (
            eye_x == 0.0
            and eye_y == 0.0
            and head_pose.x == 0.0
            and head_pose.y == 0.0
            and head_pose.rotation_degrees == 0.0
            and head_pose.arc == 0.0
            and closure == 0.0
        ):
            return self.compose_head(0.0, 0.0, head_pose)
        compose_head_blink = getattr(self._compositor, "compose_head_blink")
        return compose_head_blink(eye_x, eye_y, head_pose, closure)

    def hit_test_eye(self, point: tuple[float, float]) -> bool:
        hit_test = getattr(self._compositor, "hit_test_eye", None)
        if callable(hit_test):
            return bool(hit_test(point))
        x, y = point
        return any(
            left <= x < right and top <= y < bottom
            for left, top, right, bottom in self.eye_interaction_boxes
        )


@dataclass(frozen=True)
class _PresentationSnapshot:
    source_image: Image.Image
    resized_image: Image.Image
    rect: Rect
    display_height: int
    geometry: str


def screen_work_area(window_id: int, fallback: Rect) -> Rect:
    if os.name != "nt":
        return fallback
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    monitor_from_window = user32.MonitorFromWindow
    monitor_from_window.argtypes = [wintypes.HWND, wintypes.DWORD]
    monitor_from_window.restype = wintypes.HANDLE
    monitor = monitor_from_window(window_id, MONITOR_DEFAULTTONEAREST)
    return _monitor_work_area(user32, monitor, fallback)


def screen_work_area_for_rect(rect: Rect, fallback: Rect) -> Rect:
    if os.name != "nt":
        return fallback
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    monitor_from_rect = user32.MonitorFromRect
    monitor_from_rect.argtypes = [ctypes.POINTER(WinRect), wintypes.DWORD]
    monitor_from_rect.restype = wintypes.HANDLE
    native_rect = WinRect(rect.x, rect.y, rect.right, rect.bottom)
    monitor = monitor_from_rect(
        ctypes.byref(native_rect), MONITOR_DEFAULTTONEAREST
    )
    return _monitor_work_area(user32, monitor, fallback)


class PetWindow:
    def __init__(
        self,
        root: tk.Tk,
        frames: dict[str, Sequence[Image.Image]],
        renderer_factory: RendererFactory = LayeredWindowRenderer,
        *,
        compositor: Compositor | None = None,
        cursor_provider: CursorProvider | None = None,
        legacy_mode: bool = False,
        runtime_failure_reporter: RuntimeFailureReporter | None = None,
        clock: Callable[[], float] = time.monotonic,
        head_follow: bool = False,
        cursor_service_factory: Callable[[int], CursorMovementService] | None = None,
        button_state_factory: Callable[[int], object] | None = None,
        paw_activity_service: PawActivityService | None = None,
        paw_compositor: PawCompositor | None = None,
        paw_motion_config: PawMotionConfig = PawMotionConfig(),
        services: ApplicationServices | None = None,
        persisted_state: dict | None = None,
        animation_sequences: Mapping[str, AnimationSequence] | None = None,
    ) -> None:
        if legacy_mode:
            if (
                compositor is not None
                or cursor_provider is not None
                or head_follow
            ):
                raise ValueError("legacy mode cannot accept eye-follow dependencies")
        elif compositor is None or cursor_provider is None:
            raise ValueError(
                "source-probe construction requires compositor and cursor provider"
            )

        self.root = root
        self._clock = services.runtime.clock.monotonic if services is not None else clock
        self.services = services
        self._persisted_state = dict(persisted_state or {})
        self._runtime_timer: object | None = None
        self._activity_token: ActivityToken | None = None
        self.frames = frames
        saved_window = self._persisted_state.get("window", {})
        saved_height = saved_window.get("height", 280) if isinstance(saved_window, dict) else 280
        self.display_height = clamp_height(saved_height)
        self.always_on_top = True
        self.action_cycle = ActionCycle()
        self._rng = Random()
        self.dialogue = DialogueChooser(load_phrase_pools(), self._rng)
        self._current_image = frames["jump"][0]
        self._resized_image = self._current_image
        self._press_pointer: tuple[int, int] | None = None
        self._press_window: tuple[int, int] | None = None
        self._closed = False
        self._paw_controller: PawPressController | None = None
        self._paw_compositor = paw_compositor
        self._paw_after: object | None = None
        self._paw_base_image: Image.Image | None = None
        self._paw_paused_eye = False
        self._paw_pose = PawPose(PawState.IDLE)
        self._paw_candidate: PawSide | None = None
        self._paw_candidate_exceeded = False
        self._paw_click_consumed = False
        self._window_dragging = False
        self._ole_drag_active = False
        self._paw_activity = paw_activity_service or (
            FoundationPawActivityAdapter(services.runtime.coordinator)
            if services is not None else LocalPawActivityAdapter()
        )
        self._button_state = None
        self._legacy_fallback = bool(legacy_mode)
        self._rendering_available = True
        self._consecutive_renderer_failures = 0
        self._runtime_failure_reported = False
        self._action_ownership_failed = False
        self._active_animation_action: str | None = None
        self._runtime_failure_reporter = (
            runtime_failure_reporter or self._show_runtime_failure
        )
        self._neutral_center_frame: object | None = None
        self.eye_session: RuntimeEyeSession | None = None
        self._eye_interaction_boxes: tuple[tuple[int, int, int, int], ...] = ()
        self._eye_source_size: tuple[int, int] = (0, 0)
        self._eye_hit_test: Callable[[tuple[float, float]], bool] | None = None
        self._region_anchors: dict[str, tuple[int, int]] = {}
        self._presentation_snapshot: _PresentationSnapshot | None = None
        self._startup_presentation_error: Exception | None = None
        self._constructing = True
        self._pending_runtime_failure = False
        self._window_shown = False
        self._window_rect = Rect(
            root.winfo_x(),
            root.winfo_y(),
            1,
            self.display_height,
        )

        try:
            if self.services is not None:
                info = self.services.build_info
                root.title(
                    "桌面宠物 V2.1-CORE | "
                    f"{info.product_version} | git:{info.git_short_hash} | "
                    f"foundation:{info.foundation_commit}"
                )
            else:
                root.title("桌面宠物")
            root.overrideredirect(True)
            root.configure(cursor="hand2")
            root.attributes("-topmost", True)
            root.update_idletasks()
            self.renderer = renderer_factory(root.winfo_id())
            self.renderer.set_topmost(True)
            self.bubble = BubbleWindow(root, renderer_factory=renderer_factory)
            if cursor_service_factory is not None:
                if paw_compositor is None:
                    raise ValueError("cursor service requires paw compositor")
                if button_state_factory is None:
                    raise ValueError("cursor service requires input-router adapter")
                self._button_state = button_state_factory(root.winfo_id())
                self._paw_controller = PawPressController(
                    cursor_service_factory(root.winfo_id()),
                    self,
                    approval_validator=self._paw_activity.validate_paw,
                    on_complete=self._paw_activity.complete_paw,
                    on_cancel=self._paw_activity.cancel_paw,
                    config=paw_motion_config,
                )
            self.animation = AnimationController(
                animation_sequences
                or {
                    action: len(action_frames)
                    for action, action_frames in frames.items()
                },
                self._schedule_animation,
                self._show_animation_frame,
                lambda action: self._animation_finished(action, ""),
                cancel=self._cancel_after,
                finished_with_id=self._animation_finished,
            )
            self._topmost_var = tk.BooleanVar(root, value=True)
            self.menu = self._create_menu()
            self._bind_events()
            root.protocol("WM_DELETE_WINDOW", self.close)
            if self.services is not None:
                self._bind_runtime()
            self._prepare_default_rect(self._current_image)

            cached_compositor: _CachedCenterCompositor | None = None
            if not legacy_mode:
                cached_compositor = _CachedCenterCompositor(compositor)
                self._eye_interaction_boxes = cached_compositor.eye_interaction_boxes
                self._eye_source_size = tuple(cached_compositor.source_size)
                self._eye_hit_test = cached_compositor.hit_test_eye
                midpoint = tuple(int(round(value)) for value in cached_compositor.eye_midpoint)
                self._region_anchors = {"eye-center": midpoint}
                for index, box in enumerate(self._eye_interaction_boxes, start=1):
                    left, top, right, bottom = box
                    self._region_anchors[f"eye-{index}"] = ((left + right) // 2, (top + bottom) // 2)
                self.eye_session = RuntimeEyeSession(
                    compositor=cached_compositor,
                    cursor_provider=cursor_provider,
                    rect_provider=lambda: self._window_rect,
                    display=self._display_eye_frame,
                    scheduler=root.after,
                    cancel=self._cancel_after,
                    clock=clock,
                    on_disabled=self._on_eye_disabled,
                    action_cycle=self.action_cycle,
                    physical_frames=frames,
                    play_action=self._play_action,
                    cancel_action=self._cancel_action,
                    choose_phrase=self.dialogue.choose,
                    present_phrase=self._present_phrase,
                    on_action_failed=self._on_action_failed,
                    head_follow=head_follow,
                    on_ambient_blink_due=(
                        lambda: self._post_and_drain("input.blink")
                        if self.services is not None
                        else None
                    ),
                )
                result = self.eye_session.start()
                self._neutral_center_frame = cached_compositor.center_frame
                if self._startup_presentation_error is not None:
                    raise self._startup_presentation_error
                if result is SessionResult.FALLBACK:
                    self._apply_image(self.frames["jump"][0])
                    self._show_window()
            else:
                self._apply_image(self._current_image)
                self._show_window()

            self._constructing = False
            if self.services is not None:
                self.services.dragdrop.register(self.renderer.hwnd)
                self._schedule_runtime_drain()
            if self._pending_runtime_failure:
                self._report_runtime_failure_once()
        except Exception:
            self._cleanup_partial_construction()
            raise

    def _create_menu(self) -> tk.Menu:
        menu = tk.Menu(self.root, tearoff=False)
        for label, height in SIZE_PRESETS.items():
            menu.add_command(
                label=label,
                command=lambda value=height: self.request_display_height(value),
            )
        menu.add_separator()
        menu.add_checkbutton(
            label="始终置顶",
            variable=self._topmost_var,
            command=lambda: self.request_topmost(self._topmost_var.get()),
        )
        menu.add_separator()
        menu.add_command(label="关于 / 运行状态", command=self._show_about)
        if self.services is not None and self.services.build_info.feature_config.debug_menu_enabled:
            menu.add_command(label="调试", command=self._show_debug_commands)
        menu.add_separator()
        menu.add_command(label="退出", command=self.close)
        return menu

    def _bind_runtime(self) -> None:
        runtime = self.services.runtime
        runtime.bind("input.paw", lambda event: self._trigger_paw_press_direct(PawSide(event.payload["side"])))
        runtime.bind("input.action", self._consume_action)
        runtime.bind("input.graphic-clip", self._consume_graphic_clip)
        runtime.bind("input.blink", self._consume_blink)
        runtime.bind("input.tilt", self._consume_tilt)
        runtime.bind("activity.timer-complete", self._consume_timed_activity_complete)
        runtime.bind("window.move", self._consume_move)
        runtime.bind("input.context_menu", self._consume_context_menu)
        runtime.bind("window.resize", lambda event: self.set_display_height(int(event.payload["height"])))
        runtime.bind("window.topmost", lambda event: self.set_always_on_top(bool(event.payload["enabled"])))
        runtime.bind("dragdrop.enter", self._consume_drag_enter)
        runtime.bind("dragdrop.leave", self._consume_drag_end)
        runtime.bind("dragdrop.drop-rejected", self._consume_drag_end)
        self.services.animation.register(
            "body",
            self._play_registered_graphic,
            self._recover_body_channel,
        )
        config = self.services.build_info.feature_config
        if config.test_build or config.debug_enabled:
            for label, action in ACTION_MENU_ITEMS:
                self.services.debug.register(label, lambda value=action: self.trigger_named_action(value))
            self.services.debug.register("眨眼", self.trigger_blink)
            for label, mode in TILT_MENU_ITEMS:
                self.services.debug.register(label, lambda value=mode: self.trigger_idle_tilt(value))
            self.services.debug.register("区域与锚点", self._show_region_status)
            self.services.debug.register("运行状态", self._show_about)
            self.services.debug.register("日志位置", self._show_log_location)
            self.services.debug.register("取消并安全恢复", self._debug_recover)
            self.services.debug.register("左前肢按压", lambda: self.trigger_paw_press(PawSide.LEFT))
            self.services.debug.register("右前肢按压", lambda: self.trigger_paw_press(PawSide.RIGHT))
            for name in ("饥饿", "舔手", "喂食", "耳朵", "期待"):
                self.services.debug.register(f"{name}（未接入）", lambda: None, enabled=False)

    def _schedule_runtime_drain(self) -> None:
        if self._closed or self.services is None:
            return
        self.services.runtime.drain()
        self._runtime_timer = self.root.after(16, self._schedule_runtime_drain)

    def _post_and_drain(self, event_type: str, **payload: object) -> None:
        if self.services is None:
            return
        self.services.runtime.post(event_type, source="window", **payload)
        self.services.runtime.drain()

    def _consume_action(self, event: RuntimeEvent) -> None:
        current = self.services.runtime.coordinator.current_token
        if current is not None and current.activity is Activity.DRAG_PREVIEW:
            self.services.runtime.coordinator.cancel_and_recover(current)
            return
        action = event.payload.get("action")
        selected = self.action_cycle.peek() if action is None else str(action)
        token = self.services.runtime.coordinator.request_activity(Activity.BODY_ACTION, animation_id=selected)
        if token is None:
            return
        self._activity_token = token
        accepted = self.services.animation.play("body", action, token)
        if not accepted and self._activity_token is token:
            self.services.runtime.coordinator.cancel_and_recover(token)
            self._activity_token = None

    def _consume_graphic_clip(self, event: RuntimeEvent) -> None:
        name = str(event.payload["name"])
        activity = Activity(event.payload["activity"])
        if name not in self.frames or activity not in GRAPHIC_ACTIVITIES:
            raise ValueError("graphic clip requires a registered clip and graphic activity")
        token = self.services.runtime.coordinator.request_activity(
            activity,
            animation_id=name,
        )
        if token is None:
            return
        self._activity_token = token
        if not self.services.animation.play("body", name, token):
            self.services.runtime.coordinator.cancel_and_recover(token)
            self._activity_token = None

    def _play_registered_graphic(self, action: str | None) -> bool:
        if action is None or action in ACTIONS:
            return self._trigger_action_direct(action)
        if self.eye_session is None or self._legacy_fallback:
            return self._play_action(action)
        result = self.eye_session.pause_and_recenter(lambda: self._play_action(action))
        return result is SessionResult.ACCEPTED

    def register_graphic_clip(
        self,
        name: str,
        frames: Sequence[Image.Image],
        sequence: AnimationSequence,
        *,
        _restored_local: bool = False,
    ) -> None:
        """Register validated real RGBA frames; no runtime geometry substitutes."""
        from .assets import validate_runtime_graphic_frame

        graphic_frames = tuple(frames)
        if sequence.layer_mode == "local" and not _restored_local:
            raise ValueError("local clips must provide per-frame restoration layers")
        if not graphic_frames or any(frame.mode != "RGBA" for frame in graphic_frames):
            raise ValueError("graphic clip frames must be RGBA")
        if any(frame.size != graphic_frames[0].size for frame in graphic_frames):
            raise ValueError("graphic clip frames must share one canvas")
        if max(step.frame_index for step in sequence.steps) >= len(graphic_frames):
            raise ValueError("graphic sequence references a missing frame")
        if not (0 <= sequence.anchor[0] <= graphic_frames[0].width and 0 <= sequence.anchor[1] <= graphic_frames[0].height):
            raise ValueError("graphic anchor is outside the canonical canvas")
        expected_canvas = (
            self._neutral_center_frame.size
            if isinstance(self._neutral_center_frame, Image.Image)
            else graphic_frames[0].size
        )
        for frame in graphic_frames:
            validate_runtime_graphic_frame(frame, expected_canvas)
        self.frames[name] = graphic_frames
        self.animation.register_sequence(name, sequence)

    def request_graphic_clip(self, name: str, activity: Activity) -> None:
        if name not in self.frames:
            raise ValueError("graphic clip is not registered")
        if activity not in GRAPHIC_ACTIVITIES:
            raise ValueError("activity does not own graphic playback")
        self._post_and_drain("input.graphic-clip", name=name, activity=activity.value)

    def register_local_graphic_clip(
        self,
        name: str,
        layers: Sequence[Image.Image],
        restorations: Sequence[Image.Image],
        offsets: Sequence[tuple[int, int]],
        sequence: AnimationSequence,
    ) -> None:
        """Compose local art over neutral only after restoring vacated body pixels."""
        from .assets import compose_local_graphic_frame

        if not (len(layers) == len(restorations) == len(offsets)):
            raise ValueError("local clip layers, restorations and offsets must align")
        if sequence.layer_mode != "local":
            raise ValueError("local graphic clip requires local layer mode")
        base = self._neutral_center_frame
        if not isinstance(base, Image.Image):
            raise RuntimeError("neutral graphic base is unavailable")
        frames = tuple(
            compose_local_graphic_frame(
                base,
                layer,
                offset=offset,
                restoration=restoration,
            )
            for layer, restoration, offset in zip(
                layers, restorations, offsets, strict=True
            )
        )
        self.register_graphic_clip(
            name,
            frames,
            sequence,
            _restored_local=True,
        )

    def _consume_move(self, event: RuntimeEvent) -> None:
        self._move_to(int(event.payload["x"]), int(event.payload["y"]))

    def _consume_blink(self, _event: RuntimeEvent) -> None:
        token = self.services.runtime.coordinator.request_activity(Activity.BLINK, timeout_seconds=1.0)
        if token is None:
            return
        self.services.runtime.coordinator.attach_recovery(token, lambda: self.eye_session.cancel_blink())
        if not self._trigger_blink_direct():
            self.services.runtime.coordinator.cancel_and_recover(token)
            return
        self.root.after(600, lambda: self._post_and_drain("activity.timer-complete", token=token))

    def _consume_tilt(self, event: RuntimeEvent) -> None:
        mode = event.payload["mode"]
        token = self.services.runtime.coordinator.request_activity(
            Activity.BODY_ACTION, animation_id=f"tilt:{mode}", timeout_seconds=5.0
        )
        if token is None:
            return
        self.services.runtime.coordinator.attach_recovery(token, lambda: self.eye_session.interrupt_idle())
        if not self._trigger_idle_tilt_direct(mode):
            self.services.runtime.coordinator.cancel_and_recover(token)
            return
        self.root.after(4000, lambda: self._post_and_drain("activity.timer-complete", token=token))

    def _consume_timed_activity_complete(self, event: RuntimeEvent) -> None:
        token = event.payload.get("token")
        if isinstance(token, ActivityToken):
            self.services.runtime.coordinator.complete(token, animation_id=token.animation_id)

    def _recover_body_channel(self) -> bool:
        action = self._active_animation_action
        if action is not None:
            self._cancel_action(action)
        if self.eye_session is not None:
            self.eye_session.cancel_for_recovery()
        if isinstance(self._neutral_center_frame, Image.Image):
            self._apply_image(self._neutral_center_frame, self._anchor())
        self._active_animation_action = None
        return True

    def _consume_drag_enter(self, _event: RuntimeEvent) -> None:
        self.services.runtime.coordinator.request_activity(Activity.DRAG_PREVIEW)

    def _consume_drag_end(self, _event: RuntimeEvent) -> None:
        current = self.services.runtime.coordinator.current_token
        if current is not None and current.activity is Activity.DRAG_PREVIEW:
            self.services.runtime.coordinator.cancel_and_recover(current)

    def _consume_context_menu(self, event: RuntimeEvent) -> None:
        if not self.services.runtime.coordinator.permits(Activity.CONTEXT_MENU_OPEN):
            return
        current = self.services.runtime.coordinator.current_token
        if current is not None and current.activity is not Activity.CONTEXT_MENU_OPEN:
            if self.animation.busy and self._active_animation_action is not None:
                self.services.animation.recover("body", current)
            else:
                self.services.runtime.coordinator.cancel_and_recover(current)
            self._activity_token = None
        token = self.services.runtime.coordinator.request_activity(Activity.CONTEXT_MENU_OPEN)
        if token is None:
            return
        try:
            self.menu.tk_popup(int(event.payload["x"]), int(event.payload["y"]))
        finally:
            self.menu.grab_release()
            self.services.runtime.coordinator.complete(token)

    def _show_about(self) -> None:
        if self.services is None:
            return
        fields = self.services.build_info.as_fields()
        state = self.services.runtime.snapshot()
        message = "\n".join(f"{key}: {value}" for key, value in fields.items())
        message += f"\nactivity: {state.activity.value}\nactivity_version: {state.activity_version}"
        messagebox.showinfo("关于 / 运行状态", message, parent=self.root)

    def _show_region_status(self) -> None:
        messagebox.showinfo("区域与锚点", f"coordinate_version: {self.services.regions.coordinate_version}", parent=self.root)

    def _show_log_location(self) -> None:
        messagebox.showinfo("日志位置", str(self.services.log_path), parent=self.root)

    def _debug_recover(self) -> None:
        self.cancel_paw_press()
        self.services.animation.recover("body", self._activity_token)
        self._activity_token = None

    def _show_debug_commands(self) -> None:
        panel = tk.Toplevel(self.root)
        panel.title("调试")
        height = max(160, int(self.current_screen().height * 0.8))
        panel.geometry(f"360x{height}")
        scrollbar = tk.Scrollbar(panel)
        commands = tk.Listbox(panel, yscrollcommand=scrollbar.set)
        scrollbar.configure(command=commands.yview)
        entries = self.services.debug.commands()
        for name, _command, enabled in entries:
            commands.insert("end", name if enabled else f"{name} [禁用]")
        commands.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        def invoke(_event=None):
            selection = commands.curselection()
            if selection and entries[selection[0]][2]:
                entries[selection[0]][1]()
        commands.bind("<Return>", invoke)
        commands.bind("<Double-Button-1>", invoke)
        commands.bind("<Escape>", lambda _event: panel.destroy())
        commands.bind("<Home>", lambda _event: commands.yview_moveto(0.0))
        commands.bind("<End>", lambda _event: commands.yview_moveto(1.0))
        commands.bind("<MouseWheel>", lambda event: commands.yview_scroll(-1 if event.delta > 0 else 1, "units"))
        commands.focus_set()

    def _bind_events(self) -> None:
        self.root.bind("<ButtonPress-1>", self._on_left_press)
        self.root.bind("<B1-Motion>", self._on_left_motion)
        self.root.bind("<ButtonRelease-1>", self._on_left_release)
        self.root.bind("<Button-3>", self._on_context_menu)
        self.root.bind("<MouseWheel>", self._on_wheel)
        self.root.bind("<FocusOut>", lambda _event: self.cancel_paw_press())

    def _prepare_default_rect(self, image: Image.Image) -> None:
        area = self.current_screen()
        width = max(
            1,
            round(image.width * self.display_height / image.height),
        )
        self._window_rect = Rect(
            area.right - width - 36,
            area.bottom - self.display_height - 36,
            width,
            self.display_height,
        )
        saved = self._persisted_state.get("window", {})
        if isinstance(saved, dict) and all(key in saved for key in ("x", "y")):
            self._window_rect = constrain_rect_to_area(
                Rect(int(saved["x"]), int(saved["y"]), width, self.display_height), area
            )

    def _show_window(self) -> None:
        if self._window_shown:
            return
        self.root.deiconify()
        self.root.lift()
        self._window_shown = True

    def _cleanup_partial_construction(self) -> None:
        self._closed = True
        session = self.eye_session
        if session is not None:
            try:
                session.stop()
            except Exception:
                pass
        animation = getattr(self, "animation", None)
        if animation is not None:
            try:
                animation.stop()
            except Exception:
                pass
        bubble = getattr(self, "bubble", None)
        if bubble is not None:
            try:
                bubble.destroy()
            except Exception:
                pass

    def _anchor(self) -> tuple[int, int]:
        return (
            self._window_rect.x + self._window_rect.width // 2,
            self._window_rect.y + self._window_rect.height,
        )

    def _apply_image(
        self,
        image: Image.Image,
        anchor: tuple[int, int] | None = None,
        *,
        requested_height: int | None = None,
        source_anchor: tuple[int, int] | None = None,
    ) -> None:
        if self._closed or not self._rendering_available:
            raise RuntimeError("pet rendering is unavailable")
        target_height = (
            self.display_height
            if requested_height is None
            else clamp_height(requested_height)
        )
        width = max(1, round(image.width * target_height / image.height))
        if anchor is None:
            x, y = self._window_rect.x, self._window_rect.y
        else:
            if source_anchor is None:
                source_anchor = (image.width // 2, image.height)
            x = anchor[0] - round(source_anchor[0] * width / image.width)
            y = anchor[1] - round(source_anchor[1] * target_height / image.height)
        proposed = Rect(x, y, width, target_height)
        area = self.work_area_for(proposed)
        max_height_by_width = max(
            1, area.width * image.height // image.width
        )
        fitted_height = max(
            1,
            min(
                target_height,
                max(1, area.height),
                max_height_by_width,
            ),
        )
        if fitted_height != target_height:
            width = max(1, round(image.width * fitted_height / image.height))
            if anchor is not None:
                x = anchor[0] - round(source_anchor[0] * width / image.width)
                y = anchor[1] - round(source_anchor[1] * fitted_height / image.height)
            proposed = Rect(x, y, width, fitted_height)
        resized_image = image.convert("RGBA").resize(
            (width, fitted_height), Image.Resampling.LANCZOS
        )
        window_rect = constrain_rect_to_area(proposed, area)
        self._present_candidate(
            image,
            resized_image,
            window_rect,
            fitted_height,
        )

    def _move_to(self, x: int, y: int) -> None:
        if self._closed or not self._rendering_available:
            raise RuntimeError("pet rendering is unavailable")
        proposed = Rect(x, y, self._window_rect.width, self._window_rect.height)
        window_rect = constrain_rect_to_area(
            proposed, self.work_area_for(proposed)
        )
        self._present_candidate(
            self._current_image,
            self._resized_image,
            window_rect,
            self.display_height,
        )

    def _present_candidate(
        self,
        source_image: Image.Image,
        resized_image: Image.Image,
        rect: Rect,
        display_height: int,
    ) -> None:
        input_padding = 16 if self.services is not None else 0
        geometry = (
            f"{rect.width + input_padding * 2}x{rect.height + input_padding * 2}"
            f"{format_position(rect.x - input_padding, rect.y - input_padding)}"
        )
        self._render_candidate(resized_image, rect.x, rect.y)
        try:
            self.root.geometry(geometry)
            padded = getattr(self, "_candidate_padded_image", resized_image)
            set_input_region = getattr(self.renderer, "set_input_region", None)
            if callable(set_input_region):
                set_input_region(padded, expansion=input_padding)
        except Exception as error:
            self._handle_geometry_failure(error)
            raise
        self._current_image = source_image
        self._resized_image = resized_image
        self._window_rect = rect
        self.display_height = display_height
        self._presentation_snapshot = _PresentationSnapshot(
            source_image,
            resized_image,
            rect,
            display_height,
            geometry,
        )
        if self.services is not None:
            self.services.regions.update_pose(
                window=FoundationRect(rect.x, rect.y, rect.width, rect.height),
                source_size=source_image.size,
                anchors=self._region_anchors,
                alpha=resized_image.getchannel("A"),
            )
        self._consecutive_renderer_failures = 0

    def _render_candidate(self, image: Image.Image, x: int, y: int) -> None:
        if self._closed or not self._rendering_available:
            raise RuntimeError("pet rendering is unavailable")
        try:
            if self.services is not None:
                padded = Image.new("RGBA", (image.width + 32, image.height + 32))
                padded.paste(image, (16, 16))
                self._candidate_padded_image = padded
                self.renderer.render(padded, x - 16, y - 16)
            else:
                self.renderer.render(image, x, y)
        except Exception as error:
            self._consecutive_renderer_failures += 1
            if self._presentation_snapshot is None:
                self._startup_presentation_error = error
            elif self._consecutive_renderer_failures >= 2:
                self._mark_rendering_unavailable()
            elif self.animation.busy:
                self._activate_legacy_fallback()
            if (
                not self._constructing
                and (
                    self._presentation_snapshot is None
                    or not self._rendering_available
                )
            ):
                self._report_runtime_failure_once()
            raise

    def _handle_geometry_failure(self, error: Exception) -> None:
        snapshot = self._presentation_snapshot
        if snapshot is None:
            self._startup_presentation_error = error
            self._mark_rendering_unavailable()
            return
        try:
            self._render_candidate(snapshot.resized_image, snapshot.rect.x, snapshot.rect.y)
            self.root.geometry(snapshot.geometry)
        except Exception:
            self._consecutive_renderer_failures = max(
                2, self._consecutive_renderer_failures
            )
            self._mark_rendering_unavailable()
        else:
            self._activate_legacy_fallback()
        if not self._constructing:
            self._report_runtime_failure_once()

    def _mark_rendering_unavailable(self) -> None:
        if not self._rendering_available:
            return
        self._rendering_available = False
        self.cancel_paw_press()
        if self.eye_session is not None:
            self.eye_session.stop()
        animation = getattr(self, "animation", None)
        if animation is not None:
            animation.stop()

    def _fallback_screen(self) -> Rect:
        return Rect(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def current_screen(self) -> Rect:
        self.root.update_idletasks()
        return screen_work_area(self.root.winfo_id(), self._fallback_screen())

    def work_area_for(self, rect: Rect) -> Rect:
        return screen_work_area_for_rect(rect, self._fallback_screen())

    def pet_rect(self) -> Rect:
        return self._window_rect

    def show_at_default_position(self) -> None:
        area = self.current_screen()
        x = area.right - self._window_rect.width - 36
        y = area.bottom - self._window_rect.height - 36
        self._move_to(x, y)
        self.root.deiconify()
        self.root.lift()

    def set_display_height(self, value: int) -> None:
        if self._closed or not self._rendering_available:
            return
        anchor = self._anchor()
        try:
            self._apply_image(
                self._current_image,
                anchor,
                requested_height=clamp_height(value),
            )
        except Exception:
            return
        self.bubble.reposition(self.pet_rect(), self.current_screen())

    def request_display_height(self, value: int) -> None:
        if self.services is not None:
            self._post_and_drain("window.resize", height=value)
        else:
            self.set_display_height(value)

    def set_always_on_top(self, enabled: bool) -> None:
        self.always_on_top = bool(enabled)
        self._topmost_var.set(self.always_on_top)
        self.root.attributes("-topmost", self.always_on_top)
        self.renderer.set_topmost(self.always_on_top)
        self.bubble.set_always_on_top(self.always_on_top)
        self.root.lift()

    def request_topmost(self, enabled: bool) -> None:
        if self.services is not None:
            self._post_and_drain("window.topmost", enabled=enabled)
        else:
            self.set_always_on_top(enabled)

    def handle_left_release(
        self,
        press: tuple[int, int],
        release: tuple[int, int],
    ) -> None:
        distance = abs(release[0] - press[0]) + abs(release[1] - press[1])
        if distance >= CLICK_THRESHOLD:
            return
        if self._point_in_eye_region(press):
            self.trigger_blink()
            return
        self.trigger_next_action()

    def _point_in_eye_region(self, point: tuple[int, int]) -> bool:
        source_width, source_height = self._eye_source_size
        rect = self._window_rect
        if (
            not self._eye_interaction_boxes
            or source_width <= 0
            or source_height <= 0
            or rect.width <= 0
            or rect.height <= 0
        ):
            return False
        source_x = (point[0] - rect.x) * source_width / rect.width
        source_y = (point[1] - rect.y) * source_height / rect.height
        eye_hit_test = getattr(self, "_eye_hit_test", None)
        if eye_hit_test is not None:
            return eye_hit_test((source_x, source_y))
        return any(
            left <= source_x < right and top <= source_y < bottom
            for left, top, right, bottom in self._eye_interaction_boxes
        )

    def trigger_next_action(self) -> None:
        if self.services is not None:
            self._post_and_drain("input.action", action=None)
            return
        self._trigger_action_direct(None)

    def trigger_named_action(self, action: str) -> None:
        if action not in ACTIONS:
            raise ValueError("named action is invalid")
        if self.services is not None:
            self._post_and_drain("input.action", action=action)
            return
        self._trigger_action_direct(action)

    def trigger_blink(self) -> None:
        if self.services is not None:
            self._post_and_drain("input.blink")
            return
        self._trigger_blink_direct()

    def _trigger_blink_direct(self) -> bool:
        if self.services is not None and self.services.runtime.snapshot().activity is Activity.DRAG_PREVIEW:
            return False
        if (
            self._closed
            or not self._rendering_available
            or self.eye_session is None
            or self._legacy_fallback
        ):
            return False
        return self.eye_session.request_blink() is SessionResult.ACCEPTED

    # PawInputGate adapter. Foundation InputRouter/ActivityCoordinator can
    # replace these reads without changing the feature controller.
    def any_button_down(self) -> bool:
        return bool(self._button_state and self._button_state.any_button_down())

    def pointer_interaction_blocked(self) -> bool:
        return self._window_dragging or self._ole_drag_active

    def paw_activity_allowed(self) -> bool:
        return (
            not self._closed
            and self._rendering_available
            and not self.animation.busy
            and not self.pointer_interaction_blocked()
        )

    def trigger_paw_press(self, side: PawSide) -> None:
        if self.services is not None:
            self._post_and_drain("input.paw", side=side.value)
        else:
            self._trigger_paw_press_direct(side)

    def _trigger_paw_press_direct(self, side: PawSide) -> None:
        controller = self._paw_controller
        if (controller is None or not self.paw_activity_allowed()
                or not self._paw_activity.paw_allowed()):
            return
        approval = self._paw_activity.request_paw(side)
        if approval is None:
            return
        self._paw_base_image = self._current_image
        try:
            if controller.start(side, approval, self._clock()):
                self._paw_activity.attach_paw_recovery(
                    approval, lambda: self.cancel_paw_press(notify=False)
                )
                def begin_presentation() -> None:
                    if not controller.begin_presentation(self._clock()):
                        return
                    self._paw_base_image = self._current_image
                    self._paw_tick()
                if self.eye_session is not None and not self._legacy_fallback:
                    self._paw_paused_eye = True
                    outcome = self.eye_session.pause_and_recenter(begin_presentation)
                    if outcome is SessionResult.FALLBACK:
                        self._paw_paused_eye = False
                        begin_presentation()
                    elif outcome is not SessionResult.ACCEPTED:
                        self._paw_paused_eye = False
                        self.cancel_paw_press()
                else:
                    begin_presentation()
            else:
                self._paw_activity.complete_paw(approval)
        except Exception:
            self._paw_activity.complete_paw(approval)
            self.cancel_paw_press()

    def _paw_tick(self) -> None:
        controller, base = self._paw_controller, self._paw_base_image
        if controller is None or base is None or self._closed:
            return
        try:
            pose = controller.sample(self._clock())
            self._paw_pose = pose
            if pose.state is PawState.IDLE:
                self._apply_image(base, self._anchor())
                self._paw_base_image = None
                self._paw_pose = PawPose(PawState.IDLE)
                self._paw_after = None
                self._resume_paw_eye()
                return
            image = self._paw_compositor.compose_frame(
                base, controller.side.value, pose.frame_index
            )
            self._apply_image(image, self._anchor())
            self._paw_after = self.root.after(16, self._paw_tick)
        except Exception:
            self.cancel_paw_press()

    def cancel_paw_press(self, *, notify: bool = True) -> None:
        if self._paw_controller is not None:
            self._paw_controller.cancel(notify=notify)
        if self._paw_after is not None:
            self._cancel_after(self._paw_after)
            self._paw_after = None
        base, self._paw_base_image = self._paw_base_image, None
        self._paw_pose = PawPose(PawState.IDLE)
        if base is not None and not self._closed and self._rendering_available:
            try:
                self._apply_image(base, self._anchor())
            except Exception:
                pass
        self._resume_paw_eye()

    def _resume_paw_eye(self) -> None:
        if self._paw_paused_eye:
            self._paw_paused_eye = False
            if self.eye_session is not None:
                self.eye_session.cancel_for_recovery()

    def trigger_idle_tilt(self, mode: TiltMode) -> None:
        if mode not in TILT_MODES:
            raise ValueError("idle tilt mode is invalid")
        if self.services is not None:
            self._post_and_drain("input.tilt", mode=mode)
            return
        self._trigger_idle_tilt_direct(mode)

    def _trigger_idle_tilt_direct(self, mode: TiltMode) -> bool:
        if (
            self._closed
            or not self._rendering_available
            or self.eye_session is None
            or self._legacy_fallback
        ):
            return False
        return self.eye_session.request_idle_tilt(mode) is SessionResult.ACCEPTED

    def _trigger_action_direct(self, action: str | None) -> bool:
        self.cancel_paw_press()
        if (
            self._closed
            or not self._rendering_available
            or self._action_ownership_failed
            or self.animation.busy
        ):
            return False
        if self.eye_session is not None and not self._legacy_fallback:
            result = (
                self.eye_session.request_action()
                if action is None
                else self.eye_session.request_named_action(action)
            )
            if result is not SessionResult.FALLBACK:
                return result is SessionResult.ACCEPTED
            self._activate_legacy_fallback()
        return self._trigger_legacy_action(action)

    def _trigger_legacy_action(self, requested_action: str | None = None) -> bool:
        if self.animation.busy:
            return False
        action = (
            self.action_cycle.peek()
            if requested_action is None
            else requested_action
        )
        try:
            accepted = self._play_action(action)
        except Exception:
            self._handle_action_callback_failure()
            return False
        if accepted is not True:
            return False
        if requested_action is None:
            try:
                self.action_cycle.commit(action)
            except Exception:
                if self._cancel_action(action) is not True:
                    self._on_action_failed(action, ActionFailure.CANCEL_REJECTED)
                return False
        try:
            phrase = self.dialogue.choose(action)
            self._present_phrase(phrase)
        except Exception:
            pass
        return True

    def show_frame(self, action: str, index: int) -> None:
        self._show_animation_frame(action, index)

    def _show_animation_frame(self, action: str, index: int) -> None:
        if self._closed or not self._rendering_available:
            raise RuntimeError("pet rendering is unavailable")
        self._active_animation_action = action
        source_anchor = self.animation.sequence(action).anchor
        if action not in ACTIONS or self._legacy_fallback or self.eye_session is None:
            image = self.frames[action][index]
        else:
            image = self.eye_session.logical_frame(action, index)
            if index in (0, 5):
                # Logical neutral frames use the wider eye compositor canvas.
                source_anchor = (image.width // 2, image.height)
        if (
            index == 0
            and self._presentation_snapshot is not None
            and image is self._current_image
        ):
            return
        self._apply_image(
            image,
            self._anchor(),
            source_anchor=source_anchor,
        )

    def _animation_finished(self, action: str, playback_id: str) -> None:
        token = self._activity_token
        if self.services is not None:
            if token is None or token.cancellation_id != playback_id or token.animation_id != action:
                return
            completed = self.services.animation.complete_current("body", action)
            if completed != token:
                return
            self._activity_token = None
        self._active_animation_action = None
        if not self._closed and action not in ACTIONS and isinstance(self._neutral_center_frame, Image.Image):
            self._apply_image(self._neutral_center_frame, self._anchor())
        if self._closed or self._legacy_fallback or self.eye_session is None:
            return
        if action in ACTIONS:
            self.eye_session.animation_finished(action)
        else:
            self.eye_session.resume_following()

    def _play_action(self, action: str) -> bool:
        if self.services is not None:
            token = self.services.runtime.coordinator.current_token
            if token is None or token.activity not in GRAPHIC_ACTIVITIES or token.animation_id != action:
                return False
        try:
            token = self.services.runtime.coordinator.current_token if self.services is not None else None
            accepted = self.animation.play(
                action,
                playback_id=token.cancellation_id if token is not None else None,
            )
        except Exception:
            if not self.animation.busy:
                self._active_animation_action = None
            raise
        if accepted is not True and not self.animation.busy:
            self._active_animation_action = None
        return accepted

    def _cancel_action(self, action: str) -> bool:
        cancelled = self.animation.cancel_current(action)
        if cancelled is True:
            self._active_animation_action = None
        return cancelled

    def _display_eye_frame(self, frame: object) -> None:
        if not isinstance(frame, Image.Image):
            raise TypeError("eye compositor must return a Pillow image")
        displayed = frame
        if self._paw_base_image is not None and self._paw_compositor is not None:
            self._paw_base_image = frame
            side = self._paw_controller.side
            if side is not None:
                displayed = self._paw_compositor.compose_frame(
                    frame, side.value, self._paw_pose.frame_index
                )
        self._apply_image(displayed, self._anchor())
        if self._neutral_center_frame is None:
            self._neutral_center_frame = frame
        if self._constructing and not self._window_shown:
            try:
                self._show_window()
            except Exception as error:
                self._startup_presentation_error = error
                raise

    def _present_phrase(self, phrase: str) -> None:
        if self._closed:
            return
        self.bubble.show_message(
            phrase,
            self.pet_rect(),
            self.current_screen(),
        )

    def _schedule_animation(
        self, delay_ms: int, callback: Callable[[], None]
    ) -> object:
        def guarded_callback() -> None:
            if self._closed:
                return
            try:
                callback()
            except Exception:
                self._handle_action_callback_failure()

        return self.root.after(delay_ms, guarded_callback)

    def _cancel_after(self, token: object) -> None:
        try:
            self.root.after_cancel(token)
        except tk.TclError:
            pass

    def _on_eye_disabled(self) -> None:
        self._legacy_fallback = True
        if self._constructing:
            self._pending_runtime_failure = True
        else:
            self._report_runtime_failure_once()

    def _activate_legacy_fallback(self) -> None:
        if self._closed or not self._rendering_available:
            return
        if self.animation.busy:
            action = self._active_animation_action
            try:
                cancelled = (
                    action is not None and self._cancel_action(action)
                )
            except Exception:
                cancelled = False
            if cancelled is not True:
                self._on_action_failed(
                    action or "unknown",
                    ActionFailure.CANCEL_REJECTED,
                )
                return
        self._legacy_fallback = True
        if self.eye_session is not None and self.eye_session.state not in (
            "disabled",
            "stopped",
        ):
            self.eye_session.stop()

    def _handle_action_callback_failure(self) -> None:
        if self._closed or not self._rendering_available:
            return
        self.cancel_paw_press()
        if not self.animation.busy:
            self._active_animation_action = None
        if self.eye_session is not None:
            self.eye_session.stop()
        self._legacy_fallback = True
        self._report_runtime_failure_once()

    def _on_action_failed(
        self, _action: str, _failure: ActionFailure
    ) -> None:
        if self._closed:
            return
        self._action_ownership_failed = True
        if self.services is not None:
            self.services.animation.recover("body", self._activity_token)
            self._activity_token = None
        if self.eye_session is not None:
            self.eye_session.stop()
        self.animation.stop()
        self._report_runtime_failure_once(
            "动作播放已安全停止；请重启桌面宠物。"
        )

    def _show_runtime_failure(self, message: str) -> None:
        del message

    def _report_runtime_failure_once(
        self,
        message: str = "眼睛跟随已停用，点击动作仍可继续。",
    ) -> None:
        if self._runtime_failure_reported:
            return
        self._runtime_failure_reported = True
        try:
            self._runtime_failure_reporter(message)
        except Exception:
            pass

    def close(self) -> None:
        if self._closed:
            return
        if self._paw_controller is not None:
            self._paw_controller.close()
        if self._paw_after is not None:
            self._cancel_after(self._paw_after)
            self._paw_after = None
        self._closed = True
        if self._runtime_timer is not None:
            self._cancel_after(self._runtime_timer)
            self._runtime_timer = None
        if self.eye_session is not None:
            self.eye_session.stop()
        self.animation.stop()
        self.bubble.destroy()
        if self.services is not None:
            window_state = {
                "x": self._window_rect.x,
                "y": self._window_rect.y,
                "height": self.display_height,
            }
            try:
                self.services.update_state(
                    lambda state: state.__setitem__("window", window_state),
                    durable=True,
                )
            except (OSError, RuntimeError, ValueError):
                pass
            finally:
                try:
                    self.services.close()
                except (OSError, RuntimeError, ValueError):
                    pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _on_left_press(self, event: tk.Event) -> None:
        interrupt_idle = getattr(self.eye_session, "interrupt_idle", None)
        if callable(interrupt_idle):
            interrupt_idle()
        self._press_pointer = (event.x_root, event.y_root)
        self._press_window = (self._window_rect.x, self._window_rect.y)
        self._window_dragging = False
        self._paw_candidate_exceeded = False
        pressed_paw = self._paw_side_at(self._press_pointer)
        self._paw_click_consumed = pressed_paw is not None
        self._paw_candidate = (
            pressed_paw
            if self._paw_controller is not None
            and self._paw_controller.state is PawState.IDLE
            else None
        )

    def _on_left_motion(self, event: tk.Event) -> None:
        if self._press_pointer is None or self._press_window is None:
            return
        delta_x = event.x_root - self._press_pointer[0]
        delta_y = event.y_root - self._press_pointer[1]
        if not self._drag_threshold_exceeded(delta_x, delta_y):
            return
        self._paw_candidate_exceeded = True
        self._window_dragging = True
        try:
            x = self._press_window[0] + delta_x
            y = self._press_window[1] + delta_y
            if self.services is not None:
                self._post_and_drain("window.move", x=x, y=y)
            else:
                self._move_to(x, y)
        except Exception:
            return
        self.bubble.reposition(self.pet_rect(), self.current_screen())

    def _on_left_release(self, event: tk.Event) -> None:
        candidate = self._paw_candidate
        should_start_paw = (
            candidate is not None
            and not self._paw_candidate_exceeded
            and self._paw_side_at((event.x_root, event.y_root)) is candidate
            and not self.any_button_down()
            and not self._ole_drag_active
        )
        if (self._press_pointer is not None and candidate is None
                and not self._paw_click_consumed):
            self.handle_left_release(
                self._press_pointer,
                (event.x_root, event.y_root),
            )
        self._press_pointer = None
        self._press_window = None
        self._paw_candidate = None
        self._paw_candidate_exceeded = False
        self._paw_click_consumed = False
        self._window_dragging = False
        if should_start_paw:
            self.trigger_paw_press(candidate)

    def _paw_side_at(self, point: tuple[int, int]) -> PawSide | None:
        compositor = self._paw_compositor
        if compositor is None:
            return None
        if compositor.hit_test("left", point, self._window_rect):
            return PawSide.LEFT
        if compositor.hit_test("right", point, self._window_rect):
            return PawSide.RIGHT
        return None

    def _on_context_menu(self, event: tk.Event) -> None:
        self.cancel_paw_press()
        if self.services is not None:
            self._post_and_drain("input.context_menu", x=event.x_root, y=event.y_root)
            return
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    @staticmethod
    def _drag_threshold_exceeded(delta_x: int, delta_y: int) -> bool:
        if os.name == "nt":
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            return abs(delta_x) >= user32.GetSystemMetrics(68) or abs(delta_y) >= user32.GetSystemMetrics(69)
        return abs(delta_x) + abs(delta_y) >= CLICK_THRESHOLD

    def _on_wheel(self, event: tk.Event) -> None:
        delta = 24 if event.delta > 0 else -24
        self.request_display_height(self.display_height + delta)

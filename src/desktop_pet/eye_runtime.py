"""Pure runtime ownership for cursor-following eye frames."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Callable, Literal, Protocol

from .eye_follow import (
    CursorProvider,
    EyeGeometry,
    EyeMotionController,
    SAMPLE_INTERVAL_MS,
)
from .blink import NaturalBlinkMotion
from .head_neck_deformation import HeadPose
from .model import ACTIONS, ActionCycle


RECENTER_DURATION_SECONDS = 0.132
_RECENTER_SCHEDULING = object()

SessionState = Literal[
    "following", "recentering", "playing", "disabled", "stopped"
]


class SessionResult(Enum):
    """Explicit outcome for ownership transitions."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FALLBACK = "fallback"


class ActionFailure(Enum):
    """Observable action-owner failures requiring adapter intervention."""

    CANCEL_REJECTED = "cancel_rejected"
    CANCEL_RAISED = "cancel_raised"


class Compositor(Protocol):
    source_size: tuple[int, int]
    eye_midpoint: tuple[float, float]

    def compose(self, eye_x: float, eye_y: float) -> object: ...


class RectLike(Protocol):
    x: int
    y: int
    width: int
    height: int


class RuntimeEyeSession:
    """Coordinate one eye loop, recenter ownership, and disabled fallback."""

    def __init__(
        self,
        *,
        compositor: Compositor,
        cursor_provider: CursorProvider,
        rect_provider: Callable[[], RectLike],
        display: Callable[[object], None],
        scheduler: Callable[[int, Callable[[], None]], object],
        cancel: Callable[[object], None],
        clock: Callable[[], float] = time.monotonic,
        on_disabled: Callable[[], None],
        action_cycle: ActionCycle,
        physical_frames: Mapping[str, Sequence[object]],
        play_action: Callable[[str], bool],
        cancel_action: Callable[[str], bool],
        choose_phrase: Callable[[str], str],
        present_phrase: Callable[[str], None],
        on_action_failed: Callable[[str, ActionFailure], None],
        head_follow: bool = False,
        blink_motion: NaturalBlinkMotion | None = None,
    ) -> None:
        self._compositor = compositor
        self._head_follow = bool(head_follow)
        if self._head_follow and not callable(
            getattr(compositor, "compose_head", None)
        ):
            raise ValueError("head-follow compositor must expose compose_head")
        blink_method = (
            getattr(compositor, "compose_head_blink", None)
            if self._head_follow
            else getattr(compositor, "compose_blink", None)
        )
        self._blink_supported = callable(blink_method)
        if blink_motion is not None and not self._blink_supported:
            raise ValueError("blink motion requires a blink-capable compositor")
        self._blink_motion = (
            blink_motion
            if blink_motion is not None
            else NaturalBlinkMotion() if self._blink_supported else None
        )
        self._blink_closure = 0.0
        self._rect_provider = rect_provider
        self._display = display
        self._scheduler = scheduler
        self._cancel = cancel
        self._clock = clock
        self._on_disabled = on_disabled
        self._action_cycle = action_cycle
        self._physical_frames = self._validate_physical_frames(physical_frames)
        self._play_action = play_action
        self._cancel_action = cancel_action
        self._choose_phrase = choose_phrase
        self._present_phrase = present_phrase
        self._on_action_failed = on_action_failed

        self._source_width, self._source_height = self._valid_pair(
            compositor.source_size, "source size"
        )
        if self._source_width <= 0.0 or self._source_height <= 0.0:
            raise ValueError("source size must be positive")
        self._midpoint_x, self._midpoint_y = self._valid_pair(
            compositor.eye_midpoint, "eye midpoint"
        )

        self._state: SessionState = "stopped"
        self._lifecycle_epoch = 0
        self._terminal = False
        self._start_attempted = False
        self._disabled_notified = False
        self._last_displayed_pose: tuple[float, float] | None = None
        self._last_displayed_head_pose: tuple[float, float] | None = None
        self._center_frame: object | None = None
        self._pending_action: str | None = None
        self._active_action: str | None = None
        self._starting_action: str | None = None
        self._early_finish = False
        self._action_failure: tuple[str, ActionFailure] | None = None
        self._recenter_token: object | None = None
        self._recenter_slot: object | None = None
        self._recenter_generation = 0
        self._recenter_started_at = 0.0
        self._recenter_start_pose = (0.0, 0.0)
        self._recenter_start_head_pose = (0.0, 0.0)
        self._recenter_complete: Callable[[], None] | None = None

        self._controller = EyeMotionController(
            self._schedule_eye_tick,
            cancel,
            cursor_provider,
            self._eye_geometry,
            self._following_pose_changed,
            clock=clock,
            coordinated_pose_changed=(
                self._following_coordinated_pose_changed
                if self._head_follow
                else None
            ),
            pulse=(
                self._following_blink_pulse
                if self._blink_motion is not None
                else None
            ),
        )

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def last_displayed_pose(self) -> tuple[float, float] | None:
        return self._last_displayed_pose

    @property
    def last_displayed_head_pose(self) -> tuple[float, float] | None:
        return self._last_displayed_head_pose

    @property
    def action_failure(self) -> tuple[str, ActionFailure] | None:
        return self._action_failure

    def start(self) -> SessionResult:
        if self._state == "disabled":
            return SessionResult.FALLBACK
        if self._state == "following":
            return SessionResult.ACCEPTED
        if self._terminal or self._start_attempted:
            return SessionResult.REJECTED

        self._start_attempted = True
        epoch = self._lifecycle_epoch
        if not self._try_display_pose((0.0, 0.0), epoch, "stopped"):
            if self._state == "disabled":
                return SessionResult.FALLBACK
            return SessionResult.REJECTED
        if not self._work_is_current(epoch, "stopped"):
            return SessionResult.REJECTED
        self._transition("following")
        following_epoch = self._lifecycle_epoch
        try:
            self._controller.start()
        except Exception:
            if self._work_is_current(following_epoch, "following"):
                self._disable()
            return (
                SessionResult.FALLBACK
                if self._state == "disabled"
                else SessionResult.REJECTED
            )
        if not self._work_is_current(following_epoch, "following"):
            return (
                SessionResult.FALLBACK
                if self._state == "disabled"
                else SessionResult.REJECTED
            )
        return SessionResult.ACCEPTED

    def pause_and_recenter(
        self, on_complete: Callable[[], None]
    ) -> SessionResult:
        if self._terminal:
            return SessionResult.REJECTED
        if self._state == "disabled":
            return SessionResult.FALLBACK
        if self._state != "following":
            return SessionResult.REJECTED

        self._transition("recentering")
        epoch = self._lifecycle_epoch
        try:
            self._controller.pause()
        except Exception:
            if self._work_is_current(epoch, "recentering"):
                self._disable()
            return (
                SessionResult.FALLBACK
                if self._state == "disabled"
                else SessionResult.REJECTED
            )
        if not self._work_is_current(epoch, "recentering"):
            return (
                SessionResult.FALLBACK
                if self._state == "disabled"
                else SessionResult.REJECTED
            )
        self._recenter_generation += 1
        try:
            self._recenter_started_at = self._clock()
        except Exception:
            if self._work_is_current(epoch, "recentering"):
                self._disable()
            return SessionResult.FALLBACK
        self._recenter_start_pose = self._last_displayed_pose or (0.0, 0.0)
        self._recenter_start_head_pose = (
            self._last_displayed_head_pose or (0.0, 0.0)
        )
        self._recenter_complete = on_complete

        if (
            self._recenter_start_pose == (0.0, 0.0)
            and self._recenter_start_head_pose == (0.0, 0.0)
        ):
            self._finish_recenter(epoch)
            if self._state == "disabled":
                return SessionResult.FALLBACK
            return SessionResult.ACCEPTED

        if self._schedule_recenter():
            return SessionResult.ACCEPTED
        return (
            SessionResult.FALLBACK
            if self._state == "disabled"
            else SessionResult.REJECTED
        )

    def resume_following(self) -> SessionResult:
        if self._terminal:
            return SessionResult.REJECTED
        if self._state == "disabled":
            return SessionResult.FALLBACK
        if self._state == "following":
            return SessionResult.ACCEPTED
        if self._state != "playing":
            return SessionResult.REJECTED
        if (
            self._action_failure is not None
            or self._pending_action is not None
            or self._active_action is not None
            or self._starting_action is not None
        ):
            return SessionResult.REJECTED

        self._transition("following")
        epoch = self._lifecycle_epoch
        try:
            self._controller.resume()
        except Exception:
            if self._work_is_current(epoch, "following"):
                self._disable()
            return (
                SessionResult.FALLBACK
                if self._state == "disabled"
                else SessionResult.REJECTED
            )
        if not self._work_is_current(epoch, "following"):
            return (
                SessionResult.FALLBACK
                if self._state == "disabled"
                else SessionResult.REJECTED
            )
        return SessionResult.ACCEPTED

    def request_blink(self) -> SessionResult:
        """Restart one ordinary blink without pausing cursor following."""

        if self._terminal:
            return SessionResult.REJECTED
        if self._state == "disabled":
            return SessionResult.FALLBACK
        if self._state != "following" or self._blink_motion is None:
            return SessionResult.REJECTED
        try:
            self._blink_motion.trigger(self._clock())
        except Exception:
            self._blink_motion = None
            self._blink_closure = 0.0
            return SessionResult.REJECTED
        if self._blink_closure != 0.0:
            self._blink_closure = 0.0
            pose = self._last_displayed_pose or (0.0, 0.0)
            head_pose = self._last_displayed_head_pose or (0.0, 0.0)
            self._try_display_pose(
                pose,
                self._lifecycle_epoch,
                "following",
                head_pose,
            )
        return SessionResult.ACCEPTED

    def request_action(self) -> SessionResult:
        if self._terminal:
            return SessionResult.REJECTED
        if self._state == "disabled":
            return SessionResult.FALLBACK
        if self._state != "following":
            return SessionResult.REJECTED
        if (
            self._pending_action is not None
            or self._active_action is not None
            or self._starting_action is not None
        ):
            return SessionResult.REJECTED

        action = self._action_cycle.peek()
        self._action_failure = None
        self._pending_action = action
        self._early_finish = False
        result = self.pause_and_recenter(lambda: self._begin_action(action))
        if result is not SessionResult.ACCEPTED and self._pending_action == action:
            self._pending_action = None
        return result

    def logical_frame(self, action: str, index: int) -> object:
        if not isinstance(index, int) or not 0 <= index < 6:
            raise IndexError("logical action frame index must be between 0 and 5")
        if (
            self._state != "playing"
            or action not in (self._pending_action, self._active_action)
        ):
            raise RuntimeError("logical action frame is not owned by this session")
        if self._center_frame is None:
            raise RuntimeError("logical action frames are unavailable")
        if index in (0, 5):
            return self._center_frame
        return self._physical_frames[action][index]

    def animation_finished(self, action: str) -> SessionResult:
        if self._terminal:
            return SessionResult.REJECTED
        if self._early_finish and action in (
            self._pending_action,
            self._active_action,
            self._starting_action,
        ):
            return SessionResult.REJECTED
        if (
            self._state == "playing"
            and self._active_action is None
            and self._pending_action == action
            and self._starting_action == action
            and not self._early_finish
        ):
            self._early_finish = True
            return SessionResult.ACCEPTED
        if (
            self._state != "playing"
            or self._active_action is None
            or action != self._active_action
        ):
            return SessionResult.REJECTED
        return self._complete_active_action(action, self._lifecycle_epoch)

    def stop(self) -> None:
        if self._terminal:
            return
        self._terminal = True
        self._lifecycle_epoch += 1
        self._state = "stopped"
        self._pending_action = None
        self._active_action = None
        self._starting_action = None
        self._early_finish = False
        try:
            self._invalidate_recenter()
        except Exception:
            pass
        self._controller.stop()

    def _following_blink_pulse(self) -> None:
        if self._state != "following" or self._blink_motion is None:
            return
        try:
            closure = self._blink_motion.sample(self._clock())
        except Exception:
            self._blink_motion = None
            self._blink_closure = 0.0
            return
        if closure == self._blink_closure:
            return
        self._blink_closure = closure
        pose = self._last_displayed_pose or (0.0, 0.0)
        head_pose = self._last_displayed_head_pose or (0.0, 0.0)
        self._try_display_pose(
            pose,
            self._lifecycle_epoch,
            "following",
            head_pose,
        )

    def _following_pose_changed(self, eye_x: float, eye_y: float) -> None:
        if self._state != "following":
            return
        epoch = self._lifecycle_epoch
        self._try_display_pose((eye_x, eye_y), epoch, "following")

    def _following_coordinated_pose_changed(
        self,
        eye_x: float,
        eye_y: float,
        head_x: float,
        head_y: float,
    ) -> None:
        if self._state != "following":
            return
        epoch = self._lifecycle_epoch
        self._try_display_pose(
            (eye_x, eye_y),
            epoch,
            "following",
            (head_x, head_y),
        )

    def _try_display_pose(
        self,
        pose: tuple[float, float],
        epoch: int,
        expected_state: SessionState,
        head_pose: tuple[float, float] = (0.0, 0.0),
    ) -> bool:
        if not self._work_is_current(epoch, expected_state):
            return False
        try:
            if self._head_follow:
                if self._blink_motion is not None:
                    compose_head_blink = getattr(
                        self._compositor, "compose_head_blink"
                    )
                    frame = compose_head_blink(
                        *pose,
                        HeadPose(*head_pose),
                        self._blink_closure,
                    )
                else:
                    compose_head = getattr(self._compositor, "compose_head")
                    frame = compose_head(*pose, HeadPose(*head_pose))
            elif self._blink_motion is not None:
                compose_blink = getattr(self._compositor, "compose_blink")
                frame = compose_blink(*pose, self._blink_closure)
            else:
                frame = self._compositor.compose(*pose)
        except Exception:
            if (
                expected_state != "following"
                and self._work_is_current(epoch, expected_state)
            ):
                self._disable()
            return False
        if not self._work_is_current(epoch, expected_state):
            return False
        try:
            self._display(frame)
        except Exception:
            if (
                expected_state != "following"
                and self._work_is_current(epoch, expected_state)
            ):
                self._disable()
            return False
        if not self._work_is_current(epoch, expected_state):
            return False
        self._last_displayed_pose = pose
        if self._head_follow:
            self._last_displayed_head_pose = head_pose
        if expected_state == "stopped" and pose == (0.0, 0.0):
            self._center_frame = frame
        return True

    def _begin_action(self, action: str) -> None:
        if self._state != "playing" or self._pending_action != action:
            return
        epoch = self._lifecycle_epoch
        self._starting_action = action
        try:
            accepted = self._play_action(action)
        except Exception:
            if self._work_is_current(epoch, "playing"):
                self._abandon_action_request()
            return
        if not self._work_is_current(epoch, "playing"):
            return
        if accepted is not True:
            self._abandon_action_request()
            return

        try:
            self._action_cycle.commit(action)
        except Exception:
            if self._work_is_current(epoch, "playing"):
                self._cancel_accepted_action(action, epoch)
            return
        if not self._work_is_current(epoch, "playing"):
            return
        self._pending_action = None
        self._active_action = action
        self._starting_action = None

        try:
            phrase = self._choose_phrase(action)
        except Exception:
            phrase = None
        if phrase is not None and self._work_is_current(epoch, "playing"):
            try:
                self._present_phrase(phrase)
            except Exception:
                pass
        if self._work_is_current(epoch, "playing") and self._early_finish:
            self._early_finish = False
            self._complete_active_action(action, epoch)

    def _cancel_accepted_action(self, action: str, epoch: int) -> None:
        if self._early_finish:
            self._abandon_action_request()
            return
        try:
            cancelled = self._cancel_action(action)
        except Exception:
            if self._work_is_current(epoch, "playing"):
                self._report_action_failure(
                    action, ActionFailure.CANCEL_RAISED, epoch
                )
            return
        if self._work_is_current(epoch, "playing") and cancelled is True:
            self._abandon_action_request()
        elif self._work_is_current(epoch, "playing"):
            self._report_action_failure(
                action, ActionFailure.CANCEL_REJECTED, epoch
            )

    def _report_action_failure(
        self, action: str, failure: ActionFailure, epoch: int
    ) -> None:
        if not self._work_is_current(epoch, "playing"):
            return
        self._action_failure = (action, failure)
        try:
            self._on_action_failed(action, failure)
        except Exception:
            pass

    def _complete_active_action(
        self, action: str, epoch: int
    ) -> SessionResult:
        if self._active_action != action:
            return SessionResult.REJECTED
        self._synchronize_controller_center()
        if not self._work_is_current(epoch, "playing"):
            return SessionResult.REJECTED
        self._pending_action = None
        self._active_action = None
        self._starting_action = None
        self._early_finish = False
        self._transition("following")
        following_epoch = self._lifecycle_epoch
        try:
            self._controller.resume()
        except Exception:
            if self._work_is_current(following_epoch, "following"):
                self._disable()
            return (
                SessionResult.FALLBACK
                if self._state == "disabled"
                else SessionResult.REJECTED
            )
        if not self._work_is_current(following_epoch, "following"):
            return (
                SessionResult.FALLBACK
                if self._state == "disabled"
                else SessionResult.REJECTED
            )
        return SessionResult.ACCEPTED

    def _abandon_action_request(self) -> None:
        self._pending_action = None
        self._active_action = None
        self._starting_action = None
        self._early_finish = False
        self._transition("following")
        epoch = self._lifecycle_epoch
        try:
            self._controller.resume()
        except Exception:
            if self._work_is_current(epoch, "following"):
                self._disable()
            return
        if not self._work_is_current(epoch, "following"):
            return

    def _schedule_recenter(self) -> bool:
        if (
            self._terminal
            or self._state != "recentering"
            or self._recenter_token is not None
        ):
            return False
        generation = self._recenter_generation
        slot = object()
        fired = False
        scheduler_returned = False

        def scheduled_callback() -> None:
            nonlocal fired
            fired = True
            if scheduler_returned:
                self._recenter_tick(generation, slot)

        self._recenter_slot = slot
        self._recenter_token = _RECENTER_SCHEDULING
        try:
            token = self._scheduler(SAMPLE_INTERVAL_MS, scheduled_callback)
        except Exception:
            if self._recenter_slot is slot:
                self._recenter_slot = None
                self._recenter_token = None
                if self._state == "recentering" and not self._terminal:
                    self._disable()
            return False
        scheduler_returned = True
        if fired:
            if self._recenter_slot is slot:
                self._recenter_slot = None
                self._recenter_token = None
                if self._state == "recentering" and not self._terminal:
                    self._disable()
            return False
        if (
            not self._terminal
            and generation == self._recenter_generation
            and self._state == "recentering"
            and self._recenter_slot is slot
        ):
            self._recenter_token = token
            return True
        try:
            self._cancel(token)
        except Exception:
            pass
        return False

    def _recenter_tick(self, generation: int, slot: object) -> None:
        if (
            self._terminal
            or generation != self._recenter_generation
            or self._state != "recentering"
            or self._recenter_slot is not slot
        ):
            return
        self._recenter_token = None
        self._recenter_slot = None
        epoch = self._lifecycle_epoch

        elapsed = max(0.0, self._clock() - self._recenter_started_at)
        if elapsed >= RECENTER_DURATION_SECONDS:
            pose = (0.0, 0.0)
            head_pose = (0.0, 0.0)
        else:
            remaining = 1.0 - elapsed / RECENTER_DURATION_SECONDS
            pose = (
                self._recenter_start_pose[0] * remaining,
                self._recenter_start_pose[1] * remaining,
            )
            head_pose = (
                self._recenter_start_head_pose[0] * remaining,
                self._recenter_start_head_pose[1] * remaining,
            )
        if not self._try_display_pose(
            pose,
            epoch,
            "recentering",
            head_pose,
        ):
            return
        if not self._work_is_current(epoch, "recentering"):
            return
        if pose == (0.0, 0.0) and head_pose == (0.0, 0.0):
            self._finish_recenter(epoch)
        else:
            self._schedule_recenter()

    def _finish_recenter(self, epoch: int) -> None:
        if not self._work_is_current(epoch, "recentering"):
            return
        self._recenter_generation += 1
        self._synchronize_controller_center()
        if not self._work_is_current(epoch, "recentering"):
            return
        self._transition("playing")
        completion_epoch = self._lifecycle_epoch
        on_complete = self._recenter_complete
        self._recenter_complete = None
        if on_complete is not None:
            try:
                on_complete()
            except Exception:
                if self._work_is_current(completion_epoch, "playing"):
                    self._transition("following")
                    following_epoch = self._lifecycle_epoch
                    try:
                        self._controller.resume()
                    except Exception:
                        if self._work_is_current(following_epoch, "following"):
                            self._disable()

    def _disable(self) -> None:
        if self._state == "disabled" or self._terminal:
            return
        self._transition("disabled")
        self._pending_action = None
        self._active_action = None
        self._starting_action = None
        self._early_finish = False
        try:
            self._invalidate_recenter()
        except Exception:
            pass
        self._controller.stop()
        if self._terminal or self._state != "disabled":
            return
        if self._disabled_notified:
            return
        self._disabled_notified = True
        try:
            self._on_disabled()
        except Exception:
            pass

    def _transition(self, state: SessionState) -> None:
        self._lifecycle_epoch += 1
        self._state = state
        self._blink_closure = 0.0
        if state == "following" and self._blink_motion is not None:
            try:
                self._blink_motion.reset(self._clock())
            except Exception:
                self._blink_motion = None

    def _work_is_current(self, epoch: int, state: SessionState) -> bool:
        return (
            not self._terminal
            and self._lifecycle_epoch == epoch
            and self._state == state
        )

    def _invalidate_recenter(self) -> None:
        self._recenter_generation += 1
        self._recenter_complete = None
        token = self._recenter_token
        self._recenter_token = None
        self._recenter_slot = None
        if token is not None and token is not _RECENTER_SCHEDULING:
            self._cancel(token)

    def _schedule_eye_tick(
        self, delay_ms: int, callback: Callable[[], None]
    ) -> object:
        def guarded_callback() -> None:
            try:
                callback()
            except Exception:
                self._disable()

        return self._scheduler(delay_ms, guarded_callback)

    def _eye_geometry(self) -> EyeGeometry:
        rect = self._rect_provider()
        try:
            x = float(rect.x)
            y = float(rect.y)
            width = float(rect.width)
            height = float(rect.height)
        except (AttributeError, OverflowError, TypeError, ValueError) as error:
            raise ValueError("rect provider returned invalid geometry") from error
        if (
            not all(math.isfinite(value) for value in (x, y, width, height))
            or width <= 0.0
            or height <= 0.0
        ):
            raise ValueError("window rect must be finite with positive dimensions")
        return EyeGeometry(
            x + self._midpoint_x * width / self._source_width,
            y + self._midpoint_y * height / self._source_height,
            height,
        )

    def _synchronize_controller_center(self) -> None:
        if self._head_follow:
            self._controller.synchronize_center()
        else:
            self._controller.synchronize_pose(0.0, 0.0)

    @staticmethod
    def _valid_pair(values: object, name: str) -> tuple[float, float]:
        try:
            first, second = values  # type: ignore[misc]
            pair = (float(first), float(second))
        except (OverflowError, TypeError, ValueError) as error:
            raise ValueError(f"{name} must contain two finite values") from error
        if not all(math.isfinite(value) for value in pair):
            raise ValueError(f"{name} must contain two finite values")
        return pair

    @staticmethod
    def _validate_physical_frames(
        physical_frames: Mapping[str, Sequence[object]],
    ) -> dict[str, tuple[object, ...]]:
        if set(physical_frames) != set(ACTIONS):
            raise ValueError(f"physical frames must contain exactly {list(ACTIONS)}")
        validated: dict[str, tuple[object, ...]] = {}
        for action in ACTIONS:
            frames = tuple(physical_frames[action])
            if len(frames) != 6:
                raise ValueError(f"physical action {action!r} must contain six frames")
            validated[action] = frames
        return validated

"""Occasional three-pattern idle head-tilt motion without a scheduler."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal


MIN_IDLE_INTERVAL_SECONDS: Final = 35.0
MAX_IDLE_INTERVAL_SECONDS: Final = 80.0
MIN_HOLD_SECONDS: Final = 0.8
MAX_HOLD_SECONDS: Final = 2.0
MIN_TILT_DEGREES: Final = 30.0
MAX_TILT_DEGREES: Final = 50.0
APPROACH_SECONDS: Final = 0.55
ARC_TRAVEL_SECONDS: Final = 1.15
RETURN_SECONDS: Final = 0.55

TiltMode = Literal["left", "right", "left_arc_right"]
TILT_MODES: Final[tuple[TiltMode, ...]] = (
    "left",
    "right",
    "left_arc_right",
)


def _finite_time(value: object, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be finite") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


@dataclass(frozen=True)
class IdleTiltPose:
    rotation_degrees: float = 0.0
    arc: float = 0.0

    def __post_init__(self) -> None:
        rotation = _finite_time(self.rotation_degrees, "idle tilt rotation")
        arc = _finite_time(self.arc, "idle tilt arc")
        if abs(rotation) > MAX_TILT_DEGREES:
            raise ValueError("idle tilt rotation is outside the supported range")
        if not 0.0 <= arc <= 1.0:
            raise ValueError("idle tilt arc must be within 0..1")
        object.__setattr__(self, "rotation_degrees", rotation)
        object.__setattr__(self, "arc", arc)


class IdleHeadTiltMotion:
    """Sample an infrequent left, right, or left-to-right arc head tilt."""

    def __init__(
        self,
        *,
        uniform: Callable[[float, float], float] | None = None,
        choice: Callable[[tuple[TiltMode, ...]], TiltMode] | None = None,
    ) -> None:
        source = random.SystemRandom()
        self._uniform = uniform or source.uniform
        self._choice = choice or source.choice
        self._next_action_at: float | None = None
        self._started_at: float | None = None
        self._mode: TiltMode | None = None
        self._first_hold = 0.0
        self._second_hold = 0.0
        self._first_rotation = 0.0
        self._second_rotation = 0.0

    @property
    def next_action_at(self) -> float | None:
        return self._next_action_at

    @property
    def active_mode(self) -> TiltMode | None:
        return self._mode

    def trigger(self, mode: TiltMode, now: float) -> None:
        """Start the requested tilt mode now, bypassing the idle wait."""

        current = _finite_time(now, "idle tilt clock")
        if mode not in TILT_MODES:
            raise ValueError("idle tilt mode is invalid")
        self._next_action_at = current
        self._start_action(current, mode)

    def reset(self, now: float) -> None:
        current = _finite_time(now, "idle tilt clock")
        interval = self._random_duration(
            MIN_IDLE_INTERVAL_SECONDS,
            MAX_IDLE_INTERVAL_SECONDS,
            "idle tilt interval",
        )
        self._next_action_at = current + interval
        self._started_at = None
        self._mode = None
        self._first_hold = 0.0
        self._second_hold = 0.0
        self._first_rotation = 0.0
        self._second_rotation = 0.0

    def sample(self, now: float) -> IdleTiltPose:
        current = _finite_time(now, "idle tilt clock")
        if self._next_action_at is None:
            self.reset(current)
            return IdleTiltPose()
        if self._started_at is None:
            if current < self._next_action_at:
                return IdleTiltPose()
            self._start_action(self._next_action_at)

        assert self._started_at is not None
        assert self._mode is not None
        elapsed = max(0.0, current - self._started_at)
        rotation = self._first_rotation

        if elapsed < APPROACH_SECONDS:
            return IdleTiltPose(
                rotation * _smoothstep(elapsed / APPROACH_SECONDS)
            )
        elapsed -= APPROACH_SECONDS
        if elapsed < self._first_hold:
            return IdleTiltPose(rotation)
        elapsed -= self._first_hold

        if self._mode == "left_arc_right":
            if elapsed < ARC_TRAVEL_SECONDS:
                progress = _smoothstep(elapsed / ARC_TRAVEL_SECONDS)
                return IdleTiltPose(
                    self._first_rotation
                    + (self._second_rotation - self._first_rotation) * progress,
                    math.sin(math.pi * progress),
                )
            elapsed -= ARC_TRAVEL_SECONDS
            if elapsed < self._second_hold:
                return IdleTiltPose(self._second_rotation)
            elapsed -= self._second_hold
            rotation = self._second_rotation

        if elapsed < RETURN_SECONDS:
            return IdleTiltPose(
                rotation
                * (1.0 - _smoothstep(elapsed / RETURN_SECONDS))
            )

        self.reset(current)
        return IdleTiltPose()

    def _start_action(
        self,
        started_at: float,
        mode: TiltMode | None = None,
    ) -> None:
        if mode is None:
            try:
                mode = self._choice(TILT_MODES)
            except Exception as error:
                raise ValueError("idle tilt mode source failed") from error
        if mode not in TILT_MODES:
            raise ValueError("idle tilt mode source returned an invalid mode")
        self._mode = mode
        self._started_at = started_at
        self._first_rotation = self._random_rotation(
            -1.0 if mode != "right" else 1.0
        )
        self._second_rotation = (
            self._random_rotation(1.0) if mode == "left_arc_right" else 0.0
        )
        self._first_hold = self._random_duration(
            MIN_HOLD_SECONDS,
            MAX_HOLD_SECONDS,
            "idle tilt hold",
        )
        self._second_hold = (
            self._random_duration(
                MIN_HOLD_SECONDS,
                MAX_HOLD_SECONDS,
                "idle tilt hold",
            )
            if mode == "left_arc_right"
            else 0.0
        )

    def _random_duration(self, low: float, high: float, name: str) -> float:
        try:
            value = float(self._uniform(low, high))
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"{name} source returned an invalid value") from error
        if not math.isfinite(value) or value < low or value > high:
            raise ValueError(f"{name} is outside the supported range")
        return value

    def _random_rotation(self, direction: float) -> float:
        magnitude = self._random_duration(
            MIN_TILT_DEGREES,
            MAX_TILT_DEGREES,
            "idle tilt angle",
        )
        return direction * magnitude

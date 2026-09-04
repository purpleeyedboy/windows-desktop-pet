"""Deterministic, scheduler-free state machine for idle hand licking."""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Literal, Protocol


STABILITY_WINDOW_SECONDS = 2.0
STABILITY_RANGE_LIMIT = 0.02
IDLE_INTERVAL_MIN_SECONDS = 25.0
IDLE_INTERVAL_MAX_SECONDS = 70.0
MAX_TICK_GAP_SECONDS = 1.0
RAISE_SECONDS = 0.12
LICK_SECONDS = 0.10
CONTACT_SECONDS = 0.08
RETRACT_SECONDS = 0.10

LickSide = Literal["left", "right"]
LickPhase = Literal["neutral", "raise", "lick", "contact", "retract"]
LickState = Literal["waiting", "active"]


class LickRandom(Protocol):
    def uniform(self, low: float, high: float) -> float: ...

    def choice(self, values: tuple[LickSide, ...]) -> LickSide: ...

    def randint(self, low: int, high: int) -> int: ...


@dataclass(frozen=True)
class LickPose:
    """Logical lick channels; all-zero is the only neutral pose."""

    side: LickSide | None = None
    phase: LickPhase = "neutral"
    arm: float = 0.0
    tongue: float = 0.0
    eye_x: float = 0.0
    eye_y: float = 0.0
    head_x: float = 0.0
    head_y: float = 0.0


class IdleLickMotion:
    """Qualify true idle time and sample one bounded left/right lick round.

    The class owns no timer and never sleeps.  A GUI's existing periodic tick
    calls :meth:`sample`; injected clocks and random sources therefore remain
    deterministic in tests.
    """

    def __init__(self, *, rng: LickRandom | None = None) -> None:
        self._rng = rng or random.SystemRandom()
        self._samples: deque[tuple[float, float, float]] = deque()
        self._last_now: float | None = None
        self._idle_qualified_at: float | None = None
        self._next_round_at: float | None = None
        self._state: LickState = "waiting"
        self._side: LickSide | None = None
        self._planned_licks = 0
        self._completed_licks = 0
        self._phase: LickPhase = "neutral"
        self._phase_started_at = 0.0
        self._interrupt_requested = False
        self._pose = LickPose()

    @property
    def state(self) -> LickState:
        return self._state

    @property
    def side(self) -> LickSide | None:
        return self._side

    @property
    def planned_licks(self) -> int:
        return self._planned_licks

    @property
    def completed_licks(self) -> int:
        return self._completed_licks

    @property
    def pose(self) -> LickPose:
        return self._pose

    def sample(
        self,
        now: float,
        target: tuple[float, float],
        *,
        eligible: bool = True,
    ) -> LickPose:
        try:
            current = self._finite(now, "idle lick clock")
            target_x = self._finite(target[0], "idle target x")
            target_y = self._finite(target[1], "idle target y")
        except (IndexError, TypeError, ValueError):
            return self._fail_safe()

        if self._clock_discontinuous(current):
            self._restore_neutral(current)
            self._last_now = current
            return self._pose
        self._last_now = current

        if self._state == "active":
            if not eligible:
                self._interrupt_requested = True
            return self._advance_active(current)
        if not eligible:
            self._reset_idle_tracking()
            return self._pose

        self._record_target(current, target_x, target_y)
        if not self._target_is_stable(current):
            self._idle_qualified_at = None
            self._next_round_at = None
            return self._pose
        if self._idle_qualified_at is None:
            self._idle_qualified_at = current
            try:
                self._next_round_at = current + self._interval()
            except Exception:
                return self._fail_safe(current)
        if self._next_round_at is not None and current >= self._next_round_at:
            try:
                self._start_round(current)
            except Exception:
                return self._fail_safe(current)
        return self._pose

    def interrupt(self, now: float) -> LickPose:
        """Request neutral restoration at the next phase-safe boundary."""

        try:
            current = self._finite(now, "idle lick clock")
        except ValueError:
            return self._fail_safe()
        self._reset_idle_tracking()
        if self._state == "active":
            self._interrupt_requested = True
            return self._advance_active(current)
        self._restore_neutral(current)
        return self._pose

    def _clock_discontinuous(self, current: float) -> bool:
        if self._last_now is None:
            return False
        elapsed = current - self._last_now
        return elapsed < 0.0 or elapsed > MAX_TICK_GAP_SECONDS

    def _record_target(self, now: float, x: float, y: float) -> None:
        self._samples.append((now, x, y))
        cutoff = now - STABILITY_WINDOW_SECONDS
        while len(self._samples) > 1 and self._samples[1][0] <= cutoff:
            self._samples.popleft()

    def _target_is_stable(self, now: float) -> bool:
        if not self._samples or now - self._samples[0][0] < STABILITY_WINDOW_SECONDS:
            return False
        xs = [sample[1] for sample in self._samples]
        ys = [sample[2] for sample in self._samples]
        return max(xs) - min(xs) < STABILITY_RANGE_LIMIT and max(ys) - min(ys) < STABILITY_RANGE_LIMIT

    def _start_round(self, now: float) -> None:
        side = self._rng.choice(("left", "right"))
        count = self._rng.randint(3, 20)
        if side not in ("left", "right"):
            raise ValueError("idle lick side source returned an invalid side")
        if not isinstance(count, int) or isinstance(count, bool) or not 3 <= count <= 20:
            raise ValueError("idle lick count source returned an invalid count")
        self._state = "active"
        self._side = side
        self._planned_licks = count
        self._completed_licks = 0
        self._interrupt_requested = False
        self._set_phase("raise", now)

    def _advance_active(self, now: float) -> LickPose:
        # At most 81 transitions exist in a legal round (raise + 4 * 20).
        for _ in range(82):
            duration = {
                "raise": RAISE_SECONDS,
                "lick": LICK_SECONDS,
                "contact": CONTACT_SECONDS,
                "retract": RETRACT_SECONDS,
            }[self._phase]
            boundary = self._phase_started_at + duration
            if now + 1e-9 < boundary:
                return self._pose
            if self._interrupt_requested:
                self._restore_neutral(now)
                return self._pose
            if self._phase == "raise":
                self._set_phase("lick", boundary)
            elif self._phase == "lick":
                self._set_phase("contact", boundary)
            elif self._phase == "contact":
                self._set_phase("retract", boundary)
            else:
                self._completed_licks += 1
                if self._completed_licks >= self._planned_licks:
                    self._restore_neutral(now)
                    return self._pose
                self._set_phase("lick", boundary)
        return self._fail_safe(now)

    def _set_phase(self, phase: LickPhase, started_at: float) -> None:
        assert self._side is not None
        self._phase = phase
        self._phase_started_at = started_at
        arm = 1.0
        tongue = 1.0 if phase in ("lick", "contact") else 0.0
        self._pose = LickPose(self._side, phase, arm, tongue)

    def _restore_neutral(self, now: float | None = None) -> None:
        self._state = "waiting"
        self._side = None
        self._phase = "neutral"
        self._interrupt_requested = False
        self._pose = LickPose()
        self._reset_idle_tracking()
        if now is not None:
            self._last_now = now

    def _reset_idle_tracking(self) -> None:
        self._samples.clear()
        self._idle_qualified_at = None
        self._next_round_at = None

    def _fail_safe(self, now: float | None = None) -> LickPose:
        self._restore_neutral(now)
        return self._pose

    def _interval(self) -> float:
        try:
            value = float(
                self._rng.uniform(
                    IDLE_INTERVAL_MIN_SECONDS,
                    IDLE_INTERVAL_MAX_SECONDS,
                )
            )
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("idle lick interval source failed") from error
        if not math.isfinite(value) or not IDLE_INTERVAL_MIN_SECONDS <= value <= IDLE_INTERVAL_MAX_SECONDS:
            raise ValueError("idle lick interval is outside the supported range")
        return value

    @staticmethod
    def _finite(value: object, name: str) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"{name} must be finite") from error
        if not math.isfinite(result):
            raise ValueError(f"{name} must be finite")
        return result

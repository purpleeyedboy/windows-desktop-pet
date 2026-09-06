"""Feature-only grooming adapter for the shared activity foundation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .idle_lick import LickPose


PREPARE_SECONDS = 1.5
LICK_SECONDS = 0.45
RECOVERY_SECONDS = 1.0
URGENT_RECOVERY_SECONDS = 0.15


class GroomRandom(Protocol):
    def choice(self, values: tuple[str, str]) -> str: ...

    def randint(self, low: int, high: int) -> int: ...


@dataclass(frozen=True)
class GroomRunIdentity:
    animation_id: str
    state_version: int
    cancellation_token: str


@dataclass(frozen=True)
class GroomStartRequest:
    identity: GroomRunIdentity
    started_at: float
    authorized: bool


class GroomFoundationPort(Protocol):
    """Required PR5 surface; implemented once by the shared foundation."""

    def request_groom(
        self,
        on_granted: Callable[[GroomStartRequest], bool],
    ) -> None: ...

    def publish_groom_finished(self, identity: GroomRunIdentity) -> None: ...


class GroomFeatureAdapter:
    """Sample one coordinator-authorized round; owns no clock or event queue."""

    def __init__(
        self,
        *,
        rng: GroomRandom,
        on_complete: Callable[[GroomRunIdentity], None] | None = None,
    ) -> None:
        self._rng = rng
        self._on_complete = on_complete or (lambda _identity: None)
        self._identity: GroomRunIdentity | None = None
        self._started_at = 0.0
        self._side: str | None = None
        self._planned_licks = 0
        self._completed_licks = 0
        self._stop_at_boundary = False
        self._recovery_started_at: float | None = None
        self._recovery_duration = RECOVERY_SECONDS
        self._recovery_start_pose = LickPose()
        self._pose = LickPose()

    @property
    def active(self) -> bool:
        return self._identity is not None

    @property
    def stopping(self) -> bool:
        return self._stop_at_boundary or self._recovery_started_at is not None

    @property
    def side(self) -> str | None:
        return self._side

    @property
    def planned_licks(self) -> int:
        return self._planned_licks

    @property
    def completed_licks(self) -> int:
        return self._completed_licks

    @property
    def lick_duration(self) -> float:
        return LICK_SECONDS

    @property
    def total_duration(self) -> float:
        return PREPARE_SECONDS + self._planned_licks * LICK_SECONDS + RECOVERY_SECONDS

    def start(self, request: GroomStartRequest) -> bool:
        if self.active or not request.authorized:
            return False
        side = self._rng.choice(("left", "right"))
        count = self._rng.randint(3, 20)
        if side not in ("left", "right") or not isinstance(count, int) or not 3 <= count <= 20:
            return False
        self._identity = request.identity
        self._started_at = float(request.started_at)
        self._side = side
        self._planned_licks = count
        self._completed_licks = 0
        self._stop_at_boundary = False
        self._recovery_started_at = None
        self._pose = LickPose(side, "raise", 0.0, 0.0)
        return True

    def sample(self, now: float, identity: GroomRunIdentity) -> LickPose:
        if identity != self._identity or self._side is None:
            return LickPose()
        current = float(now)
        if self._recovery_started_at is not None:
            return self._sample_recovery(current)
        elapsed = max(0.0, current - self._started_at)
        if elapsed < PREPARE_SECONDS:
            progress = elapsed / PREPARE_SECONDS
            self._pose = LickPose(self._side, "raise", progress, 0.0)
            return self._pose

        lick_elapsed = elapsed - PREPARE_SECONDS
        completed = min(self._planned_licks, int(lick_elapsed / LICK_SECONDS))
        self._completed_licks = completed
        if completed >= self._planned_licks or (
            self._stop_at_boundary and lick_elapsed >= LICK_SECONDS
        ):
            boundary = self._started_at + PREPARE_SECONDS + completed * LICK_SECONDS
            self._begin_recovery(boundary, RECOVERY_SECONDS)
            return self._sample_recovery(current)

        cycle = (lick_elapsed % LICK_SECONDS) / LICK_SECONDS
        if cycle < 0.25:
            phase, tongue = "extend", cycle / 0.25
        elif cycle < 0.5:
            phase, tongue = "upstroke", 1.0
        elif cycle < 0.75:
            phase, tongue = "downstroke", 1.0
        else:
            phase, tongue = "retract", 1.0 - (cycle - 0.75) / 0.25
        self._pose = LickPose(self._side, phase, 1.0, tongue)
        return self._pose

    def request_cycle_boundary_stop(self, identity: GroomRunIdentity) -> bool:
        if identity != self._identity:
            return False
        self._stop_at_boundary = True
        return True

    def request_urgent_recovery(
        self, identity: GroomRunIdentity, now: float
    ) -> bool:
        if identity != self._identity:
            return False
        self._begin_recovery(float(now), URGENT_RECOVERY_SECONDS)
        return True

    def _begin_recovery(self, now: float, duration: float) -> None:
        if self._recovery_started_at is not None:
            return
        self._recovery_started_at = now
        self._recovery_duration = duration
        self._recovery_start_pose = self._pose

    def _sample_recovery(self, now: float) -> LickPose:
        assert self._recovery_started_at is not None
        progress = min(
            1.0,
            max(0.0, (now - self._recovery_started_at) / self._recovery_duration),
        )
        if progress >= 1.0 - 1e-9:
            self._finish()
            return LickPose()
        self._pose = LickPose(
            self._side,
            "lower",
            self._recovery_start_pose.arm * (1.0 - progress),
            self._recovery_start_pose.tongue * (1.0 - progress),
        )
        return self._pose

    def _finish(self) -> None:
        identity = self._identity
        self._identity = None
        self._side = None
        self._pose = LickPose()
        self._stop_at_boundary = False
        self._recovery_started_at = None
        if identity is not None:
            self._on_complete(identity)

"""PR #11 adapter contracts for the shared V2.1 interaction foundation.

This module deliberately owns no queue, clock, health state, persistence, or file
validation implementation.  PR5 supplies those services and the total-controller
integration injects them here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .drag_expectation import DROPEFFECT_COPY, DROPEFFECT_NONE


def theoretical_reward_units(size_bytes: int) -> int:
    if size_bytes < 0:
        raise ValueError("size_bytes must be non-negative")
    return size_bytes * 10000 // 1048576


@dataclass(frozen=True)
class DragCandidate:
    path: str
    count: int


@dataclass(frozen=True)
class DragRegion:
    in_sensing_region: bool
    in_head_region: bool


@dataclass(frozen=True)
class FileValidation:
    valid: bool
    size_bytes: int
    theoretical_units: int
    actual_units: int
    overflow_units: int


@dataclass(frozen=True)
class DropPreviewEvent:
    path: str
    count: int
    screen_point: tuple[int, int]
    received_at: float
    session_version: int
    validation: FileValidation


class InputRouter(Protocol):
    def submit(self, callback: Callable[[], None]) -> None: ...


class InteractionRegionService(Protocol):
    def classify_drag_point(self, point: tuple[int, int]) -> DragRegion: ...


class ActivityCoordinator(Protocol):
    def begin_drag_preview(
        self,
        session: int,
        candidate: DragCandidate,
        validation: FileValidation,
    ) -> None: ...
    def end_drag_preview(self, session: int, reason: str) -> None: ...


class HungerService(Protocol):
    def is_full(self) -> bool: ...


class ClockService(Protocol):
    def now(self) -> float: ...


class FileValidationService(Protocol):
    def validate_async(
        self,
        candidate: DragCandidate,
        session: int,
        done: Callable[[FileValidation], None],
    ) -> None: ...


class DragFoundationAdapter:
    """Versioned bridge from OLE callbacks into the shared serialized services."""

    def __init__(
        self,
        *,
        input_router: InputRouter,
        regions: InteractionRegionService,
        activities: ActivityCoordinator,
        hunger: HungerService,
        clock: ClockService,
        validator: FileValidationService,
        consume_drop: Callable[[DropPreviewEvent], None],
    ) -> None:
        self._router = input_router
        self._regions = regions
        self._activities = activities
        self._hunger = hunger
        self._clock = clock
        self._validator = validator
        self._consume_drop = consume_drop
        self._version = 0
        self._candidate: DragCandidate | None = None
        self._validation: FileValidation | None = None
        self._preview_active = False

    def enter(
        self,
        candidate: DragCandidate,
        point: tuple[int, int],
        allowed_effects: int,
    ) -> int:
        self.leave("replaced")
        self._version += 1
        version = self._version
        region = self._regions.classify_drag_point(point)
        if (
            candidate.count != 1
            or not allowed_effects & DROPEFFECT_COPY
            or not region.in_head_region
            or self._hunger.is_full()
        ):
            return DROPEFFECT_NONE
        self._candidate = candidate

        def validated(result: FileValidation) -> None:
            self._router.submit(lambda: self._accept_validation(version, result))

        self._validator.validate_async(candidate, version, validated)
        return DROPEFFECT_NONE

    def _accept_validation(self, version: int, result: FileValidation) -> None:
        if version != self._version or self._candidate is None or not result.valid:
            return
        self._validation = result
        self._preview_active = True
        self._activities.begin_drag_preview(version, self._candidate, result)

    def over(self, point: tuple[int, int], allowed_effects: int) -> int:
        region = self._regions.classify_drag_point(point)
        if (
            self._preview_active
            and self._validation is not None
            and self._validation.valid
            and region.in_head_region
            and not self._hunger.is_full()
            and allowed_effects & DROPEFFECT_COPY
        ):
            return DROPEFFECT_COPY
        return DROPEFFECT_NONE

    def leave(self, reason: str = "leave") -> None:
        version = self._version
        was_active = self._preview_active
        self._version += 1
        self._candidate = None
        self._validation = None
        self._preview_active = False
        if was_active:
            self._router.submit(
                lambda: self._activities.end_drag_preview(version, reason)
            )

    def drop(
        self,
        candidate: DragCandidate,
        point: tuple[int, int],
        allowed_effects: int,
    ) -> int:
        region = self._regions.classify_drag_point(point)
        version = self._version
        validation = self._validation
        accepted = (
            self._preview_active
            and self._candidate == candidate
            and validation is not None
            and validation.valid
            and region.in_head_region
            and not self._hunger.is_full()
            and bool(allowed_effects & DROPEFFECT_COPY)
        )
        if accepted:
            event = DropPreviewEvent(
                path=str(candidate.path),
                count=int(candidate.count),
                screen_point=(int(point[0]), int(point[1])),
                received_at=float(self._clock.now()),
                session_version=version,
                validation=validation,
            )
            self.leave("drop-handoff")
            self._router.submit(lambda: self._consume_drop(event))
        else:
            self.leave("drop-rejected")
        return DROPEFFECT_NONE


__all__ = [
    "DROPEFFECT_COPY",
    "DROPEFFECT_NONE",
    "DragCandidate",
    "DragFoundationAdapter",
    "DragRegion",
    "DropPreviewEvent",
    "FileValidation",
    "theoretical_reward_units",
]

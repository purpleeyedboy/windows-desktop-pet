from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def contains(self, point: Point) -> bool:
        return self.x <= point.x < self.x + self.width and self.y <= point.y < self.y + self.height


@dataclass(frozen=True)
class HitRegion:
    name: str
    rect: Rect

    def contains(self, point: Point) -> bool:
        return self.rect.contains(point)


@dataclass(frozen=True)
class MonitorSnapshot:
    bounds: Rect
    work_area: Rect
    dpi: int


@dataclass(frozen=True)
class DpiScale:
    dpi: int

    def __post_init__(self) -> None:
        if self.dpi <= 0:
            raise ValueError("dpi must be positive")

    def logical_to_physical(self, value: int) -> int:
        scaled = value * self.dpi / 96
        return math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5)


class InputMode(Enum):
    INTERACTIVE = "interactive"
    PASS_THROUGH = "pass_through"


@dataclass(frozen=True)
class InputSnapshot:
    mode: InputMode
    regions: tuple[HitRegion, ...]


class InputState:
    def __init__(self, *, mode: InputMode, regions: tuple[HitRegion, ...]) -> None:
        self.mode = mode
        self.regions = regions

    def snapshot(self) -> InputSnapshot:
        return InputSnapshot(self.mode, self.regions)

    def set_pass_through(self) -> None:
        self.mode = InputMode.PASS_THROUGH

    def restore(self, snapshot: InputSnapshot) -> None:
        self.mode = snapshot.mode
        self.regions = snapshot.regions

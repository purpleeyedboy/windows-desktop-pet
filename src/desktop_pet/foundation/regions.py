"""Physical-screen hit regions derived from the current rendered pose."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from PIL import Image

from .platform import Point, Rect


@dataclass(frozen=True)
class RegionHit:
    part: str
    side: str | None
    coordinate_version: int


class RegionService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._version = 0
        self._regions: dict[str, Rect] = {}
        self._alpha: Image.Image | None = None
        self._window: Rect | None = None

    def update_pose(self, *, window: Rect, source_size: tuple[int, int], anchors: dict[str, tuple[int, int]] | None = None, alpha: Image.Image | None = None) -> int:
        with self._lock:
            self._version += 1
            self._window = window
            self._alpha = alpha.copy() if alpha is not None else None
            self._regions = {
                "cat": window,
                "sensing": Rect(window.x - 16, window.y - 16, window.width + 32, window.height + 32),
                "cat-right": Rect(window.x, window.y, window.width // 2, window.height),
                "cat-left": Rect(window.x + window.width // 2, window.y, window.width - window.width // 2, window.height),
            }
            if source_size[0] > 0 and source_size[1] > 0:
                self._regions["head"] = Rect(window.x, window.y, window.width, window.height // 2)
                for name, (anchor_x, anchor_y) in (anchors or {}).items():
                    x = window.x + round(anchor_x * window.width / source_size[0])
                    y = window.y + round(anchor_y * window.height / source_size[1])
                    self._regions[f"anchor:{name}"] = Rect(x - 1, y - 1, 3, 3)
            return self._version

    def hit_test(self, screen_point: Point, purpose: str) -> RegionHit | None:
        with self._lock:
            if purpose == "expectation":
                if self._window is None:
                    return None
                head = self._regions.get("anchor:head-center") or self._regions.get("anchor:eye-center") or self._regions.get("head")
                if head is None:
                    return None
                cx, cy = head.x + head.width // 2, head.y + head.height // 2
                radius_squared = 2.25 * (self._window.width ** 2 + self._window.height ** 2)
                if (screen_point.x - cx) ** 2 + (screen_point.y - cy) ** 2 <= radius_squared:
                    return RegionHit("expectation", None, self._version)
                return None
            order = ("sensing",) if purpose == "drag" else ("head", "cat-left", "cat-right")
            for name in order:
                rect = self._regions.get(name)
                if rect and rect.contains(screen_point):
                    if name != "sensing" and not self._alpha_hit(screen_point, 0):
                        continue
                    if name == "sensing" and not self._alpha_hit(screen_point, 16):
                        continue
                    side = "left" if name.endswith("-left") else "right" if name.endswith("-right") else None
                    return RegionHit(name, side, self._version)
        return None

    @property
    def coordinate_version(self) -> int:
        return self._version

    def _alpha_hit(self, point: Point, expansion: int) -> bool:
        if self._alpha is None or self._window is None:
            return True
        local_x = point.x - self._window.x
        local_y = point.y - self._window.y
        left, top = max(0, local_x - expansion), max(0, local_y - expansion)
        right = min(self._alpha.width, local_x + expansion + 1)
        bottom = min(self._alpha.height, local_y + expansion + 1)
        if left >= right or top >= bottom:
            return False
        return self._alpha.crop((left, top, right, bottom)).getbbox() is not None

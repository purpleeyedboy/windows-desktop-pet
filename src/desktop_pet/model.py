from dataclasses import dataclass
from typing import Literal, Mapping
ACTIONS = ("jump", "squash", "shake")


def clamp_height(value: int) -> int:
    return max(120, min(520, int(value)))


def format_position(x: int, y: int) -> str:
    return f"{int(x):+d}{int(y):+d}"


class ActionCycle:
    def __init__(self) -> None:
        self._index = 0

    def peek(self) -> str:
        return ACTIONS[self._index]

    def commit(self, expected: str) -> None:
        action = self.peek()
        if expected != action:
            raise ValueError(
                f"cannot commit expected {expected!r}; current action is {action!r}"
            )
        self._index = (self._index + 1) % len(ACTIONS)

    def next(self) -> str:
        action = self.peek()
        self.commit(action)
        return action


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def left(self) -> int:
        return self.x

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def top(self) -> int:
        return self.y

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def contains(self, other: "Rect") -> bool:
        return (
            self.left <= other.left
            and self.top <= other.top
            and self.right >= other.right
            and self.bottom >= other.bottom
        )

    def intersects(self, other: "Rect") -> bool:
        return (
            self.left < other.right
            and self.right > other.left
            and self.top < other.bottom
            and self.bottom > other.top
        )


TailDirection = Literal["down", "up", "left", "right"]


@dataclass(frozen=True)
class BubblePlacement:
    rect: Rect
    tail_direction: TailDirection


def place_oriented_bubble(
    pet: Rect,
    sizes: Mapping[TailDirection, tuple[int, int]],
    screen: Rect,
    gap: int = 12,
) -> BubblePlacement | None:
    """Place a complete directional bubble, preferring above then either side."""
    down_width, down_height = sizes["down"]
    right_width, right_height = sizes["right"]
    left_width, left_height = sizes["left"]
    up_width, up_height = sizes["up"]
    candidates: tuple[BubblePlacement, ...] = (
        BubblePlacement(
            Rect(
                pet.x + (pet.width - down_width) // 2,
                pet.top - gap - down_height,
                down_width,
                down_height,
            ),
            "down",
        ),
        BubblePlacement(
            Rect(
                pet.left - gap - right_width,
                pet.y + (pet.height - right_height) // 3,
                right_width,
                right_height,
            ),
            "right",
        ),
        BubblePlacement(
            Rect(
                pet.right + gap,
                pet.y + (pet.height - left_height) // 3,
                left_width,
                left_height,
            ),
            "left",
        ),
        BubblePlacement(
            Rect(
                pet.x + (pet.width - up_width) // 2,
                pet.bottom + gap,
                up_width,
                up_height,
            ),
            "up",
        ),
    )
    for placement in candidates:
        if screen.contains(placement.rect) and not placement.rect.intersects(pet):
            return placement

    side_options: tuple[tuple[TailDirection, int, int, int], ...] = (
        ("right", right_width, right_height, pet.left - gap - screen.left),
        ("left", left_width, left_height, screen.right - pet.right - gap),
    )
    for direction, width, height, available_width in side_options:
        if screen.height < height or available_width < min(width, 72):
            continue
        fitted_width = min(width, available_width)
        side_y = max(
            screen.top,
            min(screen.bottom - height, pet.y + (pet.height - height) // 3),
        )
        x = pet.left - gap - fitted_width if direction == "right" else pet.right + gap
        rect = Rect(x, side_y, fitted_width, height)
        if screen.contains(rect) and not rect.intersects(pet):
            return BubblePlacement(rect, direction)

    return None


def place_bubble(
    pet: Rect,
    size: tuple[int, int],
    screen: Rect,
    gap: int = 12,
) -> Rect | None:
    placement = place_oriented_bubble(
        pet,
        {direction: size for direction in ("down", "up", "left", "right")},
        screen,
        gap,
    )
    return placement.rect if placement is not None else None

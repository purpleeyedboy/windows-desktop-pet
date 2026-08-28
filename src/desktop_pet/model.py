from dataclasses import dataclass
ACTIONS = ("jump", "squash", "shake")


def clamp_height(value: int) -> int:
    return max(120, min(520, int(value)))


def format_position(x: int, y: int) -> str:
    return f"{int(x):+d}{int(y):+d}"


class ActionCycle:
    def __init__(self) -> None:
        self._index = 0

    def next(self) -> str:
        action = ACTIONS[self._index]
        self._index = (self._index + 1) % len(ACTIONS)
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


def place_bubble(
    pet: Rect,
    size: tuple[int, int],
    screen: Rect,
    gap: int = 12,
) -> Rect | None:
    width, height = size
    candidates = (
        Rect(pet.x + (pet.width - width) // 2, pet.top - gap - height, width, height),
        Rect(pet.left - gap - width, pet.y + (pet.height - height) // 3, width, height),
        Rect(pet.right + gap, pet.y + (pet.height - height) // 3, width, height),
        Rect(pet.x + (pet.width - width) // 2, pet.bottom + gap, width, height),
    )
    for candidate in candidates:
        if screen.contains(candidate) and not candidate.intersects(pet):
            return candidate

    minimum_width = min(width, 72)
    side_y = max(
        screen.top,
        min(screen.bottom - height, pet.y + (pet.height - height) // 3),
    )
    if screen.height >= height:
        left_space = pet.left - gap - screen.left
        if left_space >= minimum_width:
            fitted_width = min(width, left_space)
            candidate = Rect(
                pet.left - gap - fitted_width,
                side_y,
                fitted_width,
                height,
            )
            if screen.contains(candidate):
                return candidate

        right_space = screen.right - pet.right - gap
        if right_space >= minimum_width:
            fitted_width = min(width, right_space)
            candidate = Rect(pet.right + gap, side_y, fitted_width, height)
            if screen.contains(candidate):
                return candidate

    return None

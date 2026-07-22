from PIL import Image


class FakeRenderer:
    def __init__(self, hwnd: int) -> None:
        self.hwnd = hwnd
        self.calls: list[tuple[Image.Image, int, int]] = []
        self.topmost = True

    def render(self, image: Image.Image, x: int, y: int) -> None:
        self.calls.append((image.copy(), x, y))

    def set_topmost(self, enabled: bool) -> None:
        self.topmost = bool(enabled)

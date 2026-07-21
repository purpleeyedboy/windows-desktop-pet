from collections.abc import Callable

from desktop_pet.animation import AnimationController


class FakeScheduler:
    def __init__(self) -> None:
        self.callbacks: list[Callable[[], None]] = []

    def __call__(self, delay_ms: int, callback: Callable[[], None]) -> str:
        assert delay_ms > 0
        self.callbacks.append(callback)
        return f"after-{len(self.callbacks)}"

    def run_all(self) -> None:
        while self.callbacks:
            self.callbacks.pop(0)()


def test_controller_rejects_overlap_and_finishes():
    scheduler = FakeScheduler()
    frames: list[tuple[str, int]] = []
    finished: list[str] = []
    controller = AnimationController(
        {"jump": 3},
        scheduler,
        lambda action, index: frames.append((action, index)),
        finished.append,
        interval_ms=1,
    )
    assert controller.play("jump") is True
    assert controller.play("jump") is False
    scheduler.run_all()
    assert frames == [("jump", 0), ("jump", 1), ("jump", 2)]
    assert finished == ["jump"]
    assert controller.busy is False


def test_controller_rejects_unknown_action():
    scheduler = FakeScheduler()
    controller = AnimationController({"jump": 3}, scheduler, lambda *_: None, lambda _: None)
    assert controller.play("shake") is False

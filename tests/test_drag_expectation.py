from PIL import Image, ImageChops
import pytest

from desktop_pet.drag_expectation import (
    DROPEFFECT_COPY,
    DROPEFFECT_NONE,
    DragExpectationController,
    DragVisualConfig,
    decorate_drag_expectation,
)


class Scheduler:
    def __init__(self):
        self.callbacks = {}
        self.cancelled = []
        self.next_token = 0

    def call(self, delay, callback):
        self.next_token += 1
        token = self.next_token
        def run():
            self.callbacks.pop(token, None)
            callback()
        self.callbacks[token] = (delay, run)
        return token

    def cancel(self, token):
        self.cancelled.append(token)
        self.callbacks.pop(token, None)


def controller():
    scheduler = Scheduler()
    phases = []
    restores = []
    target = DragExpectationController(
        schedule=scheduler.call,
        cancel=scheduler.cancel,
        show_phase=phases.append,
        restore=lambda: restores.append(True),
    )
    return target, scheduler, phases, restores


def test_valid_drag_enters_copy_expectation_and_ticks_once():
    target, scheduler, phases, restores = controller()

    assert target.drag_enter(True, True) == DROPEFFECT_COPY
    assert target.active is True
    assert phases == [0]
    assert len(scheduler.callbacks) == 1
    assert restores == []

    _, callback = next(iter(scheduler.callbacks.values()))
    callback()
    assert phases == [0, 1]
    assert len(scheduler.callbacks) == 1


def test_invalid_or_outside_drag_is_none_and_clears_every_effect():
    target, scheduler, phases, restores = controller()
    target.drag_enter(True, True)

    assert target.drag_over(False, True) == DROPEFFECT_NONE
    assert target.active is False
    assert phases == [0]
    assert restores == [True]
    assert scheduler.cancelled == [1]


def test_leave_drop_cancel_focus_loss_and_exception_cleanup_are_idempotent():
    for stop in ("drag_leave", "drop", "cancel", "focus_lost", "exception"):
        target, scheduler, _, restores = controller()
        target.drag_enter(True, True)
        result = getattr(target, stop)()
        assert result == (DROPEFFECT_NONE if stop == "drop" else None)
        getattr(target, stop)()
        assert target.active is False
        assert restores == [True]
        assert scheduler.cancelled == [1]


def test_repeated_enter_and_fast_cancel_never_leak_scheduled_particles():
    target, scheduler, phases, restores = controller()
    assert target.drag_enter(True, True) == DROPEFFECT_COPY
    assert target.drag_enter(True, True) == DROPEFFECT_COPY
    assert len(scheduler.callbacks) == 1
    target.cancel()
    old_callback = scheduler.callbacks.get(1, (None, lambda: None))[1]
    old_callback()
    target.drag_enter(True, True)

    assert phases == [0, 0]
    assert restores == [True]
    assert len(scheduler.callbacks) == 1


def test_render_or_schedule_exception_rolls_back_without_leaking_state():
    scheduler = Scheduler()
    restores = []
    target = DragExpectationController(
        schedule=scheduler.call,
        cancel=scheduler.cancel,
        show_phase=lambda _phase: (_ for _ in ()).throw(RuntimeError("render")),
        restore=lambda: restores.append(True),
    )

    with pytest.raises(RuntimeError, match="render"):
        target.drag_enter(True, True)

    assert target.active is False
    assert scheduler.callbacks == {}
    assert restores == [True]


def test_tick_render_exception_rolls_back_without_leaking_timer():
    scheduler = Scheduler()
    phases = []
    restores = []
    def show(phase):
        phases.append(phase)
        if phase == 1:
            raise RuntimeError("tick render")
    target = DragExpectationController(
        schedule=scheduler.call,
        cancel=scheduler.cancel,
        show_phase=show,
        restore=lambda: restores.append(True),
    )
    target.drag_enter(True, True)
    _, callback = next(iter(scheduler.callbacks.values()))

    callback()

    assert target.active is False
    assert scheduler.callbacks == {}
    assert phases == [0, 1]
    assert restores == [True]


def test_cancel_failure_still_restores_and_leaves_controller_inactive():
    scheduler = Scheduler()
    restores = []
    target = DragExpectationController(
        schedule=scheduler.call,
        cancel=lambda _token: (_ for _ in ()).throw(RuntimeError("cancel")),
        show_phase=lambda _phase: None,
        restore=lambda: restores.append(True),
    )
    target.drag_enter(True, True)

    with pytest.raises(RuntimeError, match="cancel"):
        target.cancel()

    assert target.active is False
    assert restores == [True]


def test_decorator_preserves_size_and_exact_alpha_while_changing_both_eyes_and_head():
    image = Image.new("RGBA", (80, 80), (80, 90, 100, 0))
    for y in range(10, 70):
        for x in range(10, 70):
            image.putpixel((x, y), (80, 90, 100, 255))
    for box in ((20, 30, 34, 42), (46, 30, 60, 42)):
        for y in range(box[1], box[3]):
            for x in range(box[0], box[2]):
                image.putpixel((x, y), (245, 245, 245, 255))
    config = DragVisualConfig(
        eye_boxes=((20, 30, 34, 42), (46, 30, 60, 42)),
        head_box=(12, 8, 68, 50),
    )

    decorated = decorate_drag_expectation(image, 1, config)

    assert decorated.size == image.size
    assert decorated.getchannel("A").tobytes() == image.getchannel("A").tobytes()
    assert ImageChops.difference(decorated, image).getbbox(alpha_only=False)
    for box in config.eye_boxes:
        assert ImageChops.difference(decorated.crop(box), image.crop(box)).getbbox(alpha_only=False)
    assert decorated.getpixel((40, 12)) != image.getpixel((40, 12))

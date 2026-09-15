"""Exercise actual queue/window/frame/cursor path with only in-memory inputs."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.assets import load_head_neck_compositor, load_paw_compositor, load_paw_motion_config
from desktop_pet.foundation.runtime import Activity, RuntimeContext
from desktop_pet.foundation.sources import FixedTimeSource
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.paw_press import FoundationPawActivityAdapter, PawPressController, PawPose, PawSide, PawState
from desktop_pet.window import PetWindow
from desktop_pet.eye_runtime import SessionResult
from v21_paws_gate import verify_baseline_assets


def main():
    scope = runpy.run_path(str(ROOT / "tests/test_paw_press.py"))
    cursor = scope["FakeCursor"]()
    clock = FixedTimeSource(datetime(2026, 9, 9, tzinfo=timezone.utc), 0)
    runtime = RuntimeContext(clock)
    pending, shown = [], []
    window = PetWindow.__new__(PetWindow)
    window.services = SimpleNamespace(runtime=runtime)
    window._clock = clock.monotonic
    window.root = SimpleNamespace(after=lambda _delay, cb: pending.append(cb) or cb,
                                  after_cancel=lambda cb: pending.remove(cb) if cb in pending else None)
    window._closed = False
    window._rendering_available = True
    window._window_dragging = window._ole_drag_active = False
    window._button_state = SimpleNamespace(any_button_down=lambda: False)
    window.animation = SimpleNamespace(busy=False)
    window._paw_compositor = load_paw_compositor()
    window._paw_activity = FoundationPawActivityAdapter(runtime.coordinator)
    window._paw_controller = PawPressController(cursor, window,
        approval_validator=window._paw_activity.validate_paw,
        on_complete=window._paw_activity.complete_paw,
        on_cancel=window._paw_activity.cancel_paw,
        config=load_paw_motion_config())
    base = load_head_neck_compositor().compose(0, 0, HeadPose(0, 0))
    window._current_image = base
    window._paw_base_image = None
    window._paw_paused_eye = False
    window._legacy_fallback = False
    window._paw_after = None
    window._paw_pose = PawPose(PawState.IDLE)
    window._anchor = lambda: (0, 0)
    window._apply_image = lambda frame, *_: shown.append(frame)
    class PausedEye:
        state = "following"
        deferred = False
        callback = None

        def pause_and_recenter(self, callback):
            self.state = "recentering"
            self.callback = callback
            if not self.deferred:
                self.finish_recenter()
            return SessionResult.ACCEPTED

        def finish_recenter(self):
            callback, self.callback = self.callback, None
            self.state = "playing"
            if callback is not None:
                callback()

        def cancel_for_recovery(self):
            self.callback = None
            self.state = "following"

    window.eye_session = PausedEye()
    runtime.bind("input.paw", lambda event: window._trigger_paw_press_direct(PawSide(event.payload["side"])))

    window.trigger_paw_press(PawSide.LEFT)
    token = runtime.coordinator.current_token
    assert token.activity is Activity.BODY_ACTION
    assert window._paw_activity._coordinator is runtime.coordinator
    assert window.eye_session.state == "playing"
    clock.advance(.12)
    pending.pop(0)()
    assert shown[-1].size == (640, 768)
    assert shown[-1].tobytes() != base.tobytes()
    assert shown[-1].crop((0, 0, 640, 440)).tobytes() == base.crop((0, 0, 640, 440)).tobytes()
    window.trigger_paw_press(PawSide.RIGHT)
    assert runtime.coordinator.current_token is token
    stale_callback = pending[0]
    replacement = runtime.coordinator.request_activity(Activity.FEED_ANIMATION, animation_id="replace")
    assert window._paw_controller.state is PawState.IDLE and shown[-1].tobytes() == base.tobytes()
    assert window.eye_session.state == "following" and not window._paw_paused_eye
    before = len(shown)
    stale_callback()
    assert len(shown) == before and runtime.coordinator.current_token is replacement
    runtime.coordinator.cancel_and_recover(replacement)

    cursor.point = scope["PointerPoint"](-200, 100)
    cursor.moves.clear()
    window.trigger_paw_press(PawSide.RIGHT)
    clock.advance(.20); pending.pop(0)()
    clock.advance(.20); pending.pop(0)()
    # Independent acceptance value: 14 px * 2.5 = 35 px total at 32 px
    # pointer height. Do not derive this from config, which could regress too.
    assert cursor.point == scope["PointerPoint"](-200, 135)
    assert all(point.x == -200 and 100 <= point.y <= 135 for point in cursor.moves)
    clock.advance(.82); pending.pop(0)()
    assert window._paw_controller.state is PawState.IDLE
    assert runtime.snapshot().activity is Activity.IDLE and not pending
    assert shown[-1].tobytes() == base.tobytes()
    assert window.eye_session.state == "following"
    # No eye-follow pulse drives the animation, and recenter time must never
    # replace the pointer release position captured from the user's click.
    window.eye_session.deferred = True
    cursor.point = scope["PointerPoint"](-300, 200)
    cursor.moves.clear()
    window.trigger_paw_press(PawSide.LEFT)
    assert not pending and window.eye_session.state == "recentering"
    clock.advance(.25)
    cursor.point = scope["PointerPoint"](-293, 200)
    window.eye_session.finish_recenter()
    assert pending and window.eye_session.state == "playing"
    clock.advance(.20); pending.pop(0)()
    clock.advance(.20); pending.pop(0)()
    assert not cursor.moves
    assert shown[-1].tobytes() != base.tobytes()
    clock.advance(.82); pending.pop(0)()
    assert window.eye_session.state == "following" and not pending
    window.trigger_paw_press(PawSide.LEFT)
    late_recenter = window.eye_session.callback
    replacement = runtime.coordinator.request_activity(Activity.FEED_ANIMATION, animation_id="interrupt-recenter")
    assert window.eye_session.state == "following" and not pending
    late_recenter()
    assert runtime.coordinator.current_token is replacement and not pending
    runtime.coordinator.cancel_and_recover(replacement)
    runtime.post("health.set", source="verification", health="critical"); runtime.drain()
    window.trigger_paw_press(PawSide.LEFT)
    assert runtime.coordinator.current_token is None and not pending
    verify_baseline_assets(ROOT / "assets/v2.1-baseline.sha256", ROOT)
    for path in ("tests/test_paw_press.py", "tests/test_paw_compositor.py"):
        for name, function in runpy.run_path(str(ROOT / path)).items():
            if name.startswith("test_"):
                function()
    print("PAWS: real queue/window playback, preemption, stale callbacks, cursor boundaries and 158 baseline assets verified; no real pointer operations")


if __name__ == "__main__":
    main()

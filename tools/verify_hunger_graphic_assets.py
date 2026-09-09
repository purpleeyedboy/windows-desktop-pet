"""Check real hunger frame loading, canonical restoration and archive inputs."""
from pathlib import Path
import sys
import ast
import inspect
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_pet.assets import load_head_neck_compositor
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.hunger_graphic_assets import load_hunger_graphic_assets
from desktop_pet.main import main as application_entrypoint
from desktop_pet.eye_runtime import RuntimeEyeSession, SessionResult
from desktop_pet.window import _CachedCenterCompositor
from desktop_pet.model import ActionCycle, Rect
from desktop_pet import window as window_module


def verify_window_dependency_signatures() -> None:
    tree = ast.parse((ROOT / "src/desktop_pet/window.py").read_text("utf-8"))
    factories = {
        name: getattr(window_module, name)
        for name in ("RuntimeEyeSession", "AnimationController", "BubbleWindow", "_CachedCenterCompositor", "HeadPose", "DialogueChooser", "ActionCycle", "Rect", "FoundationRect")
    }
    factories["renderer_factory"] = window_module.LayeredWindowRenderer
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target, bound_self = None, []
        if isinstance(node.func, ast.Name):
            target = factories.get(node.func.id)
        elif (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Attribute)
              and node.func.value.attr == "eye_session"):
            target = getattr(RuntimeEyeSession, node.func.attr)
            bound_self = [object()]
        if target is not None:
            if any(keyword.arg is None for keyword in node.keywords):
                raise RuntimeError("constructor verification needs explicit keyword names")
            inspect.signature(target).bind(
                *bound_self, *[object() for _ in node.args],
                **{keyword.arg: object() for keyword in node.keywords},
            )
            checked += 1
    assert checked >= 15, "shared window constructor dependency coverage regressed"


def verify_real_eye_session_start() -> None:
    compositor = _CachedCenterCompositor(load_head_neck_compositor())
    from desktop_pet.assets import load_frames
    scheduled, displayed = [], []
    def schedule(_delay, callback):
        scheduled.append(callback)
        return callback
    session = RuntimeEyeSession(
        compositor=compositor,
        cursor_provider=SimpleNamespace(position=lambda: None),
        rect_provider=lambda: Rect(0, 0, 234, 280),
        display=displayed.append,
        scheduler=schedule,
        cancel=lambda callback: scheduled.remove(callback) if callback in scheduled else None,
        clock=lambda: 1000.0,
        on_disabled=lambda: None,
        action_cycle=ActionCycle(), physical_frames=load_frames(),
        play_action=lambda _name: True, cancel_action=lambda _name: True,
        choose_phrase=lambda _name: "", present_phrase=lambda _text: None,
        on_action_failed=lambda *_args: None,
        head_follow=True, on_ambient_blink_due=lambda: None,
    )
    assert session.start() is SessionResult.ACCEPTED
    assert displayed and compositor.center_frame is displayed[0]
    assert session.cancel_for_recovery() is SessionResult.ACCEPTED
    session.stop()


def main() -> int:
    verify_window_dependency_signatures()
    verify_real_eye_session_start()
    neutral = load_head_neck_compositor().compose(0.0, 0.0, HeadPose(0.0, 0.0))
    artwork = load_hunger_graphic_assets(neutral)
    assert len(artwork.clips) == 2
    for name, (frames, sequence) in artwork.clips.items():
        assert sum(step.duration_ms for step in sequence.steps) == 1700, name
        assert frames[0].tobytes() == neutral.tobytes(), name
        assert frames[-1].tobytes() == neutral.tobytes(), name
        assert frames[1].tobytes() != neutral.tobytes(), name
    assert len(artwork.critical_frames) == 2
    assert artwork.critical_frames[0].tobytes() != artwork.critical_frames[1].tobytes()
    assert artwork.critical_durations == (240, 240)
    files = list((ROOT / "assets/hunger/v1").rglob("*.png"))
    assert len(files) == 5, "runtime artwork must deduplicate repeated hold poses"
    print("hunger graphic source hashes, live canvas, canonical restore and five-file package checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

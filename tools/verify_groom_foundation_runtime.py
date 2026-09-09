"""Real raster GROOM ownership and isolated shared-state regression gate."""
from pathlib import Path
import sys
from types import SimpleNamespace
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from desktop_pet.groom_frames import GroomFramePlayer


def verify_unapproved_idle() -> None:
    neutral = Image.new('RGBA', (640, 768))
    player = GroomFramePlayer((neutral,) * 12, rng=SimpleNamespace(uniform=lambda *_: 90, randint=lambda *_: 3))
    assert player.sample(0) is None
    assert player.sample(151) is None and not player.active, 'idle sample started grooming without an activity token'


def verify_runtime() -> None:
    from datetime import datetime, timezone
    from desktop_pet.assets import load_groom_frames
    from desktop_pet.eye_runtime import RuntimeEyeSession, SessionResult
    from desktop_pet.eye_follow import CursorPoint
    from desktop_pet.foundation.runtime import Activity, Health, RuntimeContext
    from desktop_pet.foundation.sources import FixedTimeSource
    from desktop_pet.groom_adapter import GroomFeatureAdapter
    from desktop_pet.model import ActionCycle, ACTIONS, Rect
    from desktop_pet.window import PetWindow
    frames = load_groom_frames()
    right_frames = load_groom_frames("right")
    assert frames[1].tobytes() != right_frames[1].tobytes(), "right must be separately authored art"
    assert len(frames) == 12 and all(frame.size == (640, 768) for frame in frames)
    clock = FixedTimeSource(datetime(2026, 9, 9, tzinfo=timezone.utc), 0)
    runtime = RuntimeContext(clock)
    pending = {}
    displayed = []
    def schedule(delay, callback):
        token = object()
        pending[token] = callback
        return token
    player = GroomFramePlayer(frames, rng=SimpleNamespace(uniform=lambda *_: 90, randint=lambda *_: 3, choice=lambda _: "right"), other_sides={"right": right_frames})
    adapter = None
    neutral = frames[0]
    compositor = SimpleNamespace(source_size=(640,768), eye_midpoint=(240,230), compose=lambda *_: neutral)
    session = RuntimeEyeSession(
        compositor=compositor, cursor_provider=SimpleNamespace(position=lambda: CursorPoint(0,0)),
        rect_provider=lambda: Rect(0,0,640,768), display=displayed.append, scheduler=schedule,
        cancel=lambda token: pending.pop(token,None), clock=clock.monotonic, on_disabled=lambda: None,
        action_cycle=ActionCycle(), physical_frames={action:(neutral,)*6 for action in ACTIONS},
        play_action=lambda _: True, cancel_action=lambda _: True, choose_phrase=lambda _: '',
        present_phrase=lambda _: None, on_action_failed=lambda *_: None,
        groom_player=player, on_groom_due=lambda: adapter.request(), on_groom_interrupt=lambda: adapter.cancel(),
    )
    adapter = GroomFeatureAdapter(runtime, session)
    assert session.start() is SessionResult.ACCEPTED
    def tick(delta=.08):
        assert len(pending) == 1, 'groom created or lost the single eye pulse'
        callback = pending.pop(next(iter(pending)))
        clock.advance(delta)
        callback()
        assert len(pending) == 1 and session.state == 'following'

    # Existing auto-idle and the public debug entrypoint both reach this live queue.
    tick()
    protected = runtime.coordinator.request_activity(Activity.FEED_PROCESSING, timeout_seconds=300)
    tick(151)
    assert not player.active and runtime.coordinator.current_token == protected
    adapter.request(3)
    assert not player.active and runtime.coordinator.current_token == protected
    runtime.coordinator.cancel_and_recover(protected)
    runtime.set_health(Health.CRITICAL, source='verification'); runtime.drain()
    tick(); assert not player.active
    runtime.set_health(Health.NORMAL, source='verification'); runtime.drain()
    tick(); assert player.active and runtime.snapshot().activity is Activity.GROOM
    assert player._frames[1].tobytes() == right_frames[1].tobytes(), "auto request did not choose the authored right clip"
    adapter.cancel()

    window = object.__new__(PetWindow)
    window._closed = False; window.groom_adapter = adapter; window.eye_session = session
    window.services = SimpleNamespace(runtime=runtime, build_info=SimpleNamespace(feature_config=SimpleNamespace(debug_menu_enabled=False)))
    window._groom_debug_menu = True
    window._groom_sides = ("left", "right")
    window._window_shown = True
    window._topmost_var = SimpleNamespace(get=lambda:True)
    window.root = SimpleNamespace(after_idle=lambda callback:callback())
    class Menu:
        def __init__(self,*args,**kwargs): self.commands={}; self.cascades={}
        def add_command(self,**kwargs): self.commands[kwargs["label"]]=kwargs["command"]
        def add_cascade(self,**kwargs): self.cascades[kwargs["label"]]=kwargs["menu"]
        def add_separator(self): pass
        def add_checkbutton(self,**kwargs): pass
    import desktop_pet.window as window_module
    original_menu=window_module.tk.Menu
    window_module.tk.Menu=Menu
    try: built_menu=window._create_menu()
    finally: window_module.tk.Menu=original_menu
    debug=built_menu.cascades["调试"].commands
    assert set(debug)=={"白色前爪舔手（3次）","橘色前爪舔手（3次）"}
    ready=window.groom_readiness()
    assert ready["ready"] and ready["same_runtime"] and set(ready["debug_targets"])=={"left","right"}
    assert ready["sides"]["left"]["frame_count"]==ready["sides"]["right"]["frame_count"]==12
    assert ready["sides"]["left"]["rgba_sha256"]!=ready["sides"]["right"]["rgba_sha256"]
    debug["白色前爪舔手（3次）"]()
    assert player._frames[1].tobytes()==frames[1].tobytes()
    assert player.active and runtime.snapshot().activity is Activity.GROOM
    start = len(displayed)
    for _ in range(26): tick()
    assert not player.active and adapter._token is None and runtime.snapshot().activity is Activity.IDLE
    assert session._groom_frame is None and displayed[-1] is neutral
    assert len({frame.tobytes() for frame in displayed[start:]}) >= 7, 'real groom frames did not advance'

    debug["橘色前爪舔手（3次）"]()
    assert player._frames[1].tobytes()==right_frames[1].tobytes()
    assert player.active and runtime.snapshot().activity is Activity.GROOM
    start=len(displayed)
    for _ in range(26): tick()
    assert not player.active and adapter._token is None and session._groom_frame is None
    assert runtime.snapshot().activity is Activity.IDLE and displayed[-1] is neutral
    hashes={frame.tobytes() for frame in displayed[start:]}
    assert right_frames[3].tobytes() in hashes and frames[3].tobytes() not in hashes
    window.request_groom_debug("unknown")
    assert not player.active and adapter._token is None and runtime.snapshot().activity is Activity.IDLE

    for activity in (Activity.FEED_PROCESSING,Activity.FEED_CONFIRM,Activity.TRANSACTION_REVIEW,Activity.DRAG_PREVIEW):
        window.request_groom_debug("right"); tick(.25)
        old = adapter._token
        replacement = runtime.coordinator.request_activity(activity)
        assert replacement is not None and adapter._token is None and not player.active
        assert session._groom_frame is None and displayed[-1] is neutral
        adapter._complete(old); tick()
        assert runtime.coordinator.current_token == replacement and session._groom_frame is None
        runtime.coordinator.cancel_and_recover(replacement)

    # Real right-click handler recovers GROOM but cannot cancel a protected operation.
    window.animation = SimpleNamespace(busy=False)
    window._active_animation_action = None
    window._activity_token = None
    menus = []
    window.menu = SimpleNamespace(tk_popup=lambda *_: menus.append(runtime.snapshot().activity),grab_release=lambda:None)
    runtime.bind('input.context_menu',window._consume_context_menu)
    window.request_groom_debug(); tick()
    window._on_context_menu(SimpleNamespace(x_root=3,y_root=4))
    assert menus == [Activity.CONTEXT_MENU_OPEN] and not player.active and adapter._token is None
    protected=runtime.coordinator.request_activity(Activity.FEED_PROCESSING)
    window._on_context_menu(SimpleNamespace(x_root=3,y_root=4))
    assert len(menus)==1 and runtime.coordinator.current_token==protected
    runtime.coordinator.cancel_and_recover(protected)

    # Real mouse-down path cancels the entire clip before dragging can move it.
    window._window_rect = Rect(20,30,640,768)
    window.request_groom_debug(); tick()
    window._on_left_press(SimpleNamespace(x_root=25,y_root=35))
    assert not player.active and runtime.snapshot().activity is Activity.IDLE and session._groom_frame is None

    # A queued ambient request may synchronously start a higher-priority operation.
    reenter = [True]
    runtime.bind('input.groom', lambda _: runtime.coordinator.request_activity(Activity.TRANSACTION_REVIEW) if reenter[0] else None)
    before=len(displayed); tick(151)
    assert runtime.snapshot().activity is Activity.TRANSACTION_REVIEW and not player.active
    assert all(frame is neutral for frame in displayed[before:])
    runtime.coordinator.cancel_and_recover()
    # Shutdown invalidates an already captured pulse; it cannot repaint or restart.
    reenter[0] = False
    window.request_groom_debug(); tick()
    assert adapter._token is not None
    stale = next(iter(pending.values()))
    window._runtime_timer = None
    window.display_height = 280
    window.animation = SimpleNamespace(stop=lambda:None)
    window.bubble = SimpleNamespace(destroy=lambda:None)
    window.root = SimpleNamespace(destroy=lambda:None)
    window.services.update_state = lambda *_args, **_kwargs: None
    window.services.close = runtime.close
    window.close(); before=len(displayed); stale()
    assert runtime.snapshot().activity is Activity.SHUTTING_DOWN and adapter._token is None
    assert not pending and not player.active and session._groom_frame is None and len(displayed)==before


def main() -> int:
    verify_unapproved_idle()
    assert (ROOT / 'src/desktop_pet/foundation/services.py').is_file(), 'groom entrypoint lacks the actual public shared-state services'
    import hashlib, json
    manifest=json.loads((ROOT/'docs/groom-foundation-source.json').read_text())
    for name, expected in manifest['exact_files'].items():
        assert hashlib.sha256((ROOT/name).read_text(encoding='utf-8').encode('utf-8')).hexdigest()==expected, f'public foundation diverged: {name}'
    entry=(ROOT/'src/desktop_pet/main.py').read_text()
    assert entry.count('services = create_application_services(build_info)')==1
    assert 'services=services' in entry and 'persisted_state=state' in entry
    verify_runtime()
    print('Groom real-frame queue, ownership, single pulse and recovery verification passed')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

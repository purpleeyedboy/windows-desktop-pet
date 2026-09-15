"""Integrated OLE boundary: real queue/activities; fake Windows I/O only."""
import importlib.util
from datetime import date
from types import SimpleNamespace

import pytest
from PIL import Image


def integration():
    assert importlib.util.find_spec('desktop_pet.integrated_window') is not None, 'integrated window is not implemented'
    from desktop_pet.integrated_window import IntegratedDropService
    return IntegratedDropService


@pytest.fixture
def rig(tmp_path):
    DropService = integration()
    from desktop_pet.drag_runtime import DragExpectationRuntime
    from desktop_pet.drag_foundation_adapter import DragCandidate, FileValidation
    from desktop_pet.foundation.config import BuildInfo, FeatureConfig
    from desktop_pet.foundation.services import create_application_services
    from desktop_pet.foundation.platform import Rect
    from desktop_pet.foundation_contract import SharedHungerState
    from desktop_pet.hunger import HungerService
    info = BuildInfo('2.1-integrated', date(2026, 9, 15), 'test', 'test', FeatureConfig(test_build=True))
    services = create_application_services(info, state_root=tmp_path/'state', legacy_root=tmp_path/'legacy')
    services.load_state()
    services.regions.update_pose(window=Rect(0, 0, 100, 100), source_size=(100, 100), alpha=Image.new('L', (100, 100), 255))
    hunger = HungerService(SharedHungerState(services), utc_clock=lambda: int(services.runtime.clock.utc_now().timestamp()))
    hunger.set_units(20_000)
    feed = SimpleNamespace(services=services, accepting_input=True, close=lambda: None)
    drop = DropService(feed)
    runtime = DragExpectationRuntime(services, hunger=hunger, frames=[Image.new('RGBA', (100,100)) for _ in range(5)], show_frame=lambda frame: None, restore=lambda: None, schedule=lambda *args: object(), cancel=lambda timer: None)
    drop.handler = runtime
    candidate = DragCandidate(r'C:\meal.txt', 1)
    runtime._candidate = candidate
    runtime._validation = FileValidation(True, 10, 100, 100, 0)
    runtime._effects = 1
    runtime._point = (20, 20)
    events = []
    services.runtime.bind('feed.drop', lambda event: events.append(event.payload['drop']))
    yield SimpleNamespace(drop=drop, runtime=runtime, candidate=candidate, feed=feed, services=services, hunger=hunger, events=events)
    runtime.close()
    hunger.close()
    services.file_worker.close()


def test_drop_routes_one_immutable_snapshot_to_shared_feed_queue(rig):
    assert rig.drop.over((20,20), 1) == 1
    assert rig.drop.drop(rig.candidate, (20,20), 1) == 1
    assert rig.events == []
    rig.services.runtime.drain()
    assert len(rig.events) == 1
    assert rig.events[0].paths == (r'C:\meal.txt',)
    assert rig.events[0].requested_effect == 'copy'
    assert not rig.runtime.showing
    assert rig.drop.drop(rig.candidate, (20,20), 1) == 0


def test_body_can_preview_but_cannot_offer_or_accept_drop(rig):
    assert rig.drop.over((20,80), 1) == 0
    assert rig.runtime.showing
    assert rig.drop.drop(rig.candidate, (20,80), 1) == 0
    rig.services.runtime.drain()
    assert not rig.events


@pytest.mark.parametrize('reason', ['debug', 'passive', 'unvalidated', 'blocked', 'different', 'move'])
def test_unsafe_or_nonphysical_handoff_is_rejected(rig, reason):
    candidate, effects = rig.candidate, 1
    if reason == 'debug': rig.runtime._debug_until = 999999
    if reason == 'passive': rig.runtime._tail_until = 999999
    if reason == 'unvalidated': rig.runtime._validation = None
    if reason == 'blocked': rig.feed.accepting_input = False
    if reason == 'different': candidate = type(candidate)(r'C:\other.txt', 1)
    if reason == 'move': effects = 2
    assert rig.drop.drop(candidate, (20,20), effects) == 0
    rig.services.runtime.drain()
    assert not rig.events


def test_handoff_rejects_session_replacement_during_health_drain(rig):
    original = rig.runtime.over
    replacement = []
    def replaced(*args):
        validation = rig.runtime._validation
        rig.runtime.leave('replaced')
        rig.runtime._candidate = rig.candidate
        rig.runtime._validation = validation
        original(*args)
        replacement.append(rig.runtime._token)
        return 1
    rig.runtime.over = replaced
    assert rig.drop.drop(rig.candidate, (20,20), 1) == 0
    rig.services.runtime.drain()
    assert not rig.events
    assert rig.runtime._token == replacement[0]


def test_integrated_build_requires_all_feature_flags():
    integration()
    from desktop_pet.integrated_main import validate_integrated_build, INTEGRATED_FEATURES
    from desktop_pet.foundation.config import BuildInfo, FeatureConfig
    info = BuildInfo('2.1-integrated', date(2026,9,15), 'test', 'test', FeatureConfig(enabled_features=INTEGRATED_FEATURES))
    validate_integrated_build(info)
    with pytest.raises(ValueError, match='feature'):
        validate_integrated_build(BuildInfo('old', date(2026,9,15), 'old'))


def test_window_combines_hunger_and_expectation_without_duplicate_pet_base():
    integration()
    from desktop_pet.integrated_window import IntegratedWindow
    from desktop_pet.expectation_window import ExpectationWindow
    from desktop_pet.hunger_window import HungerWindow
    from desktop_pet.window import PetWindow
    assert issubclass(IntegratedWindow, ExpectationWindow)
    assert issubclass(IntegratedWindow, HungerWindow)
    assert IntegratedWindow.__mro__.count(PetWindow) == 1


@pytest.mark.parametrize('outcome', ['accepted', 'cancelled', 'identity-changed', 'untrusted-receipt'])
def test_queued_drop_keeps_real_confirmation_transaction_and_reward_chain(rig, outcome):
    from desktop_pet.feed_core.runtime import FeedRuntime
    from desktop_pet.feed_core.business import FileSnapshot, TrustedRecycleReceipt
    from desktop_pet.foundation.runtime import Activity
    snapshot = FileSnapshot(rig.candidate.path, 7, b'x'*16, 100, 20, 0)
    class Identity:
        calls = 0
        def inspect(self, path):
            self.calls += 1
            if outcome == 'identity-changed' and self.calls > 1:
                return FileSnapshot(path, 7, b'y'*16, 100, 20, 0)
            return snapshot
    class Confirmation:
        callback = None
        def show(self, prepared, current, callback):
            self.callback = callback
        def cancel(self):
            if self.callback:
                self.callback(False)
    class Recycler:
        busy = False
        prepared = None
        def submit(self, prepared, callback):
            self.prepared, self.callback = prepared, callback
    identity, confirmation, recycler = Identity(), Confirmation(), Recycler()
    feed = FeedRuntime(rig.services, SimpleNamespace(), hunger=rig.hunger,
                       identity=identity, confirmation=confirmation, recycler=recycler)
    feed.ready = True
    feed.pet = SimpleNamespace(_closed=False, request_graphic_clip=lambda name, activity:
        rig.services.runtime.coordinator.request_activity(activity, animation_id=name))
    rig.drop.feed = feed
    before = rig.hunger.snapshot().units
    try:
        assert rig.drop.drop(rig.candidate, (20,20), 1) == 1
        rig.services.runtime.drain()
        assert rig.services.runtime.snapshot().activity is Activity.FEED_CONFIRM
        assert recycler.prepared is None
        assert rig.services.state_snapshot().get('pending_transaction') is None
        assert rig.hunger.snapshot().units == before
        confirmation.callback(outcome != 'cancelled')
        if outcome in {'cancelled', 'identity-changed'}:
            assert recycler.prepared is None
            assert rig.hunger.snapshot().units == before
            return
        prepared = recycler.prepared
        assert prepared is not None
        assert rig.services.state_snapshot()['pending_transaction']['phase'] == 'Prepared'
        assert identity.calls >= 2
        if outcome == 'untrusted-receipt':
            recycler.callback(SimpleNamespace(success=True))
            assert rig.hunger.snapshot().units == before
            assert rig.services.state_snapshot()['pending_transaction']['phase'] == 'NeedsReview'
            return
        receipt = TrustedRecycleReceipt(prepared.operation_id, 1, 0, 'proof', 0, False, 7, b'x'*16)
        recycler.callback(receipt)
        after = rig.hunger.snapshot().units
        recycler.callback(receipt)
        assert after > before
        assert rig.hunger.snapshot().units == after
        assert rig.services.state_snapshot()['pending_transaction']['phase'] == 'Completed'
        assert rig.services.runtime.snapshot().activity is Activity.FEED_ANIMATION
    finally:
        feed.close()


def test_real_integrated_window_initializes_all_layers_and_closes_hunger_once(tmp_path, monkeypatch):
    from desktop_pet.ole_drop_target import DropTargetRegistration
    registered = []
    registrar = SimpleNamespace(
        register=lambda hwnd, target: registered.append(hwnd),
        revoke=lambda hwnd: registered.remove(hwnd),
    )
    # This fixture creates a fake HWND. Exercise registration ownership with an
    # injected native boundary; the separate EXE smoke tests a real Windows HWND.
    monkeypatch.setattr('desktop_pet.drag_runtime.DropTargetRegistration',
        lambda hwnd, target: DropTargetRegistration(hwnd, target, registrar))
    from test_window import prepare_headless, HeadlessCompositor
    from desktop_pet.integrated_window import IntegratedWindow, IntegratedDropService
    from desktop_pet.foundation.config import BuildInfo, FeatureConfig
    from desktop_pet.foundation.services import create_application_services
    from desktop_pet.foundation_contract import SharedHungerState
    from desktop_pet.hunger import HungerService
    class Compositor(HeadlessCompositor):
        source_size = (640,768)
        def compose(self, x, y, *pose):
            return super().compose(x,y)
        def map_head_point(self, point):
            return point[0]+11, point[1]+7
    root, renderer, bubbles, reports, frames, compositor, cursor, clock = prepare_headless(monkeypatch, compositor=Compositor())
    renderer.hwnd = root.winfo_id()
    original_bind = root.bind
    root.bind = lambda event, callback, add=None: original_bind(event, callback)
    info = BuildInfo('2.1-integrated', date(2026,9,15), 'test', 'test', FeatureConfig(test_build=True))
    services = create_application_services(info, state_root=tmp_path/'state', legacy_root=tmp_path/'legacy')
    state = services.load_state()
    hunger = HungerService(SharedHungerState(services), lambda: int(services.runtime.clock.utc_now().timestamp()))
    checkpoints = []
    original_close = hunger.close
    def checkpoint():
        checkpoints.append(True)
        original_close()
    hunger.close = checkpoint
    feed = SimpleNamespace(services=services, accepting_input=True, close=lambda: None)
    services.dragdrop.close()
    services.dragdrop = IntegratedDropService(feed)
    neutral = Image.new('RGBA', (640,768), (30,30,30,255))
    pet = IntegratedWindow(root, frames, renderer_factory=lambda hwnd: renderer,
        compositor=compositor, cursor_provider=cursor, clock=clock,
        services=services, persisted_state=state, hunger=hunger, feed_runtime=feed,
        expectation_frames=[neutral]*5, groom_frames=[neutral]*12,
        groom_other_frames={'right':[neutral]*12})
    try:
        assert pet.groom_adapter.runtime is services.runtime
        assert pet.eye_session._groom_player.available_sides == ('left','right')
        assert pet.expectation.hunger is hunger
        assert services.dragdrop.handler is pet.expectation
        assert pet._ear_point_mapper_callback((3,5)) == (14,12)
        assert pet.hunger_runtime is None
    finally:
        pet.close()
    pet.close()
    assert checkpoints == [True]
    assert root.destroyed
    assert registered == []

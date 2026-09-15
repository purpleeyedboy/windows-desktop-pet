"""Cross-feature transitions use the real coordinator, hunger and drop bridge."""
from types import SimpleNamespace as NS

import pytest

from test_integrated_runtime import rig
from desktop_pet.foundation.runtime import Activity, Health
from desktop_pet.feed_core.runtime import FeedRuntime
from desktop_pet.hunger_graphic_runtime import HungerGraphicRuntime


def real_feed(rig):
    feed = FeedRuntime(rig.services, NS(), hunger=rig.hunger,
        confirmation=NS(cancel=lambda: None), identity=NS(), recycler=NS(busy=False))
    feed.ready = True
    rig.drop.feed = feed
    return feed


@pytest.mark.parametrize('activity', [Activity.EAR_ACTION, Activity.BODY_ACTION, Activity.GROOM])
def test_valid_drag_preempts_lower_priority_action_and_recovers_on_leave(rig, activity):
    feed = real_feed(rig)
    coordinator = rig.services.runtime.coordinator
    recovered = []
    old = coordinator.request_activity(activity)
    coordinator.attach_recovery(old, lambda: recovered.append(activity))
    try:
        assert rig.drop.over((20, 20), 1) == 1
        assert recovered == [activity]
        assert coordinator.snapshot().activity is Activity.DRAG_PREVIEW
        rig.runtime.leave('focus-lost')
        assert coordinator.snapshot().activity is Activity.IDLE
        assert not coordinator.complete(old)
    finally:
        feed.close()


@pytest.mark.parametrize('activity', [Activity.EAR_ACTION, Activity.BODY_ACTION, Activity.GROOM])
def test_entering_critical_physically_cancels_prohibited_action(rig, activity):
    coordinator = rig.services.runtime.coordinator
    recovered = []
    token = coordinator.request_activity(activity)
    coordinator.attach_recovery(token, lambda: recovered.append(activity))
    window = NS(root=NS(after=lambda *args: object()),
        _cancel_after=lambda timer: None, show_hunger_feedback=lambda mood: None,
        refresh_hunger_presentation=lambda snapshot: None,
        request_graphic_clip=lambda *args: None)
    graphic = HungerGraphicRuntime(services=rig.services, service=rig.hunger,
        window=window, clock=rig.services.runtime.clock)
    rig.hunger.set_units(900)
    graphic.start()
    try:
        assert recovered == [activity]
        assert coordinator.snapshot().health is Health.CRITICAL
        assert coordinator.snapshot().activity is Activity.IDLE
        assert coordinator.request_activity(activity) is None
    finally:
        graphic.stop()


def test_focus_loss_after_handoff_keeps_confirmation_owner(rig):
    feed = real_feed(rig)
    coordinator = rig.services.runtime.coordinator
    token = coordinator.request_activity(Activity.FEED_CONFIRM)
    cancelled = []
    coordinator.attach_recovery(token, lambda: cancelled.append(True))
    try:
        rig.runtime.leave('focus-lost')
        assert coordinator.current_token == token
        assert cancelled == []
        assert not feed.accepting_input
    finally:
        feed.close()


def test_critical_feed_receipt_updates_health_and_removes_critical_art(rig):
    from desktop_pet.feed_core.business import FileSnapshot, TrustedRecycleReceipt
    from test_hunger_window_integration import bare_window
    rig.hunger.set_units(900)
    coordinator = rig.services.runtime.coordinator
    rig.services.runtime.set_health(Health.CRITICAL, source='test')
    rig.services.runtime.drain()
    presentation_activity = [Activity.IDLE]
    window, applied = bare_window(presentation_activity)
    window.refresh_hunger_presentation(rig.hunger.snapshot())
    assert window._critical_visible
    snapshot = FileSnapshot(rig.candidate.path, 7, b'x'*16, 1024*1024, 20, 0)
    class Confirmation:
        def show(self, prepared, current, callback): self.callback = callback
        def cancel(self): pass
    class Recycler:
        busy = False
        def submit(self, prepared, callback): self.prepared, self.callback = prepared, callback
    confirmation, recycler = Confirmation(), Recycler()
    feed = FeedRuntime(rig.services, NS(), hunger=rig.hunger,
        confirmation=confirmation, identity=NS(inspect=lambda path: snapshot), recycler=recycler)
    feed.ready = True
    def animate(name, activity):
        rig.services.runtime.drain()
        coordinator.request_activity(activity, animation_id=name)
    feed.pet = NS(_closed=False, request_graphic_clip=animate)
    rig.drop.feed = feed
    try:
        assert rig.drop.drop(rig.candidate, (20,20), 1) == 1
        rig.services.runtime.drain()
        confirmation.callback(True)
        receipt = TrustedRecycleReceipt(recycler.prepared.operation_id, 1, 0, 'proof', 0, False, 7, b'x'*16)
        recycler.callback(receipt)
        assert rig.hunger.snapshot().units == 10900
        assert coordinator.snapshot().health is Health.HUNGRY
        assert coordinator.snapshot().activity is Activity.FEED_ANIMATION
        presentation_activity[0] = Activity.FEED_ANIMATION
        window.refresh_hunger_presentation(rig.hunger.snapshot())
        assert not window._critical_visible
        token = coordinator.current_token
        coordinator.complete(token, animation_id='feed')
        presentation_activity[0] = Activity.IDLE
        window.refresh_hunger_presentation(rig.hunger.snapshot())
        assert not window._critical_visible
        assert coordinator.request_activity(Activity.EAR_ACTION) is not None
    finally:
        feed.close()

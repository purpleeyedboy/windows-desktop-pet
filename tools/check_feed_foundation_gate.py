"""Safe packaging gate: real shared services/player/state, injected file results.

Uses only a temporary state folder. It never inspects or recycles user files.
"""
from __future__ import annotations
import ast
from datetime import date
import inspect
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from PIL import ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desktop_pet.animation import AnimationController
from desktop_pet.assets import load_feed_frames, load_head_neck_compositor
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.foundation.config import BuildInfo, FeatureConfig
from desktop_pet.foundation.runtime import Activity
from desktop_pet.foundation.services import create_application_services
from desktop_pet.feed_core.business import FileSnapshot, TrustedRecycleReceipt
from desktop_pet.feed_core.foundation_contract import FeedDropSnapshot, foundation_feed_ready
from desktop_pet.feed_core.runtime import FeedRuntime, SharedFeedState
from desktop_pet.feed_core.recovery import FeedRecovery
from desktop_pet.window import PetWindow
from desktop_pet.eye_runtime import RuntimeEyeSession
from desktop_pet.layered_window import LayeredWindowRenderer

class Confirmation:
    def show(self, prepared, current, callback):
        self.callback = callback
    def cancel(self):
        callback, self.callback = getattr(self, 'callback', None), None
        if callback:
            callback(False)
    def accept(self):
        callback, self.callback = self.callback, None
        callback(True)

class Recycler:
    def submit(self, prepared, callback):
        self.prepared, self.callback = prepared, callback
    def finish(self, *, valid=True):
        p = self.prepared
        self.callback(TrustedRecycleReceipt(p.operation_id, 1, 0, 'test-proof' if valid else '',
            0, False, p.snapshot.volume_serial, p.snapshot.file_id_128))

def make_window(services):
    pet = PetWindow.__new__(PetWindow)
    pet.services = services
    pet.frames = {}
    pet.eye_session = None
    pet._closed = False
    pet._legacy_fallback = False
    pet._rendering_available = True
    pet._active_animation_action = None
    pet._activity_token = None
    pet._presentation_snapshot = None
    pet._neutral_center_frame = load_head_neck_compositor().compose(0, 0, HeadPose(0, 0))
    pet._anchor = lambda: (320, 768)
    pet.menu = SimpleNamespace(add_command=lambda **kwargs: None)
    pet.close = lambda: None
    shown, scheduled = [], []
    pet._apply_image = lambda frame, *args, **kwargs: shown.append(frame)
    def schedule(delay, callback):
        scheduled.append(callback)
        return callback
    pet.animation = AnimationController({}, schedule, pet._show_animation_frame,
        lambda a: None, cancel=lambda callback: scheduled.remove(callback),
        finished_with_id=pet._animation_finished)
    services.runtime.bind('input.graphic-clip', pet._consume_graphic_clip)
    services.animation.register('body', pet._play_registered_graphic, pet._recover_body_channel)
    return pet, shown, scheduled

def main():
    # Validate the real construction boundary before a Tk-free playback check.
    # A newer window with an older eye runtime otherwise builds successfully,
    # then fails before its first GUI frame with an unexpected keyword error.
    window_source = ast.parse((ROOT/'src/desktop_pet/window.py').read_text(encoding='utf-8'))
    eye_call = next(node for node in ast.walk(window_source)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == 'RuntimeEyeSession')
    inspect.signature(RuntimeEyeSession).bind(**{keyword.arg: None for keyword in eye_call.keywords})
    assert callable(RuntimeEyeSession.cancel_blink) and callable(RuntimeEyeSession.cancel_for_recovery)
    assert callable(LayeredWindowRenderer.set_input_region)
    info = BuildInfo('2.1.0', date(2026, 9, 9), 'gate', 'f617765+e361579',
        FeatureConfig(enabled_features=('common-foundation', 'feed'), test_build=True,
                      debug_enabled=True, debug_menu_enabled=True))
    with TemporaryDirectory(prefix='desktop-pet-feed-gate-') as folder:
        services = create_application_services(info, state_root=Path(folder), legacy_root=Path(folder)/'unused')
        services.load_state()
        confirmation, recycler = Confirmation(), Recycler()
        file = FileSnapshot(r'C:\owned-test-fixture.txt', 7, b'x'*16, 1024, 20, 0)
        feature = FeedRuntime(services, None, confirmation=confirmation,
            identity=SimpleNamespace(inspect=lambda p: file), recycler=recycler)
        try:
            pet, shown, scheduled = make_window(services)
            frames = load_feed_frames(ROOT/'assets/generated/work/feed/v1')
            neutral = pet._neutral_center_frame
            allowed_face = (104, 312, 264, 476)
            assert frames[0].tobytes() == neutral.tobytes(), 'closed pose must be exact accepted neutral'
            for frame in frames:
                assert frame.getchannel('A').tobytes() == neutral.getchannel('A').tobytes(), 'cat silhouette changed'
                outside = ImageChops.difference(neutral.convert('RGB'), frame.convert('RGB'))
                outside.paste((0, 0, 0), allowed_face)
                assert outside.getbbox() is None, 'body/head pixels changed outside local face patches'
            feature.attach_window(pet, frames)
            assert foundation_feed_ready(feature)
            assert feature.services is pet.services is services
            assert frames[0].size == pet._neutral_center_frame.size == (640, 768)
            feature.hunger.set_units(10_000)
            drop = FeedDropSnapshot((file.canonical_path,), 200, 300, feature.clock.utc_iso())
            def begin():
                services.runtime.post('feed.drop', source='gate', drop=drop)
                services.runtime.drain()
                assert services.runtime.snapshot().activity is Activity.FEED_CONFIRM
            begin()
            confirmation.cancel()
            assert services.state_snapshot()['pending_transaction'] is None
            begin()
            confirmation.accept()
            assert services.runtime.snapshot().activity is Activity.FEED_PROCESSING
            assert services.state_snapshot()['pending_transaction']['phase'] == 'Prepared'
            assert not shown
            recycler.finish()
            operation = recycler.prepared.operation_id
            assert services.state_snapshot()['pending_transaction']['phase'] == 'Completed'
            assert feature.state.has_feed_reward(operation)
            assert services.runtime.snapshot().activity is Activity.FEED_ANIMATION and pet.animation.busy
            recycler.finish()
            assert services.state_snapshot()['hunger']['AppliedOperationIds'].count(operation) == 1
            while scheduled:
                scheduled.pop(0)()
            assert services.runtime.snapshot().activity is Activity.IDLE and shown[-1] is pet._neutral_center_frame
            before = services.state_snapshot()
            feature.debug_animation()
            assert pet.animation.busy and services.state_snapshot() == before
            while scheduled:
                scheduled.pop(0)()
            assert services.state_snapshot() == before
            # An untrusted Shell outcome cannot award or animate.
            shown.clear()
            begin(); confirmation.accept(); recycler.finish(valid=False)
            assert feature.recovery.feed_blocked and not pet.animation.busy and not shown
            assert services.runtime.snapshot().activity is Activity.IDLE
            rejected = recycler.prepared.operation_id
            assert not feature.state.has_feed_reward(rejected)
            assert not feature.recovery.resolve(rejected, claim_reward=True)
            assert feature.recovery.resolve(rejected, claim_reward=False)
            feature._late_recycle_result(recycler.prepared,
                TrustedRecycleReceipt(rejected, 1, 0, 'late-test-proof', 0, False, 7, b'x'*16))
            assert services.state_snapshot()['pending_transaction']['phase'] == 'Cancelled'
            assert not feature.recovery.feed_blocked
            # Fail the single atomic hunger commit after saving trusted evidence.
            begin(); confirmation.accept()
            original = feature.hunger.store.commit_hunger
            feature.hunger.store.commit_hunger = lambda record: (_ for _ in ()).throw(OSError('injected write failure'))
            recycler.finish()
            failed = recycler.prepared.operation_id
            assert feature.recovery.feed_blocked and not feature.state.has_feed_reward(failed)
            assert services.runtime.snapshot().activity is Activity.IDLE and not pet.animation.busy
            feature.hunger.store.commit_hunger = original
            assert feature.recovery.resolve(failed, claim_reward=True)
            assert feature.state.has_feed_reward(failed)
            assert not feature.recovery.resolve(failed, claim_reward=True)
            assert not pet.animation.busy
            # A stale completion is review-only, even with valid recycle proof.
            begin(); confirmation.accept()
            services.runtime.coordinator.cancel_and_recover()
            recycler.finish()
            assert feature.recovery.feed_blocked and not pet.animation.busy
            assert not feature.state.has_feed_reward(recycler.prepared.operation_id)
            assert feature.recovery.resolve(recycler.prepared.operation_id, claim_reward=False)
            # A damaged journal still opens review with a stable durable ID.
            services.update_state(lambda s: s.__setitem__('pending_transaction', {'phase': 'Prepared'}), durable=True)
            repaired = SharedFeedState(services, feature.hunger)
            review = FeedRecovery(repaired, feature.clock.utc_iso)
            review.recover_startup()
            broken = repaired.incomplete_feed_transactions()[0]
            assert broken.operation_id == services.state_snapshot()['pending_transaction']['operation_id']
            assert not review.resolve(broken.operation_id, claim_reward=True)
            assert review.resolve(broken.operation_id, claim_reward=False)
            print('FEED_SHARED_RUNTIME_GATE_OK: shared queue/state/player, trusted receipt, cancellation, duplicate, write failure, stale result, debug isolation')
        finally:
            feature.close()
            services.close()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

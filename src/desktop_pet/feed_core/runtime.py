"""FEED-owned adapters over one ApplicationServices, queue and hunger owner.

Native file work is never run by checks/debug playback. Production operations
remain behind a final owned confirmation and a durable Prepared record.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from desktop_pet.animation import AnimationSequence, FrameStep
from desktop_pet.foundation.runtime import Activity, ActivityToken
from desktop_pet.foundation_contract import HEALTH, SharedHungerState
from desktop_pet.hunger import HungerService
from .business import FeedBusinessHandler, FileSnapshot, TrustedRecycleReceipt
from .confirmation import TkFeedConfirmation
from .foundation_contract import FoundationFeedInputAdapter
from .recovery import FeedRecovery, RecoveryPhase
from .review import NeedsReviewController, TkNeedsReviewWindow
from .windows_identity import WindowsFileIdentityInspector
from .windows_recycle import _perform

# Three readable chews, then squint/lick. No separate swallow stage.
FEED_SEQUENCE = AnimationSequence(
    steps=tuple(FrameStep(i, ms) for i, ms in (
        (1, 100), (2, 160), (3, 100), (0, 130),
        (1, 90), (2, 150), (3, 90), (0, 130),
        (1, 90), (2, 150), (3, 90), (0, 130), (4, 170), (5, 320))),
    anchor=(320, 768),
)


def _snapshot_data(snapshot):
    value = asdict(snapshot)
    value['file_id_128'] = snapshot.file_id_128.hex()
    return value


def _receipt_data(receipt):
    value = asdict(receipt)
    value['source_file_id_128'] = receipt.source_file_id_128.hex()
    return value


class SharedFeedState:
    """Persist transaction records alongside hunger; never own another store."""
    def __init__(self, services, hunger):
        self.services, self.hunger = services, hunger
        pending = self._pending()
        if pending and pending.get('phase') not in {'Completed', 'Cancelled', 'completed', 'cancelled'}:
            operation_id, units = pending.get('operation_id'), pending.get('reward_units')
            if (not isinstance(operation_id, str) or not operation_id.strip()
                    or type(units) is not int or not 0 < units <= 100_000):
                self._write(dict(operation_id=operation_id if isinstance(operation_id, str)
                    and operation_id.strip() else uuid4().hex,
                    phase='NeedsReview', snapshot={}, receipt=None, reward_units=0,
                    reason='invalid_transaction_record'))

    def new_operation_id(self):
        return uuid4().hex

    def _pending(self):
        return self.services.state_snapshot().get('pending_transaction')

    def _write(self, record):
        self.services.update_state(lambda s: s.__setitem__('pending_transaction', record), durable=True)
        # Journal deliberately omits the path; identity is sufficient for review.
        journal_record = dict(record)
        journal_record['snapshot'] = dict(record.get('snapshot', {}))
        journal_record['snapshot'].pop('canonical_path', None)
        if record['phase'] in {'Completed', 'Cancelled'}:
            journal_record['phase'] = record['phase'].lower()
        self.services.journal.append(journal_record, durable=True)

    def persist_prepared(self, prepared):
        current = self._pending()
        if current and current.get('phase') not in {'Completed', 'Cancelled'}:
            raise RuntimeError('unresolved transaction blocks new feed')
        self._write(dict(operation_id=prepared.operation_id, phase='Prepared',
            snapshot=_snapshot_data(prepared.snapshot),
            reward_units=prepared.quote.actual_units, receipt=None))

    def replace_prepared(self, prepared):
        self.persist_prepared(prepared)

    def set_feed_phase(self, operation_id, phase, *, reason=None, evidence=None):
        record = self._pending()
        if not record or record.get('operation_id') != operation_id:
            raise RuntimeError('transaction identity mismatch')
        record['phase'] = phase.value if isinstance(phase, RecoveryPhase) else str(phase)
        if reason is not None:
            record['reason'] = reason
        if isinstance(evidence, TrustedRecycleReceipt):
            record['receipt'] = _receipt_data(evidence)
        self._write(record)

    def persist_cancelled(self, operation_id):
        self.set_feed_phase(operation_id, 'Cancelled')

    def persist_recycle_confirmed(self, prepared, receipt):
        self.set_feed_phase(prepared.operation_id, 'RecycleConfirmed', evidence=receipt)

    def has_feed_reward(self, operation_id):
        record = self.services.state_snapshot().get('hunger', {})
        return operation_id in record.get('AppliedOperationIds', [])

    def apply_feed_reward_once(self, operation_id, units, utc_anchor):
        if self.has_feed_reward(operation_id):
            return True
        now = int(datetime.fromisoformat(utc_anchor.replace('Z', '+00:00')).timestamp())
        _, applied = self.hunger.apply_reward(operation_id, units, now_utc=now)
        return applied or self.has_feed_reward(operation_id)

    apply_reward_atomically = apply_feed_reward_once

    def persist_reward_applied(self, operation_id):
        self.set_feed_phase(operation_id, 'RewardApplied')

    def persist_completed(self, operation_id):
        self.set_feed_phase(operation_id, 'Completed')

    def persist_needs_review(self, operation_id, reason, evidence=None):
        self.set_feed_phase(operation_id, 'NeedsReview', reason=reason, evidence=evidence)

    def incomplete_feed_transactions(self):
        record = self._pending()
        if not record or record.get('phase') in {'Completed', 'Cancelled', 'completed', 'cancelled'}:
            return ()
        value = dict(record)
        try:
            snapshot = dict(value['snapshot'])
            snapshot.setdefault('canonical_path', '')
            snapshot['file_id_128'] = bytes.fromhex(snapshot['file_id_128'])
            value['snapshot'] = FileSnapshot(**snapshot)
            if value.get('receipt'):
                receipt = dict(value['receipt'])
                receipt['source_file_id_128'] = bytes.fromhex(receipt['source_file_id_128'])
                value['receipt'] = TrustedRecycleReceipt(**receipt)
        except (KeyError, TypeError, ValueError):
            # Corrupt or old journal records can only be dismissed in review.
            value.update(phase='NeedsReview', receipt=None, snapshot=None,
                         reason='invalid_transaction_record')
        return (SimpleNamespace(**value),)

    def clear_feed_transaction(self, operation_id):
        self.set_feed_phase(operation_id, 'Cancelled')


@dataclass
class FeedActivityLease:
    initial_version: int
    token: ActivityToken


class FeedActivityAdapter:
    def __init__(self, services, start_animation, cancel_confirmation):
        self.services = services
        self.coordinator = services.runtime.coordinator
        self.start_animation = start_animation
        self.cancel_confirmation = cancel_confirmation

    def begin_feed_confirm(self):
        token = self.coordinator.request_activity(Activity.FEED_CONFIRM, animation_id='feed', timeout_seconds=31)
        if token is None:
            raise RuntimeError('feed confirmation is not permitted')
        lease = FeedActivityLease(token.version, token)
        self.coordinator.attach_recovery(token, self.cancel_confirmation)
        return token.version, 'feed', lease

    def validate_completion(self, animation_id, version, lease):
        return (isinstance(lease, FeedActivityLease) and version == lease.initial_version
                and animation_id == 'feed' and self.coordinator.current_token == lease.token)

    def transition_feed_processing(self, version, lease):
        if not self.validate_completion('feed', version, lease):
            return False
        # Do not cancel the confirmation while replacing its already-finished token.
        self.coordinator.complete(lease.token, animation_id='feed')
        token = self.coordinator.request_activity(Activity.FEED_PROCESSING, animation_id='feed', timeout_seconds=35)
        if token is None:
            return False
        lease.token = token
        return True

    def transition_feed_animation(self, version, lease):
        if not self.validate_completion('feed', version, lease):
            return False
        # A lower priority cannot preempt processing; explicitly complete first.
        self.coordinator.complete(lease.token, animation_id='feed')
        return bool(self.start_animation())

    def recover(self, version, lease):
        if isinstance(lease, FeedActivityLease) and lease.initial_version == version:
            self.coordinator.cancel_and_recover(lease.token)


class SharedFileRecycler:
    """Reuse the foundation STA worker and queue all results back to its owner."""
    def __init__(self, services, identity, schedule, cancel, late_result, operation=_perform):
        self.services, self.identity, self.operation = services, identity, operation
        self.schedule, self.cancel, self.late_result = schedule, cancel, late_result
        self._callbacks = {}
        services.runtime.bind('file.result', self._result)
        services.runtime.bind('feed.recycle-timeout', self._timeout)

    @property
    def busy(self):
        return bool(self._callbacks)

    def submit(self, prepared, callback):
        if self._callbacks:
            raise RuntimeError('recycle operation already active')
        job = dict(prepared=prepared, callback=callback, timer=None, delivered=False)
        self._callbacks[prepared.operation_id] = job
        def operation():
            # Re-check on the worker immediately before calling Windows Shell.
            if self.identity.inspect(prepared.snapshot.canonical_path) != prepared.snapshot:
                raise RuntimeError('file changed before recycle')
            return self.operation(prepared)
        try:
            self.services.file_worker.submit(prepared.operation_id, operation)
            job['timer'] = self.schedule(30_000, lambda: self.services.runtime.post(
                'feed.recycle-timeout', source='feed-timer', correlation_id=prepared.operation_id))
        except Exception:
            self._callbacks.pop(prepared.operation_id, None)
            raise

    def _result(self, event):
        job = self._callbacks.pop(event.correlation_id, None)
        if job is not None:
            if job['timer'] is not None:
                self.cancel(job['timer'])
            result = event.payload.get('result') if event.payload.get('ok') else RuntimeError(event.payload.get('error_type', 'recycle failed'))
            if job['delivered']:
                self.late_result(job['prepared'], result)
            else:
                job['callback'](result)

    def _timeout(self, event):
        job = self._callbacks.get(event.correlation_id)
        if job and not job['delivered']:
            job['timer'] = None
            job['delivered'] = True
            job['callback'](TimeoutError('recycle outcome is unknown'))

    def close(self):
        for job in self._callbacks.values():
            if job['timer'] is not None:
                self.cancel(job['timer'])
                job['timer'] = None


class SharedHungerView:
    def __init__(self, hunger):
        self.hunger = hunger
    @property
    def value_units(self):
        return self.hunger.snapshot().units


class FeedRuntime:
    def __init__(self, services, owner, *, hunger=None, confirmation=None, identity=None, recycler=None):
        self.services, self.runtime, self.owner = services, services.runtime, owner
        self.hunger = hunger or HungerService(SharedHungerState(services),
            lambda: int(self.runtime.clock.utc_now().timestamp()))
        self._owns_hunger = hunger is None
        self.confirmation = confirmation or TkFeedConfirmation(owner,
            preference_path=services.paths.root / "feed-confirmation-preference.json")
        self.identity = identity or WindowsFileIdentityInspector((services.paths.root, Path(__file__).resolve().parents[3], os.environ.get('WINDIR', r'C:\Windows')))
        self.state = SharedFeedState(services, self.hunger)
        self.clock = SimpleNamespace(utc_iso=lambda: self.runtime.clock.utc_now().isoformat())
        self.recovery = FeedRecovery(self.state, self.clock.utc_iso)
        self.pet = None
        self.closed = False
        self.ready = False
        self.activity = FeedActivityAdapter(services, self._start_animation, self.confirmation.cancel)
        self.recycler = recycler or SharedFileRecycler(services, self.identity,
            owner.after, owner.after_cancel, self._late_recycle_result)
        self.business = FeedBusinessHandler(self.identity, self.confirmation,
            self.recycler, self.state, self.activity, SharedHungerView(self.hunger),
            self.clock, self.recovery)
        self.input = FoundationFeedInputAdapter(self)
        self.review_window = None
        self.runtime.bind('feed.preview', self._preview)
        self.runtime.bind('feed.leave', self._leave)
        self.runtime.bind('feed.drop', self._drop)
        self.runtime.bind('feed.debug-animation', lambda e: self._debug_animation())
        self.recovery.recover_startup()

    def attach_window(self, pet, frames):
        self.pet = pet
        pet.register_graphic_clip('feed', frames, FEED_SEQUENCE)
        config = self.services.build_info.feature_config
        if config.test_build or config.debug_enabled:
            self.services.debug.register('进食动画预览（不操作文件）', self.debug_animation)
        controller = NeedsReviewController(self.recovery, self._open_recycle_bin,
            pet.close, lambda items: self.review_window.present(items))
        self.review_window = TkNeedsReviewWindow(self.owner, controller)
        pet.menu.add_command(label='喂食事务复核', command=self.review_window.show)
        self.ready = True
        self._publish_health()
        if self.recovery.feed_blocked:
            self.review_window.show()

    @property
    def accepting_input(self):
        return (self.ready and not self.closed and not self.recovery.feed_blocked and
                not getattr(self.recycler, 'busy', False) and
                self.business._active is None and self.hunger.snapshot().units < 100_000 and
                self.runtime.snapshot().activity in {Activity.IDLE, Activity.BLINK, Activity.GROOM,
                    Activity.BODY_ACTION, Activity.NORMAL_HUNGER_ANIMATION,
                    Activity.SEVERE_HUNGER_ANIMATION, Activity.DRAG_PREVIEW})

    def _preview(self, event):
        if self.accepting_input and self.runtime.snapshot().activity is not Activity.DRAG_PREVIEW:
            self.runtime.coordinator.request_activity(Activity.DRAG_PREVIEW)

    def _leave(self, event):
        token = self.runtime.coordinator.current_token
        if token and token.activity is Activity.DRAG_PREVIEW:
            self.runtime.coordinator.cancel_and_recover(token)

    def _drop(self, event):
        if not self.accepting_input:
            self._leave(event)
            return
        try:
            if not self.business.handle_drop(event.payload['drop']):
                self._leave(event)
        except (OSError, ValueError, RuntimeError):
            self._leave(event)
            self.services.logger.warning('feed input rejected during final validation')

    def _start_animation(self):
        if self.closed or self.pet is None or getattr(self.pet, '_closed', False):
            return False
        self._publish_health()
        self.pet.request_graphic_clip('feed', Activity.FEED_ANIMATION)
        token = self.runtime.coordinator.current_token
        return bool(token and token.activity is Activity.FEED_ANIMATION and token.animation_id == 'feed')

    def _publish_health(self):
        self.runtime.set_health(HEALTH[self.hunger.snapshot().level], source='feed-hunger')

    def debug_animation(self):
        self.services.build_info.feature_config.require_debug_injection()
        self.runtime.post('feed.debug-animation', source='debug')
        self.runtime.drain()

    def _debug_animation(self):
        if not self.business._active and not self.recovery.feed_blocked:
            self._start_animation()

    def _open_recycle_bin(self, location):
        if os.name == 'nt' and location == 'shell:RecycleBinFolder':
            os.startfile(location)

    def _late_recycle_result(self, prepared, result):
        # Timed-out work cannot grant rewards later behind the user's back.
        if isinstance(result, TrustedRecycleReceipt):
            pending = self.services.state_snapshot().get('pending_transaction')
            if (pending and pending.get('operation_id') == prepared.operation_id
                    and pending.get('phase') == 'NeedsReview'):
                self.state.persist_needs_review(prepared.operation_id, 'late_recycle_receipt', result)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.business.cancel_confirmation()
        close_recycler = getattr(self.recycler, 'close', None)
        if close_recycler:
            close_recycler()
        self._leave(None)
        if self._owns_hunger:
            self.hunger.close()


class FeedDragDropService:
    """The one HWND drop owner; replaces the foundation diagnostic drop target."""
    def __init__(self, feed):
        self.feed, self.target = feed, None

    def register(self, hwnd):
        if os.name == 'nt':
            from .windows_drop import NativeFileDropTarget
            self.target = NativeFileDropTarget(hwnd, self.feed.input)
            self.target.register()

    def close(self):
        if self.target is not None:
            self.target.close()
            self.target = None
        self.feed.close()

    def candidate_snapshot(self):
        return {'registered': self.target is not None, 'candidate_count': int(self.feed.input._preview_active)}

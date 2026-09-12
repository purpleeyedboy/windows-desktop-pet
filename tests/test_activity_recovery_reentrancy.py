from datetime import datetime, timezone

import unittest

from desktop_pet.foundation.runtime import Activity, ActivityCoordinator
from desktop_pet.foundation.sources import FixedTimeSource


def check_recovery_preserves_newer_activity(operation, raises):
    clock = FixedTimeSource(datetime(2026, 9, 12, tzinfo=timezone.utc), 0)
    coordinator = ActivityCoordinator(clock)
    old = coordinator.request_activity(Activity.GROOM, timeout_seconds=1)
    created = []

    def recover():
        created.append(coordinator.request_activity(Activity.SHUTTING_DOWN))
        if raises:
            raise RuntimeError('recovery failed after starting shutdown')

    coordinator.attach_recovery(old, recover)

    def act():
        if operation == 'cancel':
            return coordinator.cancel_and_recover(old)
        if operation == 'timeout':
            clock.advance(2)
            return coordinator.expire_timeout()
        return coordinator.request_activity(Activity.DRAG_PREVIEW)

    if raises:
        with unittest.TestCase().assertRaises(RuntimeError):
            act()
    else:
        result = act()
        if operation == 'preempt':
            assert result is None
    assert coordinator.current_token == created[0]
    assert coordinator.snapshot().activity is Activity.SHUTTING_DOWN
    assert coordinator.snapshot().input_gate == 'shutdown_only'
    assert coordinator.cancel_and_recover(old) is False


class RecoveryReentrancyTests(unittest.TestCase):
    def test_recovery_preserves_newer_activity(self):
        for operation in ('cancel', 'timeout', 'preempt'):
            for raises in (False, True):
                with self.subTest(operation=operation, raises=raises):
                    check_recovery_preserves_newer_activity(operation, raises)

    def test_normal_lifecycle_and_recovery_error(self):
        for operation in ('cancel', 'timeout', 'preempt'):
            for raises in (False, True):
                with self.subTest(operation=operation, raises=raises):
                    clock = FixedTimeSource(datetime(2026, 9, 12, tzinfo=timezone.utc), 0)
                    coordinator = ActivityCoordinator(clock)
                    old = coordinator.request_activity(Activity.GROOM, timeout_seconds=1)
                    calls = []
                    def recover():
                        calls.append(old)
                        if raises:
                            raise RuntimeError('recovery failed')
                    coordinator.attach_recovery(old, recover)
                    def act():
                        if operation == 'cancel':
                            return coordinator.cancel_and_recover(old)
                        if operation == 'timeout':
                            clock.advance(2)
                            return coordinator.expire_timeout()
                        return coordinator.request_activity(Activity.DRAG_PREVIEW)
                    if raises:
                        with self.assertRaises(RuntimeError):
                            act()
                    else:
                        act()
                    self.assertEqual(calls, [old])
                    expected = Activity.DRAG_PREVIEW if operation == 'preempt' and not raises else Activity.IDLE
                    self.assertEqual(coordinator.snapshot().activity, expected)
                    if expected is Activity.DRAG_PREVIEW:
                        self.assertTrue(coordinator.complete(coordinator.current_token))
                    self.assertIsNone(coordinator.current_token)


if __name__ == '__main__':
    unittest.main()

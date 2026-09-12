from datetime import datetime, timezone
import math

import pytest

from desktop_pet.foundation.actions import ActionCoordinator, ActionState, OwnershipConflict
from desktop_pet.foundation.sources import FixedTimeSource


def coordinator():
    return ActionCoordinator(FixedTimeSource(datetime(2026, 9, 4, tzinfo=timezone.utc), 10.0))


def test_body_part_has_one_writer_and_completion_returns_neutral():
    actions = coordinator()
    token = actions.start("blink", {"eyes"}, timeout_seconds=1.0)
    with pytest.raises(OwnershipConflict):
        actions.start("look", {"eyes"}, timeout_seconds=1.0)
    assert actions.complete(token) is ActionState.COMPLETED
    assert actions.owner_of("eyes") is None
    assert actions.is_neutral


def test_cancel_user_preemption_timeout_and_safe_recovery_release_ownership():
    actions = coordinator()
    token = actions.start("idle", {"head"}, timeout_seconds=1.0)
    assert actions.cancel(token) is ActionState.CANCELLED
    old = actions.start("idle", {"head"}, timeout_seconds=1.0)
    new = actions.preempt_for_user("touch", {"head"}, timeout_seconds=1.0)
    assert actions.state_of(old) is ActionState.PREEMPTED
    actions.time_source.advance(1.1)
    assert actions.expire_timeouts() == (new,)
    assert actions.state_of(new) is ActionState.TIMED_OUT
    actions.recover_to_neutral()
    assert actions.is_neutral


def test_invalid_user_preemption_does_not_disturb_current_owner():
    actions = coordinator()
    current = actions.start("idle", {"head"}, timeout_seconds=1.0)
    with pytest.raises(ValueError):
        actions.preempt_for_user("", {"head"}, timeout_seconds=1.0)
    assert actions.owner_of("head") == current
    assert actions.state_of(current) is ActionState.RUNNING


@pytest.mark.parametrize("timeout", [math.nan, math.inf, -math.inf])
def test_non_finite_timeout_cannot_claim_a_body_part(timeout):
    actions = coordinator()
    with pytest.raises(ValueError):
        actions.start("idle", {"head"}, timeout_seconds=timeout)
    assert actions.is_neutral

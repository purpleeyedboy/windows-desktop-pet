from datetime import datetime, timezone

import pytest

from desktop_pet.foundation.animation import AnimationChannels
from desktop_pet.foundation.runtime import Activity, ActivityCoordinator
from desktop_pet.foundation.sources import FixedTimeSource


def coordinator_and_token():
    clock = FixedTimeSource(datetime(2026, 9, 11, tzinfo=timezone.utc), 0.0)
    coordinator = ActivityCoordinator(clock)
    token = coordinator.request_activity(Activity.BODY_ACTION, animation_id="jump")
    assert token is not None
    return coordinator, token


def test_play_exception_releases_logical_activity_ownership():
    coordinator, token = coordinator_and_token()
    channels = AnimationChannels(coordinator)
    channels.register("body", lambda _payload: (_ for _ in ()).throw(RuntimeError("play")), lambda: True)

    with pytest.raises(RuntimeError, match="play"):
        channels.play("body", "jump", token)

    assert coordinator.current_token is None
    assert coordinator.snapshot().activity is Activity.IDLE


@pytest.mark.parametrize("cancel_result", [False, RuntimeError("cancel")])
def test_cancel_failure_releases_channel_and_logical_ownership(cancel_result):
    coordinator, token = coordinator_and_token()
    channels = AnimationChannels(coordinator)

    def cancel():
        if isinstance(cancel_result, Exception):
            raise cancel_result
        return cancel_result

    channels.register("body", lambda _payload: True, cancel)
    assert channels.play("body", "jump", token)

    if isinstance(cancel_result, Exception):
        with pytest.raises(RuntimeError, match="cancel"):
            channels.cancel("body", token)
    else:
        assert channels.cancel("body", token) is False

    assert coordinator.current_token is None
    successor = coordinator.request_activity(Activity.BODY_ACTION, animation_id="shake")
    assert successor is not None
    assert channels.play("body", "shake", successor)


def test_recover_exception_releases_channel_and_logical_ownership():
    coordinator, token = coordinator_and_token()
    channels = AnimationChannels(coordinator)
    channels.register("body", lambda _payload: True, lambda: (_ for _ in ()).throw(RuntimeError("recover")))
    assert channels.play("body", "jump", token)

    with pytest.raises(RuntimeError, match="recover"):
        channels.recover("body", token)

    assert coordinator.current_token is None
    assert coordinator.snapshot().activity is Activity.IDLE


def test_recover_with_stale_token_does_not_clear_successor_activity():
    coordinator, stale = coordinator_and_token()
    channels = AnimationChannels(coordinator)
    channels.register("body", lambda _payload: True, lambda: True)
    assert channels.play("body", "jump", stale)
    successor = coordinator.request_activity(Activity.CONTEXT_MENU_OPEN)
    assert successor is not None

    channels.recover("body", stale)

    assert coordinator.current_token == successor
    assert coordinator.snapshot().activity is Activity.CONTEXT_MENU_OPEN

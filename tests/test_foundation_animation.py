from datetime import datetime, timezone

import pytest

from desktop_pet.foundation.animation import AnimationChannels
from desktop_pet.foundation.runtime import Activity, ActivityCoordinator
from desktop_pet.foundation.sources import FixedTimeSource


def coordinator() -> ActivityCoordinator:
    clock = FixedTimeSource(datetime(2026, 9, 11, tzinfo=timezone.utc), 10.0)
    return ActivityCoordinator(clock)


def test_play_exception_releases_activity_ownership() -> None:
    owner = coordinator()
    channels = AnimationChannels(owner)
    channels.register("ears", lambda _payload: (_ for _ in ()).throw(RuntimeError("play")), lambda: True)
    token = owner.request_activity(Activity.EAR_ACTION, animation_id="ear:left")
    assert token is not None

    with pytest.raises(RuntimeError, match="play"):
        channels.play("ears", "left", token)

    assert owner.current_token is None


@pytest.mark.parametrize("raises", (False, True))
def test_cancel_failure_releases_channel_and_activity_ownership(raises: bool) -> None:
    owner = coordinator()
    channels = AnimationChannels(owner)

    def cancel() -> bool:
        if raises:
            raise RuntimeError("cancel")
        return False

    channels.register("ears", lambda _payload: True, cancel)
    token = owner.request_activity(Activity.EAR_ACTION, animation_id="ear:left")
    assert token is not None and channels.play("ears", "left", token)

    if raises:
        with pytest.raises(RuntimeError, match="cancel"):
            channels.cancel("ears", token)
    else:
        assert channels.cancel("ears", token) is False

    assert owner.current_token is None
    replacement = owner.request_activity(Activity.EAR_ACTION, animation_id="ear:right")
    assert replacement is not None
    assert channels.play("ears", "right", replacement)


def test_recover_exception_releases_channel_and_activity_ownership() -> None:
    owner = coordinator()
    channels = AnimationChannels(owner)
    channels.register("ears", lambda _payload: True, lambda: (_ for _ in ()).throw(RuntimeError("recover")))
    token = owner.request_activity(Activity.EAR_ACTION, animation_id="ear:left")
    assert token is not None and channels.play("ears", "left", token)

    with pytest.raises(RuntimeError, match="recover"):
        channels.recover("ears", token)

    assert owner.current_token is None


def test_stale_token_recover_does_not_clear_new_activity() -> None:
    owner = coordinator()
    channels = AnimationChannels(owner)
    channels.register("ears", lambda _payload: True, lambda: True)
    old = owner.request_activity(Activity.EAR_ACTION, animation_id="ear:left")
    assert old is not None and channels.play("ears", "left", old)
    assert owner.cancel_and_recover(old)
    current = owner.request_activity(Activity.EAR_ACTION, animation_id="ear:right")
    assert current is not None and channels.play("ears", "right", current)

    channels.recover("ears", old)

    assert owner.current_token == current
    assert not channels.play("ears", "left", current)
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

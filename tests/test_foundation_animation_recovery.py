"""Regression coverage for CORE animation ownership recovery."""
from datetime import datetime, timezone

import pytest

from desktop_pet.foundation.animation import AnimationChannels
from desktop_pet.foundation.runtime import Activity, ActivityCoordinator
from desktop_pet.foundation.sources import FixedTimeSource


def coordinator():
    clock = FixedTimeSource(datetime(2026, 9, 11, tzinfo=timezone.utc), 0)
    return ActivityCoordinator(clock)


def test_play_exception_releases_activity_ownership():
    owner = coordinator()
    channels = AnimationChannels(owner)

    def fail(_payload):
        raise RuntimeError("play failed")

    channels.register("body", fail, lambda: True)
    token = owner.request_activity(Activity.BODY_ACTION)

    with pytest.raises(RuntimeError, match="play failed"):
        channels.play("body", object(), token)

    assert owner.current_token is None
    assert owner.snapshot().activity is Activity.IDLE


@pytest.mark.parametrize("result", [False, True])
def test_cancel_always_releases_ownership_even_when_player_declines(result):
    owner = coordinator()
    channels = AnimationChannels(owner)
    channels.register("body", lambda _payload: True, lambda: result)
    token = owner.request_activity(Activity.BODY_ACTION)
    assert channels.play("body", object(), token)

    assert channels.cancel("body", token) is result
    assert owner.current_token is None
    assert owner.snapshot().activity is Activity.IDLE


def test_cancel_exception_releases_ownership_and_propagates():
    owner = coordinator()
    channels = AnimationChannels(owner)

    def fail():
        raise RuntimeError("cancel failed")

    channels.register("body", lambda _payload: True, fail)
    token = owner.request_activity(Activity.BODY_ACTION)
    assert channels.play("body", object(), token)

    with pytest.raises(RuntimeError, match="cancel failed"):
        channels.cancel("body", token)

    assert owner.current_token is None
    assert owner.snapshot().activity is Activity.IDLE


def test_recover_exception_releases_ownership_and_propagates():
    owner = coordinator()
    channels = AnimationChannels(owner)

    def fail():
        raise RuntimeError("recover failed")

    channels.register("body", lambda _payload: True, fail)
    token = owner.request_activity(Activity.BODY_ACTION)
    assert channels.play("body", object(), token)

    with pytest.raises(RuntimeError, match="recover failed"):
        channels.recover("body", token)

    assert owner.current_token is None
    assert owner.snapshot().activity is Activity.IDLE


def test_stale_token_recover_does_not_clear_replacement_activity():
    owner = coordinator()
    channels = AnimationChannels(owner)
    channels.register("body", lambda _payload: True, lambda: True)
    stale = owner.request_activity(Activity.BODY_ACTION)
    assert channels.play("body", object(), stale)
    current = owner.request_activity(Activity.FEED_ANIMATION)
    assert current is not None

    channels.recover("body", stale)

    assert owner.current_token == current
    assert owner.snapshot().activity is Activity.FEED_ANIMATION

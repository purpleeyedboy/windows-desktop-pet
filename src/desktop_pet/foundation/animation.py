"""Shared animation-channel adapter guarded by activity tokens."""
from __future__ import annotations

from typing import Any, Callable

from .runtime import ActivityCoordinator, ActivityToken


class AnimationChannels:
    def __init__(self, coordinator: ActivityCoordinator) -> None:
        self._coordinator = coordinator
        self._channels: dict[str, tuple[Callable[[Any], bool], Callable[[], bool]]] = {}
        self._active: dict[str, ActivityToken] = {}

    def register(self, channel: str, play: Callable[[Any], bool], cancel: Callable[[], bool]) -> None:
        if channel in self._channels:
            raise ValueError(f"animation channel already registered: {channel}")
        self._channels[channel] = (play, cancel)

    def play(self, channel: str, payload: Any, activity_token: ActivityToken) -> bool:
        if self._coordinator.current_token != activity_token or channel in self._active:
            return False
        try:
            accepted = self._channels[channel][0](payload)
        except Exception:
            self._coordinator.cancel_and_recover(activity_token)
            raise
        if accepted:
            self._active[channel] = activity_token
            self._coordinator.attach_recovery(
                activity_token,
                lambda: self._cancel_from_coordinator(channel, activity_token),
            )
        return accepted

    def complete(self, channel: str, activity_token: ActivityToken, animation_id: str) -> bool:
        if self._active.get(channel) != activity_token:
            return False
        accepted = self._coordinator.complete(activity_token, animation_id=animation_id)
        if accepted:
            del self._active[channel]
        return accepted

    def complete_current(self, channel: str, animation_id: str) -> ActivityToken | None:
        token = self._active.get(channel)
        if token is None or not self.complete(channel, token, animation_id):
            return None
        return token

    def cancel(self, channel: str, activity_token: ActivityToken | None) -> bool:
        if activity_token is None or self._active.get(channel) != activity_token:
            return False
        try:
            return self._channels[channel][1]()
        finally:
            self._active.pop(channel, None)
            self._coordinator.cancel_and_recover(activity_token)

    def _cancel_from_coordinator(self, channel: str, token: ActivityToken) -> None:
        if self._active.get(channel) != token:
            return
        try:
            self._channels[channel][1]()
        finally:
            self._active.pop(channel, None)

    def recover(self, channel: str, activity_token: ActivityToken | None) -> None:
        """Best-effort physical cancellation followed by mandatory logical recovery."""
        try:
            if activity_token is not None and self._active.get(channel) == activity_token:
                self._channels[channel][1]()
        finally:
            if activity_token is not None:
                self._active.pop(channel, None)
            self._coordinator.cancel_and_recover(activity_token)

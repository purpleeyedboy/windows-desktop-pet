"""Live raster-groom bridge to the one shared activity queue and coordinator."""
from __future__ import annotations
from .eye_runtime import RuntimeEyeSession, SessionResult
from .foundation.runtime import Activity, ActivityToken, RuntimeContext, RuntimeEvent

GROOM_ANIMATION_ID = 'approved-paw-groom'


class GroomFeatureAdapter:
    """Authorize the existing eye-pulse player; never create a second timer."""
    def __init__(self, runtime: RuntimeContext, session: RuntimeEyeSession) -> None:
        self.runtime = runtime
        self.session = session
        self._token: ActivityToken | None = None
        runtime.bind('input.groom', self._consume)

    def request(self, repetitions: int | None = None, *, side: str | None = None) -> None:
        self.runtime.post('input.groom', source='groom', repetitions=repetitions, side=side)
        self.runtime.drain()

    def _consume(self, event: RuntimeEvent) -> None:
        if self.session.state != 'following':
            return
        token = self.runtime.coordinator.request_activity(Activity.GROOM, animation_id=GROOM_ANIMATION_ID, timeout_seconds=12.0)
        if token is None:
            return
        self._token = token
        self.runtime.coordinator.attach_recovery(token, lambda: self._recover(token))
        try:
            accepted = self.session.start_groom(
                event.payload.get('repetitions'),
                side=event.payload.get('side'),
                is_current=lambda: self._token == token and self.runtime.coordinator.current_token == token,
                on_complete=lambda: self._complete(token),
            )
        except Exception:
            self.runtime.coordinator.cancel_and_recover(token)
            raise
        if accepted is not SessionResult.ACCEPTED:
            self.runtime.coordinator.cancel_and_recover(token)

    def _complete(self, token: ActivityToken) -> None:
        if self._token != token:
            return
        if self.runtime.coordinator.complete(token, animation_id=GROOM_ANIMATION_ID):
            self._token = None

    def _recover(self, token: ActivityToken) -> None:
        if self._token != token:
            return
        self._token = None
        self.session.cancel_groom()

    def cancel(self) -> None:
        if self._token is not None:
            self.runtime.coordinator.cancel_and_recover(self._token)

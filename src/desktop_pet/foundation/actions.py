from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable
from uuid import UUID, uuid4

from .sources import TimeSource


class ActionState(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PREEMPTED = "preempted"
    TIMED_OUT = "timed_out"
    RECOVERED = "recovered"


class OwnershipConflict(RuntimeError):
    pass


@dataclass
class _Action:
    name: str
    parts: frozenset[str]
    deadline: float
    state: ActionState = ActionState.RUNNING


class ActionCoordinator:
    def __init__(self, time_source: TimeSource) -> None:
        self.time_source = time_source
        self._actions: dict[UUID, _Action] = {}
        self._owners: dict[str, UUID] = {}

    @staticmethod
    def _validate_request(name: str, parts: Iterable[str], timeout_seconds: float) -> frozenset[str]:
        claimed = frozenset(parts)
        if not name or not claimed or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("name, body parts, and a positive timeout are required")
        return claimed

    def start(self, name: str, parts: Iterable[str], timeout_seconds: float) -> UUID:
        claimed = self._validate_request(name, parts, timeout_seconds)
        conflicts = sorted(part for part in claimed if part in self._owners)
        if conflicts:
            raise OwnershipConflict(f"body parts already owned: {', '.join(conflicts)}")
        token = uuid4()
        self._actions[token] = _Action(name, claimed, self.time_source.monotonic() + timeout_seconds)
        for part in claimed:
            self._owners[part] = token
        return token

    def _finish(self, token: UUID, state: ActionState) -> ActionState:
        action = self._actions.get(token)
        if action is None or action.state is not ActionState.RUNNING:
            raise ValueError("action is not running")
        action.state = state
        for part in action.parts:
            if self._owners.get(part) == token:
                del self._owners[part]
        return state

    def complete(self, token: UUID) -> ActionState:
        return self._finish(token, ActionState.COMPLETED)

    def cancel(self, token: UUID) -> ActionState:
        return self._finish(token, ActionState.CANCELLED)

    def preempt_for_user(self, name: str, parts: Iterable[str], timeout_seconds: float) -> UUID:
        claimed = self._validate_request(name, parts, timeout_seconds)
        for token in {self._owners[p] for p in claimed if p in self._owners}:
            self._finish(token, ActionState.PREEMPTED)
        return self.start(name, claimed, timeout_seconds)

    def expire_timeouts(self) -> tuple[UUID, ...]:
        now = self.time_source.monotonic()
        expired = tuple(token for token, action in self._actions.items() if action.state is ActionState.RUNNING and now >= action.deadline)
        for token in expired:
            self._finish(token, ActionState.TIMED_OUT)
        return expired

    def recover_to_neutral(self) -> None:
        for token, action in tuple(self._actions.items()):
            if action.state is ActionState.RUNNING:
                self._finish(token, ActionState.RECOVERED)

    def state_of(self, token: UUID) -> ActionState:
        return self._actions[token].state

    def owner_of(self, part: str) -> UUID | None:
        return self._owners.get(part)

    @property
    def is_neutral(self) -> bool:
        return not self._owners

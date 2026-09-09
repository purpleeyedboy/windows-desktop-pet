"""Durable V2.1 JSON state and transaction-journal primitives."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from uuid import uuid4


Validator = Callable[[dict[str, Any]], bool]


class AtomicJsonStore:
    """One primary JSON document with an independently valid atomic backup."""

    def __init__(
        self,
        path: Path,
        *,
        schema: str,
        version: int,
        validator: Validator | None = None,
        backup_path: Path | None = None,
        recovery_dir: Path | None = None,
    ) -> None:
        self.path = Path(path)
        self.backup_path = Path(backup_path) if backup_path else self.path.with_suffix(self.path.suffix + ".bak")
        self.recovery_dir = Path(recovery_dir) if recovery_dir else self.path.parent / "recovery"
        self.schema = schema
        self.version = version
        self.validator = validator
        self._replace = os.replace
        self._lock = RLock()
        self.last_source = "default"

    def save(self, data: dict[str, Any], *, durable: bool = False) -> None:
        del durable  # State commits are always durable before returning.
        with self._lock:
            candidate = deepcopy(data)
            self._validate_data(candidate)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            old = self._read_valid(self.path)
            if self.path.exists() and old is None:
                self._preserve_corrupt(self.path, "primary-before-save")
            elif old is not None:
                self._write_envelope_atomic(self.backup_path, old)
            self._write_envelope_atomic(self.path, candidate)
            self.last_source = "primary"

    def load(self, *, default: dict[str, Any]) -> dict[str, Any]:
        """Recover in strict order: primary, valid backup, then caller fallback."""
        with self._lock:
            primary = self._read_valid(self.path)
            if primary is not None:
                self.last_source = "primary"
                return deepcopy(primary)
            if self.path.exists():
                try:
                    self._preserve_corrupt(self.path, "primary-load")
                except OSError:
                    pass
            backup = self._read_valid(self.backup_path)
            if backup is not None:
                self.last_source = "backup"
                return deepcopy(backup)
            if self.backup_path.exists():
                try:
                    self._preserve_corrupt(self.backup_path, "backup-load", remove=False)
                except OSError:
                    pass
            self.last_source = "default"
            return deepcopy(default)

    def _envelope(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"schema": self.schema, "version": self.version, "data": data}

    def _validate_data(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict) or (self.validator is not None and not self.validator(data)):
            raise ValueError("state data is invalid")

    def _read_valid(self, path: Path) -> dict[str, Any] | None:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if envelope.get("schema") != self.schema or envelope.get("version") != self.version:
                return None
            data = envelope.get("data")
            self._validate_data(data)
            return data
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
            return None

    def _write_envelope_atomic(self, destination: Path, data: dict[str, Any]) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        envelope = self._envelope(data)
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(envelope, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            reread = json.loads(temporary.read_text(encoding="utf-8"))
            if reread != envelope:
                raise OSError("temporary state read-back validation failed")
            self._validate_data(reread["data"])
            self._replace(temporary, destination)
            self._sync_directory(destination.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def _preserve_corrupt(self, path: Path, reason: str, *, remove: bool = True) -> None:
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = self.recovery_dir / f"{path.name}.{reason}.{stamp}.{uuid4().hex}.corrupt"
        content = path.read_bytes()
        temporary = destination.with_name(f".{destination.name}.tmp")
        try:
            with temporary.open("wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            self._replace(temporary, destination)
            self._sync_directory(destination.parent)
            if remove:
                path.unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


_SENSITIVE_KEYS = {"path", "paths", "filename", "source_path", "target_path"}
_TERMINAL_PHASES = {"committed", "rolled_back", "cancelled", "completed"}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items() if key.lower() not in _SENSITIVE_KEYS}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


class TransactionJournal:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def append(self, record: dict[str, Any], *, durable: bool) -> None:
        safe = _sanitize(record)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(safe, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                if durable:
                    os.fsync(stream.fileno())

    def recover_pending(self) -> dict[str, Any] | None:
        """Return the newest non-terminal transaction without exposing file paths."""
        with self._lock:
            try:
                lines = self.path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                return None
            latest: dict[str, dict[str, Any]] = {}
            order: list[str] = []
            for line in lines:
                try:
                    record = _sanitize(json.loads(line))
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(record, dict):
                    continue
                transaction = record.get("pending_transaction", record.get("transaction", record))
                if not isinstance(transaction, dict):
                    continue
                operation_id = transaction.get("operation_id") or record.get("operation_id")
                phase = transaction.get("phase") or record.get("phase")
                if not isinstance(operation_id, str) or not isinstance(phase, str):
                    continue
                latest[operation_id] = dict(transaction, operation_id=operation_id, phase=phase)
                order.append(operation_id)
            for operation_id in reversed(order):
                transaction = latest[operation_id]
                if transaction["phase"] not in _TERMINAL_PHASES:
                    return deepcopy(transaction)
            return None

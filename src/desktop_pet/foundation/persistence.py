from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable
from threading import RLock
from uuid import uuid4


class AtomicJsonStore:
    def __init__(self, path: Path, *, schema: str, version: int, validator: Callable[[dict[str, Any]], bool] | None = None) -> None:
        self.path = Path(path)
        self.schema = schema
        self.version = version
        self.validator = validator
        self._replace = os.replace
        self._lock = RLock()

    def save(self, data: dict[str, Any], *, durable: bool = False) -> None:
        del durable  # Atomic state replacement is always flushed before return.
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
            try:
                envelope = {"schema": self.schema, "version": self.version, "data": data}
                with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                    json.dump(envelope, stream, ensure_ascii=False, sort_keys=True)
                    stream.flush()
                    os.fsync(stream.fileno())
                if json.loads(temporary.read_text(encoding="utf-8")) != envelope:
                    raise OSError("temporary state read-back validation failed")
                backup = self.path.with_suffix(self.path.suffix + ".bak")
                if self.path.is_file():
                    with backup.open("wb") as stream:
                        stream.write(self.path.read_bytes())
                        stream.flush()
                        os.fsync(stream.fileno())
                self._replace(temporary, self.path)
                if os.name != "nt":
                    directory = os.open(self.path.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
            finally:
                temporary.unlink(missing_ok=True)

    def load(self, *, default: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            try:
                envelope = json.loads(self.path.read_text(encoding="utf-8"))
                if envelope.get("schema") != self.schema or envelope.get("version") != self.version or not isinstance(envelope.get("data"), dict):
                    raise ValueError("state envelope is invalid")
                data = envelope["data"]
                if self.validator is not None and not self.validator(data):
                    raise ValueError("state data is invalid")
                return data
            except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, ValueError):
                if self.path.exists():
                    corrupt = self.path.with_name(f"{self.path.name}.corrupt-{uuid4().hex}")
                    try:
                        self.path.replace(corrupt)
                    except OSError:
                        pass
                return default.copy()


class TransactionJournal:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def append(self, record: dict[str, Any], *, durable: bool) -> None:
        safe = {key: value for key, value in record.items() if key not in {"path", "paths", "filename"}}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(safe, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                if durable:
                    os.fsync(stream.fileno())

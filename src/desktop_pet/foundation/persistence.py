from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4


class AtomicJsonStore:
    def __init__(self, path: Path, *, schema: str, version: int) -> None:
        self.path = Path(path)
        self.schema = schema
        self.version = version
        self._replace = os.replace

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump({"schema": self.schema, "version": self.version, "data": data}, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            self._replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, *, default: dict[str, Any]) -> dict[str, Any]:
        try:
            envelope = json.loads(self.path.read_text(encoding="utf-8"))
            if envelope.get("schema") != self.schema or envelope.get("version") != self.version or not isinstance(envelope.get("data"), dict):
                return default.copy()
            return envelope["data"]
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            return default.copy()

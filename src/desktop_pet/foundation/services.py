"""Lifecycle services shared by runtime features."""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import logging
import os
from pathlib import Path
from queue import Queue
from threading import Event as ThreadEvent, Thread
from typing import Callable
from uuid import UUID

from .animation import AnimationChannels
from .config import BuildInfo, FeatureConfig
from .persistence import AtomicJsonStore, TransactionJournal
from .regions import RegionService
from .runtime import RuntimeContext
from .sources import SystemRandomSource, SystemTimeSource


DEFAULT_STATE = {
    "hunger_anchor_utc_seconds": 0,
    "pending_transaction": None,
    "recent_operation_ids": [],
    "window": {},
}


def valid_v21_state(data: dict) -> bool:
    return (
        type(data.get("hunger_anchor_utc_seconds")) is int
        and (data.get("pending_transaction") is None or isinstance(data.get("pending_transaction"), dict))
        and isinstance(data.get("recent_operation_ids"), list)
        and all(isinstance(item, str) for item in data.get("recent_operation_ids", ()))
        and isinstance(data.get("window"), dict)
    )


class DebugService:
    def __init__(self, config: FeatureConfig) -> None:
        self.config = config
        self._commands: dict[str, tuple[Callable[[], None], bool]] = {}

    def register(self, name: str, command: Callable[[], None], *, enabled: bool = True) -> None:
        self.config.require_debug_injection()
        self._commands[name] = (command, enabled)

    def commands(self) -> tuple[tuple[str, Callable[[], None], bool], ...]:
        return tuple((name, command, enabled) for name, (command, enabled) in self._commands.items())


class FileWorkerQueue:
    """Single worker; results return to the runtime queue and never mutate state."""

    def __init__(self, post_event: Callable[..., str]) -> None:
        self._post = post_event
        self._queue: Queue[tuple[str, Callable[[], object]] | None] = Queue()
        self._thread = Thread(target=self._run, name="desktop-pet-file-sta", daemon=True)
        self._closed = False
        self._ready = ThreadEvent()
        self._available = False
        self._thread.start()
        if not self._ready.wait(timeout=5) or not self._available:
            raise RuntimeError("file worker STA failed to initialize")

    def submit(self, operation_id: str, operation: Callable[[], object]) -> None:
        if self._closed:
            raise RuntimeError("file worker is closed")
        if not self._available:
            raise RuntimeError("file worker is unavailable")
        if not operation_id:
            raise ValueError("operation_id is required")
        self._queue.put((operation_id, operation))

    def _run(self) -> None:
        ole32 = ctypes.OleDLL("ole32") if os.name == "nt" else None
        if ole32 is not None:
            result = ole32.OleInitialize(None)
            if result not in (0, 1):
                self._ready.set()
                return
        self._available = True
        self._ready.set()
        try:
            while True:
                item = self._queue.get()
                if item is None:
                    return
                operation_id, operation = item
                try:
                    result = operation()
                except Exception as error:
                    self._post("file.result", source="file-worker", correlation_id=operation_id, ok=False, error_type=type(error).__name__)
                else:
                    self._post("file.result", source="file-worker", correlation_id=operation_id, ok=True, result=result)
        finally:
            if ole32 is not None:
                ole32.OleUninitialize()
            self._available = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put(None)
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError("file worker did not stop")


class OleDragDropService:
    """STA/OLE lifetime and diagnostic event bridge; no file operation is performed."""

    def __init__(self, post_event: Callable[..., str]) -> None:
        self._post = post_event
        self._ole32 = None
        self._registered_hwnd: int | None = None
        self._candidate_count = 0
        self._drop_target = None

    def register(self, hwnd: int) -> None:
        if os.name != "nt":
            return
        self._ole32 = ctypes.OleDLL("ole32")
        result = self._ole32.OleInitialize(None)
        if result not in (0, 1):
            raise OSError(result, "OleInitialize failed")
        self._drop_target = _DropTarget(
            lambda event: self._emit_drag_event(event, hwnd)
        )
        register = self._ole32.RegisterDragDrop
        register.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        register.restype = ctypes.c_long
        result = register(hwnd, ctypes.byref(self._drop_target.instance))
        if result != 0:
            self._ole32.OleUninitialize()
            self._ole32 = None
            self._drop_target = None
            raise OSError(result, "RegisterDragDrop failed")
        self._registered_hwnd = hwnd
        self._post("dragdrop.registered", source="ole", hwnd=hwnd)

    def candidate_snapshot(self) -> dict[str, int | bool]:
        return {"registered": self._registered_hwnd is not None, "candidate_count": self._candidate_count}

    def _emit_drag_event(self, event: str, hwnd: int) -> None:
        if event == "dragdrop.enter":
            self._candidate_count = 1
        elif event in {"dragdrop.leave", "dragdrop.drop-rejected"}:
            self._candidate_count = 0
        self._post(event, source="ole", hwnd=hwnd)

    def close(self) -> None:
        revoke_error: OSError | None = None
        if self._ole32 is not None:
            if self._registered_hwnd is not None:
                revoke = self._ole32.RevokeDragDrop
                revoke.argtypes = [ctypes.c_void_p]
                revoke.restype = ctypes.c_long
                result = revoke(ctypes.c_void_p(self._registered_hwnd))
                if result not in (0, -2147221248):  # S_OK or DRAGDROP_E_NOTREGISTERED
                    revoke_error = OSError(result, "RevokeDragDrop failed")
            self._ole32.OleUninitialize()
        self._ole32 = None
        self._registered_hwnd = None
        self._drop_target = None
        if revoke_error is not None:
            raise revoke_error


_CALLBACK = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
_HRESULT = ctypes.c_long
_QueryInterface = _CALLBACK(_HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
_AddRef = _CALLBACK(ctypes.c_ulong, ctypes.c_void_p)
_Release = _CALLBACK(ctypes.c_ulong, ctypes.c_void_p)
_DragEnter = _CALLBACK(_HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_longlong, ctypes.POINTER(ctypes.c_ulong))
_DragOver = _CALLBACK(_HRESULT, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_longlong, ctypes.POINTER(ctypes.c_ulong))
_DragLeave = _CALLBACK(_HRESULT, ctypes.c_void_p)
_Drop = _CALLBACK(_HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_longlong, ctypes.POINTER(ctypes.c_ulong))
_SUPPORTED_IIDS = {
    UUID("00000000-0000-0000-c000-000000000046").bytes_le,
    UUID("00000122-0000-0000-c000-000000000046").bytes_le,
}


class _DropTargetVTable(ctypes.Structure):
    _fields_ = [("QueryInterface", _QueryInterface), ("AddRef", _AddRef), ("Release", _Release), ("DragEnter", _DragEnter), ("DragOver", _DragOver), ("DragLeave", _DragLeave), ("Drop", _Drop)]


class _DropTargetInstance(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(_DropTargetVTable))]


class _DropTarget:
    """Minimal real IDropTarget: emits diagnostics and never reads or mutates files."""

    def __init__(self, emit: Callable[[str], None]) -> None:
        self._emit = emit
        self._refs = 1
        self._callbacks = (
            _QueryInterface(self._query), _AddRef(self._add_ref), _Release(self._release),
            _DragEnter(self._drag_enter), _DragOver(self._drag_over),
            _DragLeave(self._drag_leave), _Drop(self._drop),
        )
        self.vtable = _DropTargetVTable(*self._callbacks)
        self.instance = _DropTargetInstance(ctypes.pointer(self.vtable))

    def _query(self, this, iid, output):
        if not iid or ctypes.string_at(iid, 16) not in _SUPPORTED_IIDS:
            output[0] = None
            return -2147467262  # E_NOINTERFACE
        output[0] = this
        self._add_ref(this)
        return 0

    def _add_ref(self, _this):
        self._refs += 1
        return self._refs

    def _release(self, _this):
        self._refs = max(0, self._refs - 1)
        return self._refs

    def _drag_enter(self, _this, _data, _keys, _point, effect):
        effect[0] = 0
        self._emit("dragdrop.enter")
        return 0

    def _drag_over(self, _this, _keys, _point, effect):
        effect[0] = 0
        return 0

    def _drag_leave(self, _this):
        self._emit("dragdrop.leave")
        return 0

    def _drop(self, _this, _data, _keys, _point, effect):
        effect[0] = 0
        self._emit("dragdrop.drop-rejected")
        return 0


@dataclass
class ApplicationServices:
    runtime: RuntimeContext
    animation: AnimationChannels
    regions: RegionService
    store: AtomicJsonStore
    journal: TransactionJournal
    dragdrop: OleDragDropService
    file_worker: FileWorkerQueue
    debug: DebugService
    build_info: BuildInfo
    random: SystemRandomSource
    logger: logging.Logger
    log_path: Path

    def close(self, state: dict) -> None:
        errors: list[Exception] = []
        for operation in (
            self.file_worker.close,
            lambda: self.runtime.drain(),
            self.dragdrop.close,
            lambda: self.store.save(state, durable=True),
            self.runtime.close,
        ):
            try:
                operation()
            except Exception as error:
                errors.append(error)
        for handler in tuple(self.logger.handlers):
            try:
                handler.flush()
                handler.close()
            finally:
                self.logger.removeHandler(handler)
        if errors:
            raise RuntimeError("application cleanup failed") from errors[0]


def create_application_services(build_info: BuildInfo, state_root: Path | None = None) -> ApplicationServices:
    clock = SystemTimeSource()
    runtime = RuntimeContext(clock)
    root = state_root or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DesktopPet"
    store = AtomicJsonStore(root / "state.json", schema="desktop-pet-v2.1", version=1, validator=valid_v21_state)
    logger = logging.getLogger("desktop_pet")
    log_path = root / "desktop-pet.log"
    if not logger.handlers:
        root.mkdir(parents=True, exist_ok=True)
        logger.addHandler(logging.FileHandler(log_path, encoding="utf-8"))
    return ApplicationServices(
        runtime=runtime,
        animation=AnimationChannels(runtime.coordinator),
        regions=RegionService(),
        store=store,
        journal=TransactionJournal(root / "transactions.jsonl"),
        dragdrop=OleDragDropService(runtime.post),
        file_worker=FileWorkerQueue(runtime.post),
        debug=DebugService(build_info.feature_config),
        build_info=build_info,
        random=SystemRandomSource(),
        logger=logger,
        log_path=log_path,
    )

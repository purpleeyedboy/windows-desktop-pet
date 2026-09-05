"""Windows IFileOperation adapter; no permanent-delete fallback exists."""
from __future__ import annotations

import ctypes
import os
import threading
import time
from pathlib import Path

from .model import FileIdentity, RecycleReceipt
from .validation import FileValidator

COINIT_APARTMENTTHREADED = 0x2
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400
FOFX_RECYCLEONDELETE = 0x00080000
RECYCLE_FLAGS = FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI | FOFX_RECYCLEONDELETE
DEFAULT_OPERATION_TIMEOUT_SECONDS = 30.0
WAIT_SLICE_SECONDS = 0.05


class _Job:
    def __init__(self, path: Path, transaction_id: str, expected_identity: FileIdentity):
        self.path = path
        self.transaction_id = transaction_id
        self.expected_identity = expected_identity
        self.done = threading.Event()
        self.cancelled = threading.Event()
        self.result = None
        self.error = None


class IFileOperationRecycler:
    """Runs each IFileOperation on its own quarantinable COM STA thread."""

    def __init__(self):
        self._active: set[tuple[threading.Thread, _Job]] = set()
        self._active_lock = threading.Lock()
        self._closed = False
        self._needs_review = False

    @property
    def available(self) -> bool:
        return not self._closed and not self._needs_review

    def block_for_review(self) -> None:
        self._needs_review = True

    def recycle(
        self,
        path: Path,
        transaction_id: str,
        *,
        expected_identity: FileIdentity,
        timeout_seconds: float = DEFAULT_OPERATION_TIMEOUT_SECONDS,
        cancel_event=None,
    ) -> RecycleReceipt:
        if os.name != "nt":
            raise OSError("IFileOperation recycling is Windows-only")
        if self._closed:
            raise RuntimeError("recycler is closed")
        if self._needs_review:
            raise InterruptedError("prior uncertain operation requires NeedsReview")
        if timeout_seconds <= 0:
            raise ValueError("operation timeout must be positive")
        job = _Job(Path(path), transaction_id, expected_identity)
        thread = threading.Thread(
            target=self._run_job, args=(job,), name=f"FeedRecycleSTA-{transaction_id[:8]}", daemon=True
        )
        with self._active_lock:
            self._active.add((thread, job))
        thread.start()
        deadline = time.monotonic() + timeout_seconds
        while not job.done.wait(
            timeout=min(WAIT_SLICE_SECONDS, max(0.0, deadline - time.monotonic()))
        ):
            if cancel_event is not None and cancel_event.is_set():
                job.cancelled.set()
                self._needs_review = True
                raise InterruptedError("recycle operation cancelled; outcome requires NeedsReview")
            if time.monotonic() >= deadline:
                job.cancelled.set()
                self._needs_review = True
                raise TimeoutError("recycle operation timed out; outcome requires NeedsReview")
        with self._active_lock:
            self._active.discard((thread, job))
        if job.error:
            raise job.error
        if not isinstance(job.result, RecycleReceipt):
            raise RuntimeError("IFileOperation returned no verifiable receipt")
        return job.result

    def close(self, *, timeout_seconds: float = 5.0):
        self._closed = True
        with self._active_lock:
            active = tuple(self._active)
        for _thread, job in active:
            job.cancelled.set()
        deadline = time.monotonic() + timeout_seconds
        for thread, _job in active:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        if any(thread.is_alive() for thread, _job in active):
            raise TimeoutError("one or more quarantined COM STA workers did not stop")

    def _run_job(self, job: _Job):
        try:
            ole32 = ctypes.OleDLL("ole32")
            hr = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
            if hr not in (0, 1):
                raise OSError(f"COM STA initialization failed: 0x{hr & 0xffffffff:08X}")
            try:
                if job.cancelled.is_set():
                    raise InterruptedError("cancelled before IFileOperation started")
                job.result = self._perform(
                    job.path, job.transaction_id, job.expected_identity, job.cancelled
                )
            finally:
                ole32.CoUninitialize()
        except Exception as error:
            job.error = error
        finally:
            job.done.set()
            with self._active_lock:
                self._active = {item for item in self._active if item[1] is not job}

    @staticmethod
    def _assert_identity(path: Path, expected: FileIdentity) -> None:
        try:
            actual = FileValidator._identity(path, path.lstat())
        except OSError as error:
            raise RuntimeError("source disappeared before recycle") from error
        if actual != expected:
            raise RuntimeError("source identity changed before recycle")

    @staticmethod
    def _perform(path: Path, transaction_id: str, expected_identity: FileIdentity, cancelled) -> RecycleReceipt:
        from ctypes import wintypes
        import uuid

        IFileOperationRecycler._assert_identity(path, expected_identity)
        if cancelled.is_set():
            raise InterruptedError("cancelled before shell item creation")
        WINFUNCTYPE = ctypes.WINFUNCTYPE

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

            @classmethod
            def parse(cls, text):
                return cls.from_buffer_copy(uuid.UUID(text).bytes_le)

        clsid = GUID.parse("3ad05575-8857-4850-9277-11b85bdb8e09")
        iid = GUID.parse("947aab5f-0a5c-4c13-b4d6-4bf7836fc9f8")
        shell_iid = GUID.parse("43826d1e-e718-42ee-bc55-a1e261c37bfe")
        operation = ctypes.c_void_p()
        shell_item = ctypes.c_void_p()
        ole32 = ctypes.OleDLL("ole32")
        shell32 = ctypes.WinDLL("shell32")
        ole32.CoCreateInstance.argtypes = [
            ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
        ]
        hr = ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(operation))
        if hr < 0:
            raise OSError(f"CoCreateInstance failed: 0x{hr & 0xffffffff:08X}")

        def call(obj, index, restype, argtypes=(), args=()):
            vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            function = WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtable[index])
            return function(obj, *args)

        try:
            shell32.SHCreateItemFromParsingName.argtypes = [
                wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)
            ]
            hr = shell32.SHCreateItemFromParsingName(
                str(path), None, ctypes.byref(shell_iid), ctypes.byref(shell_item)
            )
            if hr < 0:
                raise OSError(f"Shell item failed: 0x{hr & 0xffffffff:08X}")
            IFileOperationRecycler._assert_identity(path, expected_identity)
            if cancelled.is_set():
                raise InterruptedError("cancelled before IFileOperation commit")
            hr = call(operation, 5, ctypes.c_long, (wintypes.DWORD,), (RECYCLE_FLAGS,))
            if hr < 0:
                raise OSError(f"SetOperationFlags failed: 0x{hr & 0xffffffff:08X}")
            hr = call(operation, 18, ctypes.c_long, (ctypes.c_void_p, ctypes.c_void_p), (shell_item, None))
            if hr < 0:
                raise OSError(f"DeleteItem failed: 0x{hr & 0xffffffff:08X}")
            # Final fail-closed identity check at the commit boundary.
            IFileOperationRecycler._assert_identity(path, expected_identity)
            if cancelled.is_set():
                raise InterruptedError("cancelled at IFileOperation commit boundary")
            hr = call(operation, 21, ctypes.c_long)
            if hr < 0:
                raise OSError(f"PerformOperations failed: 0x{hr & 0xffffffff:08X}")
            aborted = wintypes.BOOL()
            hr = call(
                operation, 22, ctypes.c_long,
                (ctypes.POINTER(wintypes.BOOL),), (ctypes.byref(aborted),),
            )
            if hr < 0 or aborted.value or path.exists():
                raise RuntimeError("IFileOperation completion could not be verified")
            return RecycleReceipt.create(
                transaction_id,
                expected_identity,
                evidence="ifileoperation:perform-succeeded:not-aborted:source-absent:undo-required",
            )
        finally:
            if shell_item:
                call(shell_item, 2, wintypes.ULONG)
            if operation:
                call(operation, 2, wintypes.ULONG)

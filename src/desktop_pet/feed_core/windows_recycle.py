"""Windows recycle adapter using IFileOperation and a real progress sink.

Nothing in this module runs at import time.  A caller must explicitly submit a
validated ``PreparedFeed``.  There is no permanent-delete fallback.
"""
from __future__ import annotations

import ctypes
import os
import queue
import threading
from ctypes import wintypes

from .business import TrustedRecycleReceipt


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, value: str):
        import uuid
        raw = uuid.UUID(value).bytes_le
        return cls.from_buffer_copy(raw)


HRESULT = ctypes.c_int32
ULONG = ctypes.c_uint32
DWORD = ctypes.c_uint32
BOOL = ctypes.c_int32
PVOID = ctypes.c_void_p
CALL = ctypes.WINFUNCTYPE if os.name == "nt" else ctypes.CFUNCTYPE
S_OK, E_NOINTERFACE = 0, ctypes.c_long(0x80004002).value
COINIT_APARTMENTTHREADED = 2
CLSCTX_INPROC_SERVER = 1
FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMATION = 0x0010
FOF_NOERRORUI = 0x0400
FOF_SILENT = 0x0004
FOFX_RECYCLEONDELETE = 0x00080000
FOFX_NOCOPYSECURITYATTRIBS = 0x00000800
FOFX_EARLYFAILURE = 0x00100000
FOFX_NOELEVATION = 0x10000000
SIGDN_DESKTOPABSOLUTEPARSING = 0x80028000

CLSID_FILE_OPERATION = GUID.parse("3AD05575-8857-4850-9277-11B85BDB8E09")
IID_IFILE_OPERATION = GUID.parse("947AAB5F-0A5C-4C13-B4D6-4BF7836FC9F8")
IID_IFILE_OPERATION_PROGRESS_SINK = GUID.parse("04B0F1A7-9490-44BC-96E1-4296A31252E2")
IID_ISHELL_ITEM = GUID.parse("43826D1E-E718-42EE-BC55-A1E261C37BFE")


def _method(pointer, index, restype, *argtypes):
    address = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(PVOID))).contents[index]
    return CALL(restype, PVOID, *argtypes)(address)


class _ProgressSink:
    """ctypes IFileOperationProgressSink whose callbacks remain strongly held."""

    def __init__(self):
        self.refcount = 1
        self.item_count = 0
        self.post_hresult = -1
        self.new_item = ""
        callbacks = []
        callbacks.append(CALL(HRESULT, PVOID, PVOID, ctypes.POINTER(PVOID))(self._query))
        callbacks.append(CALL(ULONG, PVOID)(self._addref))
        callbacks.append(CALL(ULONG, PVOID)(self._release))
        callbacks.append(CALL(HRESULT, PVOID)(lambda _this: S_OK))               # Start
        callbacks.append(CALL(HRESULT, PVOID, HRESULT)(lambda _this, _hr: S_OK)) # Finish
        # rename/move/copy callbacks: their results are irrelevant for DeleteItem.
        for argc in (3, 5, 4, 6, 4, 6):
            callbacks.append(CALL(HRESULT, PVOID, *([PVOID] * argc))(lambda *_: S_OK))
        callbacks.append(CALL(HRESULT, PVOID, DWORD, PVOID)(lambda *_: S_OK))   # PreDelete
        callbacks.append(CALL(HRESULT, PVOID, DWORD, PVOID, HRESULT, PVOID)(self._post_delete))
        callbacks.append(CALL(HRESULT, PVOID, DWORD, PVOID, wintypes.LPCWSTR)(lambda *_: S_OK))
        callbacks.append(CALL(HRESULT, PVOID, DWORD, PVOID, wintypes.LPCWSTR,
                              wintypes.LPCWSTR, DWORD, HRESULT, PVOID)(lambda *_: S_OK))
        callbacks.append(CALL(HRESULT, PVOID, wintypes.UINT, wintypes.UINT)(lambda *_: S_OK))
        callbacks.extend(CALL(HRESULT, PVOID)(lambda _this: S_OK) for _ in range(3))
        self._callbacks = callbacks
        vtable_type = PVOID * len(callbacks)
        self._vtable = vtable_type(*(ctypes.cast(cb, PVOID).value for cb in callbacks))
        self._vtable_pointer = ctypes.cast(self._vtable, PVOID)
        self._object = (PVOID * 1)(self._vtable_pointer)
        self.pointer = ctypes.cast(self._object, PVOID)

    def _query(self, _this, iid, out):
        out[0] = self.pointer
        self._addref(None)
        return S_OK

    def _addref(self, _this):
        self.refcount += 1
        return self.refcount

    def _release(self, _this):
        self.refcount = max(0, self.refcount - 1)
        return self.refcount

    def _post_delete(self, _this, _flags, _source, result, newly_created):
        self.item_count += 1
        self.post_hresult = int(result)
        if newly_created:
            value = wintypes.LPWSTR()
            hr = _method(newly_created, 5, HRESULT, wintypes.DWORD,
                         ctypes.POINTER(wintypes.LPWSTR))(
                             newly_created, SIGDN_DESKTOPABSOLUTEPARSING, ctypes.byref(value))
            if hr >= 0 and value.value:
                self.new_item = value.value
                ctypes.windll.ole32.CoTaskMemFree(value)
        return S_OK


def _release(pointer):
    if pointer:
        _method(pointer, 2, ULONG)(pointer)


def _perform(prepared) -> TrustedRecycleReceipt:
    ole32, shell32 = ctypes.windll.ole32, ctypes.windll.shell32
    hr = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    if hr < 0:
        raise OSError(f"CoInitializeEx failed: 0x{hr & 0xffffffff:08x}")
    operation = PVOID(); item = PVOID(); cookie = DWORD()
    sink = _ProgressSink()
    try:
        hr = ole32.CoCreateInstance(ctypes.byref(CLSID_FILE_OPERATION), None,
                                    CLSCTX_INPROC_SERVER, ctypes.byref(IID_IFILE_OPERATION),
                                    ctypes.byref(operation))
        if hr < 0: raise OSError("CoCreateInstance(IFileOperation) failed")
        hr = shell32.SHCreateItemFromParsingName(prepared.snapshot.canonical_path, None,
                                                 ctypes.byref(IID_ISHELL_ITEM), ctypes.byref(item))
        if hr < 0: raise OSError("SHCreateItemFromParsingName failed")
        hr = _method(operation, 3, HRESULT, PVOID, ctypes.POINTER(DWORD))(
            operation, sink.pointer, ctypes.byref(cookie))
        if hr < 0: raise OSError("IFileOperation.Advise failed")
        flags = (FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT |
                 FOFX_RECYCLEONDELETE | FOFX_NOCOPYSECURITYATTRIBS | FOFX_EARLYFAILURE |
                 FOFX_NOELEVATION)
        if _method(operation, 5, HRESULT, DWORD)(operation, flags) < 0:
            raise OSError("IFileOperation.SetOperationFlags failed")
        if _method(operation, 18, HRESULT, PVOID, PVOID)(operation, item, None) < 0:
            raise OSError("IFileOperation.DeleteItem failed")
        perform_hr = int(_method(operation, 21, HRESULT)(operation))
        aborted = BOOL()
        aborted_hr = _method(operation, 22, HRESULT, ctypes.POINTER(BOOL))(
            operation, ctypes.byref(aborted))
        if aborted_hr < 0:
            aborted.value = 1
        return TrustedRecycleReceipt(prepared.operation_id, sink.item_count,
            sink.post_hresult, sink.new_item, perform_hr, bool(aborted.value),
            prepared.snapshot.volume_serial, prepared.snapshot.file_id_128)
    finally:
        if operation and cookie.value:
            _method(operation, 4, HRESULT, DWORD)(operation, cookie)
        _release(item); _release(operation); ole32.CoUninitialize()


class StaIFileOperationRecycler:
    """Single-file serialized STA worker with bounded submission and shutdown."""

    def __init__(self, dispatch, timeout_seconds: float = 30.0):
        if os.name != "nt":
            raise OSError("IFileOperation is available only on Windows")
        self.dispatch = dispatch
        self.timeout_seconds = timeout_seconds
        self._queue = queue.Queue(maxsize=1)
        self._closing = threading.Event()
        self._thread = threading.Thread(target=self._run, name="feed-ifileoperation-sta", daemon=True)
        self._thread.start()

    def submit(self, prepared, callback):
        try:
            self._queue.put_nowait((prepared, callback))
        except queue.Full as error:
            raise TimeoutError("recycle worker already has an operation") from error

    def close(self):
        self._closing.set()
        try: self._queue.put_nowait(None)
        except queue.Full: pass
        self._thread.join(self.timeout_seconds)

    def _run(self):
        while not self._closing.is_set():
            job = self._queue.get()
            if job is None: return
            prepared, callback = job
            delivered = threading.Event()

            def deliver(result):
                if delivered.is_set():
                    return
                delivered.set()
                self.dispatch(lambda result=result, callback=callback: callback(result))

            # COM offers no safe cross-apartment force-cancel for an in-flight
            # PerformOperations call.  Bound the application-visible wait and
            # report uncertainty; the daemon STA is quarantined if Shell hangs.
            timer = threading.Timer(
                self.timeout_seconds,
                lambda: deliver(TimeoutError("IFileOperation timed out; outcome needs review")),
            )
            timer.daemon = True
            timer.start()
            try: result = _perform(prepared)
            except Exception as error: result = error
            finally: timer.cancel()
            deliver(result)

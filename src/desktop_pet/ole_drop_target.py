"""Minimal, non-consuming Win32 OLE drop target for file-drag feedback."""

from __future__ import annotations

import ctypes
import ntpath
import os
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable, Protocol

from .drag_expectation import DROPEFFECT_COPY, DROPEFFECT_NONE
from .drag_foundation_adapter import DragCandidate


CF_HDROP = 15
DVASPECT_CONTENT = 1
TYMED_HGLOBAL = 1
S_OK = 0
S_FALSE = 1
E_NOINTERFACE = -2147467262
E_FAIL = -2147467259


@dataclass(frozen=True)
class FormatRequest:
    cf_format: int = CF_HDROP
    tymed: int = TYMED_HGLOBAL


class Feedback(Protocol):
    def drag_enter(self, is_file: bool, in_region: bool) -> int: ...
    def drag_over(self, is_file: bool, in_region: bool) -> int: ...
    def drag_leave(self) -> None: ...
    def drop(self) -> int: ...
    def exception(self) -> None: ...


def query_hdrop(data_object: object) -> bool:
    """Ask about CF_HDROP support without requesting its HGLOBAL or paths."""

    query = getattr(data_object, "query_get_data", None)
    if not callable(query):
        return False
    try:
        return bool(query(FormatRequest()))
    except Exception:
        return False


def extract_single_local_hdrop(data_object: object) -> DragCandidate | None:
    """Copy one local absolute path from CF_HDROP; never retain IDataObject state."""

    getter = getattr(data_object, "get_hdrop_paths", None)
    if not callable(getter):
        return None
    try:
        paths = tuple(str(path) for path in getter())
    except Exception:
        return None
    if len(paths) != 1:
        return None
    path = paths[0]
    drive, tail = ntpath.splitdrive(path)
    if (
        len(drive) != 2
        or drive[0] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        or drive[1] != ":"
        or not tail.startswith(("\\", "/"))
        or path.startswith(("\\\\", "//", "\\?\\", "\\.\\"))
    ):
        return None
    if os.path.isdir(path):
        return None
    return DragCandidate(path=path, count=1)


class OleDropTarget:
    def __init__(
        self,
        feedback: Feedback,
        in_sensing_region: Callable[[tuple[int, int]], bool],
    ) -> None:
        self.feedback = feedback
        self._in_sensing_region = in_sensing_region
        self._is_file = False

    @staticmethod
    def _source_allows_copy(allowed_effects: int) -> bool:
        return bool(allowed_effects & DROPEFFECT_COPY)

    def drag_enter(
        self, data_object: object, point: tuple[int, int], allowed_effects: int
    ) -> int:
        try:
            self._is_file = query_hdrop(data_object)
            copy_allowed = self._source_allows_copy(allowed_effects)
            effect = self.feedback.drag_enter(
                self._is_file and copy_allowed,
                bool(self._in_sensing_region(point)),
            )
            return effect if copy_allowed else DROPEFFECT_NONE
        except Exception:
            self._is_file = False
            self._safe_exception()
            return DROPEFFECT_NONE

    def drag_over(self, point: tuple[int, int], allowed_effects: int) -> int:
        try:
            copy_allowed = self._source_allows_copy(allowed_effects)
            effect = self.feedback.drag_over(
                self._is_file and copy_allowed,
                bool(self._in_sensing_region(point)),
            )
            return effect if copy_allowed else DROPEFFECT_NONE
        except Exception:
            self._safe_exception()
            return DROPEFFECT_NONE

    def drag_leave(self) -> None:
        self._is_file = False
        try:
            self.feedback.drag_leave()
        except Exception:
            self._safe_exception()

    def drop(
        self, _data_object: object, _point: tuple[int, int], _allowed_effects: int
    ) -> int:
        self._is_file = False
        try:
            self.feedback.drop()
        except Exception:
            self._safe_exception()
        return DROPEFFECT_NONE

    def _safe_exception(self) -> None:
        try:
            self.feedback.exception()
        except Exception:
            pass


class FoundationDragHandler(Protocol):
    def enter(self, candidate: DragCandidate, point: tuple[int, int], effects: int) -> int: ...
    def over(self, point: tuple[int, int], effects: int) -> int: ...
    def leave(self, reason: str = "leave") -> None: ...
    def drop(self, candidate: DragCandidate, point: tuple[int, int], effects: int) -> int: ...


class FoundationOleDropTarget:
    """OLE boundary that passes copied values—not IDataObject—to shared services."""

    def __init__(self, adapter: FoundationDragHandler) -> None:
        self.adapter = adapter

    def drag_enter(self, data_object: object, point: tuple[int, int], effects: int) -> int:
        candidate = extract_single_local_hdrop(data_object)
        if candidate is None:
            self.adapter.leave("invalid-object")
            return DROPEFFECT_NONE
        return self.adapter.enter(candidate, point, effects)

    def drag_over(self, point: tuple[int, int], effects: int) -> int:
        return self.adapter.over(point, effects)

    def drag_leave(self) -> None:
        self.adapter.leave("leave")

    def drop(self, data_object: object, point: tuple[int, int], effects: int) -> int:
        candidate = extract_single_local_hdrop(data_object)
        if candidate is None:
            self.adapter.leave("invalid-drop")
            return DROPEFFECT_NONE
        return self.adapter.drop(candidate, point, effects)

    def _safe_exception(self) -> None:
        try:
            self.adapter.leave("ole-exception")
        except Exception:
            pass


class DropTargetRegistration:
    """Exactly-once lifetime owner; injectable for tests."""

    def __init__(self, hwnd: int, target: object, registrar: object | None = None) -> None:
        self.hwnd = hwnd
        self.target = target
        self.registrar = registrar or WindowsDropTargetRegistrar()
        self.registered = False

    def register(self) -> None:
        if self.registered:
            return
        self.registrar.register(self.hwnd, self.target)
        self.registered = True

    def revoke(self) -> None:
        if not self.registered:
            return
        self.registrar.revoke(self.hwnd)
        self.registered = False


class _FORMATETC(ctypes.Structure):
    _fields_ = [
        ("cfFormat", wintypes.WORD),
        ("ptd", ctypes.c_void_p),
        ("dwAspect", wintypes.DWORD),
        ("lindex", wintypes.LONG),
        ("tymed", wintypes.DWORD),
    ]


class _STGMEDIUM_VALUE(ctypes.Union):
    _fields_ = [
        ("hBitmap", wintypes.HBITMAP),
        ("hMetaFilePict", ctypes.c_void_p),
        ("hEnhMetaFile", ctypes.c_void_p),
        ("hGlobal", wintypes.HGLOBAL),
        ("lpszFileName", wintypes.LPWSTR),
        ("pstm", ctypes.c_void_p),
        ("pstg", ctypes.c_void_p),
    ]


class _STGMEDIUM(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [
        ("tymed", wintypes.DWORD),
        ("value", _STGMEDIUM_VALUE),
        ("pUnkForRelease", ctypes.c_void_p),
    ]


class _POINTL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


_CALLBACK = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
_HRESULT = wintypes.LONG


class _IDataObjectProxy:
    def __init__(self, pointer: int) -> None:
        self.pointer = ctypes.c_void_p(pointer)

    def query_get_data(self, request: FormatRequest) -> bool:
        vtable = ctypes.cast(
            self.pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        query = _CALLBACK(_HRESULT, ctypes.c_void_p, ctypes.POINTER(_FORMATETC))(
            vtable[5]
        )
        fmt = _FORMATETC(request.cf_format, None, DVASPECT_CONTENT, -1, request.tymed)
        return query(self.pointer, ctypes.byref(fmt)) == S_OK

    def get_hdrop_paths(self) -> tuple[str, ...]:
        vtable = ctypes.cast(
            self.pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        get_data = _CALLBACK(
            _HRESULT,
            ctypes.c_void_p,
            ctypes.POINTER(_FORMATETC),
            ctypes.POINTER(_STGMEDIUM),
        )(vtable[3])
        fmt = _FORMATETC(CF_HDROP, None, DVASPECT_CONTENT, -1, TYMED_HGLOBAL)
        medium = _STGMEDIUM()
        result = get_data(self.pointer, ctypes.byref(fmt), ctypes.byref(medium))
        if result != S_OK:
            return ()
        ole32 = ctypes.OleDLL("ole32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        release = ole32.ReleaseStgMedium
        release.argtypes = [ctypes.POINTER(_STGMEDIUM)]
        release.restype = None
        drag_query = shell32.DragQueryFileW
        drag_query.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        drag_query.restype = wintypes.UINT
        try:
            if medium.tymed != TYMED_HGLOBAL or not medium.hGlobal:
                return ()
            count = int(drag_query(medium.hGlobal, 0xFFFFFFFF, None, 0))
            paths: list[str] = []
            for index in range(count):
                length = int(drag_query(medium.hGlobal, index, None, 0))
                buffer = ctypes.create_unicode_buffer(length + 1)
                copied = int(drag_query(medium.hGlobal, index, buffer, len(buffer)))
                if copied != length:
                    return ()
                paths.append(buffer.value)
            return tuple(paths)
        finally:
            release(ctypes.byref(medium))


class _DropTargetVTable(ctypes.Structure):
    _fields_ = [(name, ctypes.c_void_p) for name in (
        "QueryInterface", "AddRef", "Release", "DragEnter", "DragOver", "DragLeave", "Drop"
    )]


class _DropTargetObject(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(_DropTargetVTable))]


class _NativeDropTarget:
    """ctypes COM shell. Callback references live for the registration lifetime."""

    _iid_unknown = uuid.UUID("00000000-0000-0000-C000-000000000046").bytes_le
    _iid_drop_target = uuid.UUID("00000122-0000-0000-C000-000000000046").bytes_le

    def __init__(self, target: OleDropTarget) -> None:
        self.target = target
        self.references = 1
        self._callbacks = (
            _CALLBACK(_HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self._query_interface),
            _CALLBACK(wintypes.ULONG, ctypes.c_void_p)(self._add_ref),
            _CALLBACK(wintypes.ULONG, ctypes.c_void_p)(self._release),
            _CALLBACK(_HRESULT, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, _POINTL, ctypes.POINTER(wintypes.DWORD))(self._drag_enter),
            _CALLBACK(_HRESULT, ctypes.c_void_p, wintypes.DWORD, _POINTL, ctypes.POINTER(wintypes.DWORD))(self._drag_over),
            _CALLBACK(_HRESULT, ctypes.c_void_p)(self._drag_leave),
            _CALLBACK(_HRESULT, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, _POINTL, ctypes.POINTER(wintypes.DWORD))(self._drop),
        )
        self._vtable = _DropTargetVTable(*(ctypes.cast(cb, ctypes.c_void_p) for cb in self._callbacks))
        self.com_object = _DropTargetObject(ctypes.pointer(self._vtable))

    @property
    def pointer(self) -> ctypes.c_void_p:
        return ctypes.cast(ctypes.pointer(self.com_object), ctypes.c_void_p)

    def _query_interface(self, this, iid, output) -> int:
        raw = ctypes.string_at(iid, 16)
        if raw not in (self._iid_unknown, self._iid_drop_target):
            output[0] = None
            return E_NOINTERFACE
        output[0] = this
        self._add_ref(this)
        return S_OK

    def _add_ref(self, _this) -> int:
        self.references += 1
        return self.references

    def _release(self, _this) -> int:
        self.references = max(0, self.references - 1)
        return self.references

    @staticmethod
    def _set_effect(effect_pointer, effect: int) -> None:
        if effect_pointer:
            effect_pointer[0] = effect

    def _drag_enter(self, _this, data, _keys, point, effect) -> int:
        try:
            result = self.target.drag_enter(_IDataObjectProxy(data), (point.x, point.y), effect[0])
            self._set_effect(effect, result)
            return S_OK
        except Exception:
            self.target._safe_exception()
            self._set_effect(effect, DROPEFFECT_NONE)
            return E_FAIL

    def _drag_over(self, _this, _keys, point, effect) -> int:
        try:
            result = self.target.drag_over((point.x, point.y), effect[0])
            self._set_effect(effect, result)
            return S_OK
        except Exception:
            self.target._safe_exception()
            self._set_effect(effect, DROPEFFECT_NONE)
            return E_FAIL

    def _drag_leave(self, _this) -> int:
        try:
            self.target.drag_leave()
            return S_OK
        except Exception:
            self.target._safe_exception()
            return E_FAIL

    def _drop(self, _this, data, _keys, point, effect) -> int:
        try:
            result = self.target.drop(_IDataObjectProxy(data), (point.x, point.y), effect[0])
            self._set_effect(effect, result)
            return S_OK
        except Exception:
            self.target._safe_exception()
            self._set_effect(effect, DROPEFFECT_NONE)
            return E_FAIL


class WindowsDropTargetRegistrar:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("OLE drop target registration requires Windows")
        self._ole32 = ctypes.OleDLL("ole32", use_last_error=True)
        self._ole32.OleInitialize.argtypes = [ctypes.c_void_p]
        self._ole32.OleInitialize.restype = _HRESULT
        self._ole32.OleUninitialize.argtypes = []
        self._ole32.OleUninitialize.restype = None
        self._ole32.RegisterDragDrop.argtypes = [wintypes.HWND, ctypes.c_void_p]
        self._ole32.RegisterDragDrop.restype = _HRESULT
        self._ole32.RevokeDragDrop.argtypes = [wintypes.HWND]
        self._ole32.RevokeDragDrop.restype = _HRESULT
        self._native: _NativeDropTarget | None = None
        self._initialized = False

    def register(self, hwnd: int, target: object) -> None:
        if not isinstance(target, (OleDropTarget, FoundationOleDropTarget)):
            raise TypeError("target must implement the desktop-pet OLE drop target")
        result = self._ole32.OleInitialize(None)
        if result not in (S_OK, S_FALSE):
            raise OSError(result, "OleInitialize failed")
        self._initialized = True
        self._native = _NativeDropTarget(target)
        result = self._ole32.RegisterDragDrop(wintypes.HWND(hwnd), self._native.pointer)
        if result != S_OK:
            self._native = None
            self._ole32.OleUninitialize()
            self._initialized = False
            raise OSError(result, "RegisterDragDrop failed")

    def revoke(self, hwnd: int) -> None:
        result = self._ole32.RevokeDragDrop(wintypes.HWND(hwnd))
        if result != S_OK:
            raise OSError(result, "RevokeDragDrop failed")
        self._native = None
        if self._initialized:
            self._ole32.OleUninitialize()
            self._initialized = False

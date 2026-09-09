"""Handle-bound Windows file identity inspection for FEED validation."""
from __future__ import annotations
import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from .business import FileSnapshot, MAX_BYTES

GENERIC_READ_ATTRIBUTES = 0x80
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4
OPEN_EXISTING = 3
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
FILE_ID_INFO_CLASS = 18
DRIVE_FIXED = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class FILE_ID_128(ctypes.Structure):
    _fields_ = [("Identifier", ctypes.c_ubyte * 16)]


class FILE_ID_INFO(ctypes.Structure):
    _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong), ("FileId", FILE_ID_128)]


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class WindowsFileIdentityInspector:
    def __init__(self, protected_roots=()):
        self.protected_roots = tuple(Path(root).resolve() for root in protected_roots)

    def inspect(self, path: str) -> FileSnapshot:
        if os.name != "nt":
            raise OSError("Windows FILE_ID_INFO inspection is Windows-only")
        candidate = Path(path)
        if str(candidate).startswith(("\\\\", "//")):
            raise ValueError("network and virtual paths are rejected")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetDriveTypeW.restype = wintypes.UINT
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.GetFileInformationByHandleEx.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ]
        kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
        kernel32.GetFileInformationByHandle.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION),
        ]
        kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
        kernel32.GetFinalPathNameByHandleW.argtypes = [
            wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
        ]
        kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        absolute = candidate.absolute()
        for component in (absolute, *absolute.parents):
            try:
                component_info = component.lstat()
            except OSError:
                continue
            if getattr(component_info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("reparse point in source path is rejected")
        if kernel32.GetDriveTypeW(absolute.anchor) != DRIVE_FIXED:
            raise ValueError("only local fixed disks are accepted")
        handle = kernel32.CreateFileW(
            str(absolute), GENERIC_READ_ATTRIBUTES,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, None,
        )
        if handle == INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            length = kernel32.GetFinalPathNameByHandleW(handle, None, 0, 0)
            if not length:
                raise ctypes.WinError(ctypes.get_last_error())
            buffer = ctypes.create_unicode_buffer(length + 1)
            if not kernel32.GetFinalPathNameByHandleW(handle, buffer, length + 1, 0):
                raise ctypes.WinError(ctypes.get_last_error())
            final_text = buffer.value
            if final_text.startswith("\\\\?\\"):
                final_text = final_text[4:]
            canonical = Path(final_text)
            for root in self.protected_roots:
                try:
                    canonical.relative_to(root)
                except ValueError:
                    continue
                raise ValueError("protected path is rejected")
            identity = FILE_ID_INFO()
            if not kernel32.GetFileInformationByHandleEx(
                handle, FILE_ID_INFO_CLASS, ctypes.byref(identity), ctypes.sizeof(identity)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            info = BY_HANDLE_FILE_INFORMATION()
            if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            attrs = int(info.dwFileAttributes)
            rejected = (
                FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT |
                FILE_ATTRIBUTE_SYSTEM | FILE_ATTRIBUTE_OFFLINE |
                FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
            )
            if attrs & rejected:
                raise ValueError("directory, reparse, system, or cloud placeholder rejected")
            size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
            if not 0 < size <= MAX_BYTES:
                raise ValueError("file size must be >0 and <=1 GiB")
            modified = (int(info.ftLastWriteTime.dwHighDateTime) << 32) | int(
                info.ftLastWriteTime.dwLowDateTime
            )
            return FileSnapshot(
                canonical_path=str(canonical),
                volume_serial=int(identity.VolumeSerialNumber),
                file_id_128=bytes(identity.FileId.Identifier),
                size_bytes=size,
                modified_100ns=modified,
                attributes=attrs,
            )
        finally:
            kernel32.CloseHandle(handle)

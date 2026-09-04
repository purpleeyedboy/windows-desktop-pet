"""Windows recycle adapter. This module's only destructive capability is IFileOperation."""
from __future__ import annotations
import ctypes
import os
import queue
import threading
from pathlib import Path

COINIT_APARTMENTTHREADED=0x2
FOF_SILENT=0x0004
FOF_NOCONFIRMATION=0x0010
FOF_ALLOWUNDO=0x0040
FOF_NOERRORUI=0x0400
FOFX_RECYCLEONDELETE=0x00080000
RECYCLE_FLAGS=FOF_SILENT|FOF_NOCONFIRMATION|FOF_ALLOWUNDO|FOF_NOERRORUI|FOFX_RECYCLEONDELETE

class _Job:
    def __init__(self,path): self.path=path; self.done=threading.Event(); self.result=False; self.error=None

class IFileOperationRecycler:
    """Serializes IFileOperation calls through one dedicated COM STA thread."""
    def __init__(self):
        self._jobs=queue.Queue(); self._thread=None; self._startup=threading.Event(); self._startup_error=None
        if os.name=='nt':
            self._thread=threading.Thread(target=self._worker,name='FeedRecycleSTA',daemon=True); self._thread.start(); self._startup.wait()
    def recycle(self,path: Path,transaction_id: str) -> bool:
        del transaction_id
        if os.name!='nt': raise OSError('IFileOperation recycling is Windows-only')
        if self._startup_error is not None: raise self._startup_error
        job=_Job(Path(path)); self._jobs.put(job); job.done.wait()
        if job.error: raise job.error
        return job.result
    def close(self):
        if self._thread:
            self._jobs.put(None); self._thread.join(timeout=5); self._thread=None
    def _worker(self):
        ole32=ctypes.OleDLL('ole32'); hr=ole32.CoInitializeEx(None,COINIT_APARTMENTTHREADED)
        if hr not in (0,1):
            self._startup_error=OSError(f'COM STA initialization failed: 0x{hr & 0xffffffff:08X}'); self._startup.set(); return
        self._startup.set()
        try:
            while True:
                job=self._jobs.get()
                if job is None: break
                try: job.result=self._perform(job.path)
                except Exception as error: job.error=error
                finally: job.done.set()
        finally: ole32.CoUninitialize()
    @staticmethod
    def _perform(path: Path) -> bool:
        from ctypes import wintypes
        WINFUNCTYPE=ctypes.WINFUNCTYPE
        class GUID(ctypes.Structure):
            _fields_=[('Data1',wintypes.DWORD),('Data2',wintypes.WORD),('Data3',wintypes.WORD),('Data4',ctypes.c_ubyte*8)]
            @classmethod
            def parse(cls,text):
                import uuid
                b=uuid.UUID(text).bytes_le; return cls.from_buffer_copy(b)
        clsid=GUID.parse('3ad05575-8857-4850-9277-11b85bdb8e09')
        iid=GUID.parse('947aab5f-0a5c-4c13-b4d6-4bf7836fc9f8')
        shell_iid=GUID.parse('43826d1e-e718-42ee-bc55-a1e261c37bfe')
        operation=ctypes.c_void_p(); shell_item=ctypes.c_void_p()
        ole32=ctypes.OleDLL('ole32'); shell32=ctypes.WinDLL('shell32')
        ole32.CoCreateInstance.argtypes=[ctypes.POINTER(GUID),ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)]
        hr=ole32.CoCreateInstance(ctypes.byref(clsid),None,1,ctypes.byref(iid),ctypes.byref(operation))
        if hr<0: raise OSError(f'CoCreateInstance failed: 0x{hr & 0xffffffff:08X}')
        def call(obj,index,restype,argtypes=(),args=()):
            vtable=ctypes.cast(obj,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            fn=WINFUNCTYPE(restype,ctypes.c_void_p,*argtypes)(vtable[index]); return fn(obj,*args)
        try:
            shell32.SHCreateItemFromParsingName.argtypes=[wintypes.LPCWSTR,ctypes.c_void_p,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)]
            hr=shell32.SHCreateItemFromParsingName(str(path),None,ctypes.byref(shell_iid),ctypes.byref(shell_item))
            if hr<0: raise OSError(f'Shell item failed: 0x{hr & 0xffffffff:08X}')
            hr=call(operation,5,ctypes.c_long,(wintypes.DWORD,),(RECYCLE_FLAGS,))
            if hr<0: raise OSError(f'SetOperationFlags failed: 0x{hr & 0xffffffff:08X}')
            hr=call(operation,18,ctypes.c_long,(ctypes.c_void_p,ctypes.c_void_p),(shell_item,None))
            if hr<0: raise OSError(f'DeleteItem failed: 0x{hr & 0xffffffff:08X}')
            hr=call(operation,21,ctypes.c_long)
            if hr<0: raise OSError(f'PerformOperations failed: 0x{hr & 0xffffffff:08X}')
            aborted=wintypes.BOOL(); hr=call(operation,22,ctypes.c_long,(ctypes.POINTER(wintypes.BOOL),),(ctypes.byref(aborted),))
            if hr<0 or aborted.value: return False
            return not path.exists()
        finally:
            if shell_item: call(shell_item,2,wintypes.ULONG)
            if operation: call(operation,2,wintypes.ULONG)

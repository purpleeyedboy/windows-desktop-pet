"""Single native OLE IDropTarget owner for FEED-CORE."""
from __future__ import annotations
import ctypes
import os
import uuid
from ctypes import wintypes
from pathlib import Path

DROP_EFFECT_NONE=0
DROP_EFFECT_COPY=1
CF_HDROP=15
DVASPECT_CONTENT=1
TYMED_HGLOBAL=1
S_OK=0
E_NOINTERFACE=-2147467262
SUPPORTED_IIDS={uuid.UUID("00000000-0000-0000-c000-000000000046").bytes_le,uuid.UUID("00000122-0000-0000-c000-000000000046").bytes_le}

class POINTL(ctypes.Structure): _fields_=[('x',wintypes.LONG),('y',wintypes.LONG)]
class FORMATETC(ctypes.Structure): _fields_=[('cfFormat',wintypes.WORD),('ptd',ctypes.c_void_p),('dwAspect',wintypes.DWORD),('lindex',wintypes.LONG),('tymed',wintypes.DWORD)]
class STGMEDIUM_UNION(ctypes.Union): _fields_=[('hGlobal',wintypes.HGLOBAL),('pstm',ctypes.c_void_p),('pstg',ctypes.c_void_p)]
class STGMEDIUM(ctypes.Structure): _anonymous_=('u',); _fields_=[('tymed',wintypes.DWORD),('u',STGMEDIUM_UNION),('pUnkForRelease',ctypes.c_void_p)]

if os.name=='nt': CALLBACK=ctypes.WINFUNCTYPE
else: CALLBACK=ctypes.CFUNCTYPE
QueryInterface=CALLBACK(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))
AddRef=CALLBACK(wintypes.ULONG,ctypes.c_void_p)
Release=CALLBACK(wintypes.ULONG,ctypes.c_void_p)
DragEnter=CALLBACK(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,POINTL,ctypes.POINTER(wintypes.DWORD))
DragOver=CALLBACK(ctypes.c_long,ctypes.c_void_p,wintypes.DWORD,POINTL,ctypes.POINTER(wintypes.DWORD))
DragLeave=CALLBACK(ctypes.c_long,ctypes.c_void_p)
Drop=CALLBACK(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,POINTL,ctypes.POINTER(wintypes.DWORD))
class VTable(ctypes.Structure): _fields_=[('QueryInterface',QueryInterface),('AddRef',AddRef),('Release',Release),('DragEnter',DragEnter),('DragOver',DragOver),('DragLeave',DragLeave),('Drop',Drop)]
class COMObject(ctypes.Structure): _fields_=[('lpVtbl',ctypes.POINTER(VTable))]

class NativeFileDropTarget:
    def __init__(self,hwnd,runtime):
        if os.name!='nt': raise OSError('OLE file drop is Windows-only')
        self.hwnd=int(hwnd); self.runtime=runtime; self.paths=[]; self._registered=False; self._refs=1
        self._callbacks=(QueryInterface(self._qi),AddRef(self._addref),Release(self._release),DragEnter(self._drag_enter),DragOver(self._drag_over),DragLeave(self._drag_leave),Drop(self._drop))
        self._vtable=VTable(*self._callbacks); self._object=COMObject(ctypes.pointer(self._vtable))
        self._ole32=ctypes.OleDLL('ole32'); self._shell32=ctypes.WinDLL('shell32'); self._kernel32=ctypes.WinDLL('kernel32')
        self._ole32.OleInitialize.argtypes=[ctypes.c_void_p]; self._ole32.OleInitialize.restype=ctypes.c_long
        self._ole32.RegisterDragDrop.argtypes=[wintypes.HWND,ctypes.c_void_p]; self._ole32.RegisterDragDrop.restype=ctypes.c_long
        self._ole32.RevokeDragDrop.argtypes=[wintypes.HWND]; self._ole32.RevokeDragDrop.restype=ctypes.c_long
        self._ole32.ReleaseStgMedium.argtypes=[ctypes.POINTER(STGMEDIUM)]
        self._shell32.DragQueryFileW.argtypes=[wintypes.HANDLE,wintypes.UINT,wintypes.LPWSTR,wintypes.UINT]
        self._shell32.DragQueryFileW.restype=wintypes.UINT
    def register(self):
        hr=self._ole32.OleInitialize(None)
        if hr not in (0,1): raise OSError(f'OleInitialize failed: {hr & 0xffffffff:08X}')
        hr=self._ole32.RegisterDragDrop(wintypes.HWND(self.hwnd),ctypes.byref(self._object))
        if hr<0: self._ole32.OleUninitialize(); raise OSError(f'RegisterDragDrop failed: {hr & 0xffffffff:08X}')
        self._registered=True
    def close(self):
        if self._registered:self._ole32.RevokeDragDrop(wintypes.HWND(self.hwnd)); self._ole32.OleUninitialize(); self._registered=False
        close=getattr(self.runtime,'close',None)
        if callable(close):close()
    def _qi(self,this,iid,out):
        if not iid or ctypes.string_at(iid,16) not in SUPPORTED_IIDS:out[0]=None; return E_NOINTERFACE
        out[0]=ctypes.addressof(self._object); self._refs+=1; return S_OK
    def _addref(self,this): self._refs+=1; return self._refs
    def _release(self,this): self._refs=max(0,self._refs-1); return self._refs
    def _extract_paths(self,data_object):
        vtable=ctypes.cast(data_object,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        get_data=CALLBACK(ctypes.c_long,ctypes.c_void_p,ctypes.POINTER(FORMATETC),ctypes.POINTER(STGMEDIUM))(vtable[3])
        fmt=FORMATETC(CF_HDROP,None,DVASPECT_CONTENT,-1,TYMED_HGLOBAL); medium=STGMEDIUM()
        if get_data(data_object,ctypes.byref(fmt),ctypes.byref(medium))<0:return []
        try:
            count=self._shell32.DragQueryFileW(medium.hGlobal,0xffffffff,None,0)
            if count!=1:return []
            length=self._shell32.DragQueryFileW(medium.hGlobal,0,None,0); buffer=ctypes.create_unicode_buffer(length+1)
            self._shell32.DragQueryFileW(medium.hGlobal,0,buffer,length+1)
            paths=[Path(buffer.value)]
            return paths if len(paths) == 1 else []
        finally:self._ole32.ReleaseStgMedium(ctypes.byref(medium))
    def _effect(self,point,effect):
        allowed=bool(effect[0] & DROP_EFFECT_COPY); value=self.runtime.drag_enter(self.paths,int(point.x),int(point.y)); effect[0]=DROP_EFFECT_COPY if allowed and value=='copy' else DROP_EFFECT_NONE; return S_OK
    def _drag_enter(self,this,data,key,point,effect):
        try:self.paths=self._extract_paths(data); return self._effect(point,effect)
        except Exception:effect[0]=DROP_EFFECT_NONE; return S_OK
    def _drag_over(self,this,key,point,effect):
        try:return self._effect(point,effect)
        except Exception:effect[0]=DROP_EFFECT_NONE; return S_OK
    def _drag_leave(self,this):
        self.paths=[]
        try:self.runtime.drag_leave()
        except Exception:pass
        return S_OK
    def _drop(self,this,data,key,point,effect):
        try:
            paths=self._extract_paths(data)
            allowed=bool(effect[0] & DROP_EFFECT_COPY)
            if allowed and len(paths) == 1 and self.runtime.drag_enter(paths,int(point.x),int(point.y))=='copy':
                result=self.runtime.drop(paths,int(point.x),int(point.y))
                effect[0]=DROP_EFFECT_COPY if result is not None and result.state.value=='Completed' else DROP_EFFECT_NONE
            else:effect[0]=DROP_EFFECT_NONE
        except Exception:effect[0]=DROP_EFFECT_NONE
        finally:self.paths=[]
        return S_OK

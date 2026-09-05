import inspect
from desktop_pet.feed_core.windows_drop import DROP_EFFECT_COPY, NativeFileDropTarget

def test_native_target_is_only_owner_copy_only_and_single_hdrop():
    source=inspect.getsource(__import__('desktop_pet.feed_core.windows_drop',fromlist=['x']))
    assert 'RegisterDragDrop' in source and 'RevokeDragDrop' in source
    assert 'CF_HDROP' in source and 'DragQueryFileW' in source
    assert 'DROP_EFFECT_COPY' in source and 'DROPEFFECT_MOVE' not in source
    assert 'len(paths) == 1' in source

def test_query_interface_rejects_unknown_iid_and_release_can_reach_zero():
    import ctypes, uuid
    import desktop_pet.feed_core.windows_drop as module
    target=object.__new__(NativeFileDropTarget); target._refs=1; target._object=module.COMObject()
    out=ctypes.c_void_p(123); unknown=(ctypes.c_ubyte*16).from_buffer_copy(uuid.uuid4().bytes_le)
    assert target._qi(None,ctypes.byref(unknown),ctypes.pointer(out))==module.E_NOINTERFACE
    assert out.value is None and target._release(None)==0

def test_drag_callbacks_fail_closed_on_runtime_exception():
    import ctypes
    import desktop_pet.feed_core.windows_drop as module
    class Bad:
        def drag_enter(self,*a): raise RuntimeError('bad')
        def drag_leave(self): raise RuntimeError('bad')
    target=object.__new__(NativeFileDropTarget);target.runtime=Bad();target.paths=[]
    effect=module.wintypes.DWORD(module.DROP_EFFECT_COPY);point=module.POINTL(1,1)
    assert target._drag_over(None,0,point,ctypes.pointer(effect))==0 and effect.value==module.DROP_EFFECT_NONE
    assert target._drag_leave(None)==0

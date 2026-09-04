import pytest

from desktop_pet.drag_expectation import DROPEFFECT_COPY, DROPEFFECT_NONE
from desktop_pet.ole_drop_target import (
    CF_HDROP,
    TYMED_HGLOBAL,
    DropTargetRegistration,
    OleDropTarget,
    query_hdrop,
)


class DataObject:
    def __init__(self, supported=True):
        self.supported = supported
        self.formats = []

    def query_get_data(self, format_etc):
        self.formats.append(format_etc)
        return self.supported


class Feedback:
    active = False

    def __init__(self):
        self.calls = []

    def drag_enter(self, valid, inside):
        self.calls.append(("enter", valid, inside))
        self.active = valid and inside
        return DROPEFFECT_COPY if self.active else DROPEFFECT_NONE

    def drag_over(self, valid, inside):
        self.calls.append(("over", valid, inside))
        self.active = valid and inside
        return DROPEFFECT_COPY if self.active else DROPEFFECT_NONE

    def drag_leave(self): self.calls.append(("leave",)); self.active = False
    def drop(self): self.calls.append(("drop",)); self.active = False; return DROPEFFECT_NONE
    def exception(self): self.calls.append(("exception",)); self.active = False


def test_query_hdrop_only_queries_file_drop_format_without_getting_data():
    data = DataObject()
    assert query_hdrop(data) is True
    assert len(data.formats) == 1
    assert data.formats[0].cf_format == CF_HDROP
    assert data.formats[0].tymed == TYMED_HGLOBAL


def test_callbacks_negotiate_copy_only_for_files_in_sensing_region_and_drop_none():
    feedback = Feedback()
    target = OleDropTarget(feedback, lambda point: point[0] >= 10)
    files = DataObject()

    assert target.drag_enter(files, (12, 4), DROPEFFECT_COPY) == DROPEFFECT_COPY
    assert target.drag_over((4, 4), DROPEFFECT_COPY) == DROPEFFECT_NONE
    assert target.drag_over((12, 4), DROPEFFECT_NONE) == DROPEFFECT_NONE
    assert target.drop(files, (12, 4), DROPEFFECT_COPY) == DROPEFFECT_NONE
    assert feedback.calls == [
        ("enter", True, True),
        ("over", True, False),
        ("over", False, True),
        ("drop",),
    ]


def test_enter_without_copy_permission_does_not_activate_feedback():
    feedback = Feedback()
    target = OleDropTarget(feedback, lambda _point: True)

    assert target.drag_enter(DataObject(), (0, 0), DROPEFFECT_NONE) == DROPEFFECT_NONE
    assert feedback.calls == [("enter", False, True)]
    assert feedback.active is False


def test_non_file_multiple_entries_leave_and_callback_exception_restore():
    feedback = Feedback()
    target = OleDropTarget(feedback, lambda _point: True)
    assert target.drag_enter(DataObject(False), (0, 0), DROPEFFECT_COPY) == DROPEFFECT_NONE
    assert target.drag_enter(DataObject(True), (0, 0), DROPEFFECT_COPY) == DROPEFFECT_COPY
    assert target.drag_enter(DataObject(True), (0, 0), DROPEFFECT_COPY) == DROPEFFECT_COPY
    target.drag_leave()
    target.drag_leave()
    assert feedback.active is False

    broken = OleDropTarget(feedback, lambda _point: (_ for _ in ()).throw(RuntimeError("boom")))
    assert broken.drag_enter(DataObject(), (0, 0), DROPEFFECT_COPY) == DROPEFFECT_NONE
    assert feedback.calls[-1] == ("exception",)


class Registrar:
    def __init__(self): self.registered = []; self.revoked = []
    def register(self, hwnd, target): self.registered.append((hwnd, target))
    def revoke(self, hwnd): self.revoked.append(hwnd)


def test_registration_has_one_owner_and_idempotent_revoke():
    registrar = Registrar()
    target = object()
    owner = DropTargetRegistration(42, target, registrar)
    owner.register()
    owner.register()
    owner.revoke()
    owner.revoke()
    assert registrar.registered == [(42, target)]
    assert registrar.revoked == [42]


def test_failed_revoke_keeps_registration_owned_for_retry():
    class FailingRegistrar(Registrar):
        def revoke(self, hwnd):
            super().revoke(hwnd)
            if len(self.revoked) == 1:
                raise OSError("busy")
    registrar = FailingRegistrar()
    owner = DropTargetRegistration(42, object(), registrar)
    owner.register()
    with pytest.raises(OSError, match="busy"):
        owner.revoke()
    assert owner.registered is True
    owner.revoke()
    assert registrar.revoked == [42, 42]

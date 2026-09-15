"""Regressions at the merged ear/paw/groom window boundary."""
from types import SimpleNamespace

import pytest

from desktop_pet.paw_press import PawSide
from tests.test_window import make_headless_window, HeadlessMenu


@pytest.mark.parametrize('event', ['_on_pointer_leave', '_on_focus_lost'])
def test_pointer_ownership_loss_clears_both_feature_candidates(monkeypatch, event):
    window, *_ = make_headless_window(monkeypatch)
    window._paw_candidate = PawSide.LEFT
    window._paw_click_consumed = True
    window._paw_candidate_exceeded = True
    window._ear_press_candidate = 'left'
    window._ear_press_dragged = True
    window._window_dragging = True
    getattr(window, event)(None)
    assert window._paw_candidate is None
    assert window._ear_press_candidate is None
    assert not window._paw_click_consumed
    assert not window._paw_candidate_exceeded
    assert not window._ear_press_dragged
    assert not window._window_dragging
    window.close()


def test_ear_drag_release_does_not_leave_window_dragging(monkeypatch):
    window, *_ = make_headless_window(monkeypatch)
    window._ear_press_candidate = 'left'
    window._ear_press_dragged = True
    window._window_dragging = True
    window._point_in_ear_region = lambda point: 'left'
    window._on_left_release(SimpleNamespace(x_root=0, y_root=0))
    assert not window._window_dragging
    window.close()


def test_all_debug_entrypoints_live_under_one_submenu(monkeypatch):
    window, *_ = make_headless_window(monkeypatch)
    window._groom_debug_menu = True
    window.services = SimpleNamespace(build_info=SimpleNamespace(
        feature_config=SimpleNamespace(debug_menu_enabled=True)))
    menu = window._create_menu()
    assert '公共运行调试' not in menu.commands
    debug = menu.commands['调试']
    assert isinstance(debug, HeadlessMenu)
    assert '公共运行调试' in debug.commands
    assert '白色前爪舔手（3次）' in debug.commands
    window.services = None
    window.close()


def test_failed_eye_presentation_keeps_ear_hit_mask_on_committed_frame(monkeypatch):
    from PIL import Image
    window, _, renderer, *_ = make_headless_window(monkeypatch)
    committed = window._latest_composed_frame
    renderer.failures.append(True)
    with pytest.raises(RuntimeError, match='injected renderer failure'):
        window._display_eye_frame(Image.new('RGBA', committed.size, (0, 0, 0, 0)))
    assert window._latest_composed_frame is committed
    window.close()


def test_bound_debug_registry_does_not_advertise_obsolete_placeholders(monkeypatch):
    from desktop_pet.foundation.config import FeatureConfig
    from desktop_pet.foundation.services import DebugService
    window, *_ = make_headless_window(monkeypatch)
    config = FeatureConfig(test_build=True)
    debug = DebugService(config)
    window.services = SimpleNamespace(
        build_info=SimpleNamespace(feature_config=config), debug=debug,
        runtime=SimpleNamespace(bind=lambda *args: None),
        animation=SimpleNamespace(register=lambda *args: None),
    )
    window._bind_runtime()
    labels = [label for label, _, _ in debug.commands()]
    assert not any('未接入' in label for label in labels)
    assert '左前肢按压' in labels
    assert '立即触发：猫自身左耳' in labels
    window.services = None
    window.close()

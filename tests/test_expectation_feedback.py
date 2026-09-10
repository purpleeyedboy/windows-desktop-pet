from PIL import Image
from desktop_pet.foundation.regions import RegionService
from desktop_pet.foundation.platform import Point, Rect
from desktop_pet.drag_runtime import DragExpectationRuntime
import inspect
from types import SimpleNamespace
from desktop_pet.expectation_window import ExpectationWindow
from desktop_pet.drag_expectation import DragVisualConfig, decorate_drag_expectation


def test_expectation_radius_scales_with_cat_diagonal_and_head_anchor():
    regions = RegionService()
    regions.update_pose(window=Rect(100, 100, 300, 400), source_size=(300, 400),
                        anchors={"head-center": (150, 100)}, alpha=Image.new("L", (300, 400), 255))
    assert regions.hit_test(Point(1000, 200), "expectation") is not None
    assert regions.hit_test(Point(1001, 200), "expectation") is None
    assert regions.hit_test(Point(1000, 200), "click") is None


def test_runtime_loop_is_five_times_faster():
    durations = inspect.signature(DragExpectationRuntime).parameters["durations_ms"].default
    assert durations[-2:] == (20, 20)


def test_expectation_keeps_receiving_live_follow_frames():
    live = Image.new("RGBA", (640, 768), "red")
    shown = []
    window = ExpectationWindow.__new__(ExpectationWindow)
    window.expectation = SimpleNamespace(showing=True, active=True)
    window._particle_phase = 0
    window._expectation_phase = 3
    window._eye_interaction_boxes = ()
    window._anchor = lambda: (0, 0)
    window._apply_image = lambda frame, anchor: shown.append(frame)
    window._display_eye_frame(live)
    assert shown, "expectation must not swallow the default follow callback"
    assert shown[-1].getpixel((500, 700)) == live.getpixel((500, 700))


def test_stars_stay_at_fixed_centers_across_phases():
    base = Image.new("RGBA", (400, 400))
    config = DragVisualConfig(head_box=(80, 80, 300, 300))
    for phase in range(8):
        frame = decorate_drag_expectation(base, phase, config)
        assert frame.getpixel((100, 74))[3] > 0
        assert frame.getpixel((306, 130))[3] > 0


def test_feedback_recomposes_pupils_through_the_current_head_pose():
    from desktop_pet import expectation_window
    assert hasattr(expectation_window, "FollowingExpectationCompositor")
    calls = []
    source = SimpleNamespace(compose=lambda *args: calls.append(args) or Image.new("RGBA", (640, 768)))
    wrapper = expectation_window.FollowingExpectationCompositor(source)
    pose = object()
    wrapper.compose(1.0, 0.5, pose)
    wrapper.feedback(3)
    assert calls[-1][2] is pose
    assert calls[-1][0] < 1.0
    wrapper.feedback(4)
    assert calls[-1][0] > 1.0


def test_cached_center_frame_does_not_reuse_previous_head_pose():
    from desktop_pet.expectation_window import FollowingExpectationCompositor
    from desktop_pet.head_neck_deformation import HeadPose
    calls = []
    source = SimpleNamespace(compose=lambda *args: calls.append(args) or Image.new("RGBA", (640, 768)))
    wrapper = FollowingExpectationCompositor(source)
    center = wrapper.compose(0.0, 0.0, HeadPose(0, 0))
    wrapper.compose(1.0, 0.5, HeadPose(0.5, 0.0))
    wrapper.feedback(3, center)
    assert calls[-1][2] == HeadPose(0, 0)

from __future__ import annotations
from PIL import Image
from desktop_pet.ear_interaction import (
    EAR_ASSETS, EAR_MOTION, EarActionContext, EarFeatureAdapter,
    EarHitMasks, EarPose, render_ear_pose, sample_ear_pose,
)

def test_cat_own_left_and_right_masks_intersect_current_alpha():
    image = Image.new('RGBA', (512, 768), (0, 0, 0, 0))
    image.putpixel((220, 240), (1, 2, 3, 255))  # screen-right = cat-left
    image.putpixel((50, 240), (1, 2, 3, 255))   # screen-left = cat-right
    masks = EarHitMasks.from_frame(image)
    assert masks.hit_source((220, 240)) == 'left'
    assert masks.hit_source((50, 240)) == 'right'
    assert masks.hit_source((219, 239)) is None

def test_dynamic_mapper_is_applied_before_alpha_intersection_and_dpi_mapping():
    image = Image.new('RGBA', (640, 768), (0, 0, 0, 0))
    image.putpixel((284, 252), (255, 255, 255, 255))
    masks = EarHitMasks.from_frame(image, lambda point: (point[0] + 64, point[1] + 12))
    assert masks.hit_display((142, 126), (320, 384)) == 'left'

def test_motion_has_three_shakes_throw_ease_rebound_and_exact_neutral():
    values = [sample_ear_pose('left', i / 1000).angle_degrees for i in range(551)]
    shake = values[:181]
    crossings = sum(a * b < 0 for a, b in zip(shake, shake[1:]))
    assert crossings >= 5
    assert max(values) == EAR_MOTION.maximum_throw_degrees
    assert min(values[300:]) >= -EAR_MOTION.maximum_throw_degrees * EAR_MOTION.rebound_ratio
    assert values[-1] == 0.0

def test_local_texture_deformation_keeps_neutral_identity_and_opposite_ear_unchanged():
    image = Image.new('RGBA', (512, 768), (0, 0, 0, 0))
    for y in range(190, 340):
        for x in range(20, 250):
            image.putpixel((x, y), (x % 256, y % 256, 60, 255))
    assert render_ear_pose(image, 'left', EarPose()).tobytes() == image.tobytes()
    changed = render_ear_pose(image, 'left', EarPose(8.0))
    assert changed.tobytes() != image.tobytes()
    assert changed.crop((20, 200, 110, 340)).tobytes() == image.crop((20, 200, 110, 340)).tobytes()

class Harness:
    def __init__(self):
        self.now = 0.0; self.pending = []; self.frames = []; self.completed = []
    def clock(self): return self.now
    def schedule(self, delay, callback): self.pending.append(callback); return callback
    def cancel(self, token): self.pending = [item for item in self.pending if item is not token]
    def display(self, side, pose): self.frames.append((side, pose))
    def complete(self, context, safe): self.completed.append((context, safe))

def test_adapter_ignores_other_ear_while_active_validates_context_and_cools_down():
    h = Harness(); adapter = EarFeatureAdapter(h.schedule, h.cancel, h.clock, h.display, h.complete)
    first = EarActionContext('ear:left', 4, object())
    other = EarActionContext('ear:right', 5, object())
    assert adapter.start_approved('left', first)
    assert not adapter.start_approved('right', other)
    assert not adapter.cancel_and_recover(other)
    assert adapter.cancel_and_recover(first)
    assert h.frames[-1] == ('left', EarPose())
    assert h.completed == [(first, True)]

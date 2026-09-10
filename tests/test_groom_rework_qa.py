from PIL import Image
from tools.groom_rework_qa import frame_metrics, sequence_report


def test_white_edge_is_flagged_without_calling_white_interior_a_halo():
    image = Image.new('RGBA', (7, 7))
    image.paste((255, 255, 255, 255), (1, 1, 6, 6))
    report = frame_metrics(image)
    assert report['white_boundary_pixels'] == 16
    assert report['opaque_pixels'] == 25


def test_sequence_reports_geometry_and_pixel_jump_separately():
    a = Image.new('RGBA', (7, 7))
    a.paste((50, 40, 30, 255), (1, 1, 4, 4))
    b = a.copy()
    b.putpixel((2, 2), (100, 40, 30, 255))
    report = sequence_report([a, b])
    assert report['transitions'][0]['bbox_delta'] == [0, 0, 0, 0]
    assert report['transitions'][0]['changed_pixels'] == 1
    assert report['acceptance'] == 'requires_visual_review'

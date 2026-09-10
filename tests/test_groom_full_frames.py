import hashlib
import pytest
from PIL import Image

from desktop_pet.groom_import import load_full_cat_frames


def fixture(tmp_path, mode='RGBA'):
    neutral = Image.new('RGBA', (8, 8))
    neutral.paste((90, 60, 30, 255), (2, 2, 6, 6))
    items = []
    for index in range(12):
        frame = neutral.copy()
        if index not in (0, 11):
            frame.putpixel((3, 3), (100 + index, 60, 30, 255))
        path = tmp_path / f'{index:02d}.png'
        frame.convert(mode).save(path)
        items.append({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return neutral, {'format': 'full-cat-rgba-v1', 'frames': items}


def test_full_frames_preserve_pixels_without_masks(tmp_path):
    neutral, data = fixture(tmp_path)
    frames = load_full_cat_frames(tmp_path, data, neutral)
    assert len(frames) == 12
    assert frames[4].getpixel((3, 3)) == (104, 60, 30, 255)
    assert frames[0].tobytes() == neutral.tobytes()


@pytest.mark.parametrize('fault', ['rgb', 'hash', 'endpoint', 'path'])
def test_full_frames_reject_invalid_sources(tmp_path, fault):
    neutral, data = fixture(tmp_path, 'RGB' if fault == 'rgb' else 'RGBA')
    if fault == 'hash':
        data['frames'][-1]['sha256'] = 'invalid'
    if fault == 'endpoint':
        neutral.putpixel((3, 3), (1, 1, 1, 255))
    if fault == 'path':
        data['frames'][0]['path'] = '../outside.png'
    with pytest.raises(ValueError):
        load_full_cat_frames(tmp_path, data, neutral)

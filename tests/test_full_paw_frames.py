import base64
import hashlib
import json
import zlib

from PIL import Image
import pytest

from desktop_pet.paw_compositor import load_generated_paw_frames


def pack(tmp_path, opaque=False):
    image = Image.new('RGBA', (512, 768), (0, 0, 0, 0))
    image.paste((200, 120, 60, 255), (100, 100, 400, 750))
    if opaque:
        image.putalpha(255)
    raw = image.tobytes()
    frame = {'rgba_sha256': hashlib.sha256(raw).hexdigest(),
             'rgba_zlib_base85': base64.b85encode(zlib.compress(raw)).decode()}
    payload = {'encoding': 'generated-full-cat-zlib-base85-v1',
               'source_size': [512, 768], 'source_sha256': 'baseline',
               'frame_map': [None] + list(range(13)) + [None],
               'sides': {side: {'frames': [frame] * 13} for side in ('left', 'right')}}
    path = tmp_path / 'full.json'
    path.write_text(json.dumps(payload))
    return path, image


def test_full_cat_frames_replace_entire_canvas_without_local_feather(tmp_path):
    path, image = pack(tmp_path)
    result = load_generated_paw_frames(path, source_sha256='baseline')
    assert result.layers['left'][1].tobytes() == image.tobytes()
    assert result.replacement_masks['left'][1].getextrema() == (255, 255)
    assert result.replacement_masks['left'][0].getextrema() == (0, 0)


def test_full_cat_frames_reject_fake_opaque_background(tmp_path):
    path, _ = pack(tmp_path, opaque=True)
    with pytest.raises(ValueError, match='transparent'):
        load_generated_paw_frames(path, source_sha256='baseline')


def test_importer_preserves_full_rgba_bytes_and_requires_thirteen_frames(tmp_path):
    from tools.import_full_paw_frames import import_frames
    _, image = pack(tmp_path)
    image.save(tmp_path / 'pose.png')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({side: ['pose.png'] * 13 for side in ('left', 'right')}))
    output = tmp_path / 'output.json'
    import_frames(manifest, output, source_sha256='baseline')
    result = load_generated_paw_frames(output, source_sha256='baseline')
    assert result.layers['right'][7].tobytes() == image.tobytes()
    manifest.write_text(json.dumps({'left': ['pose.png'], 'right': ['pose.png']}))
    with pytest.raises(ValueError, match='13'):
        import_frames(manifest, output, source_sha256='baseline')

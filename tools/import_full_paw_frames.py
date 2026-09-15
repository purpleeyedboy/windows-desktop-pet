"""Losslessly package full-cat RGBA frames; no cutouts, resizing or retouching.

Manifest: {"left": [13 PNG paths], "right": [13 PNG paths]}.
Paths are relative to the manifest. Endpoints restore the existing default pose.
Import success is technical validation, NOT visual acceptance.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zlib

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from desktop_pet.paw_compositor import load_generated_paw_frames


def import_frames(manifest: Path, output: Path, *, source_sha256: str):
    definitions = json.loads(manifest.read_text(encoding='utf-8'))
    payload = {'encoding': 'generated-full-cat-zlib-base85-v1',
               'source_size': [512, 768], 'source_sha256': source_sha256,
               'frame_map': [None] + list(range(13)) + [None], 'sides': {}}
    for side in ('left', 'right'):
        paths = definitions[side]
        if len(paths) != 13:
            raise ValueError('each paw needs 13 intermediate full-cat frames')
        frames = []
        for name in paths:
            path = manifest.parent / name
            with Image.open(path) as image:
                if image.mode != 'RGBA' or image.size != (512, 768):
                    raise ValueError('full-cat PNG must be RGBA 512x768; no automatic conversion')
                raw = image.tobytes()
            frames.append({'rgba_sha256': hashlib.sha256(raw).hexdigest(),
                           'rgba_zlib_base85': base64.b85encode(zlib.compress(raw, 9)).decode('ascii'),
                           'source_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        payload['sides'][side] = {'frames': frames}
    encoded = json.dumps(payload, indent=2) + '\n'
    # Reject a malformed pack before replacing any existing deliverable.
    with tempfile.TemporaryDirectory(prefix='paw-validation-') as folder:
        candidate = Path(folder) / 'candidate.json'
        candidate.write_text(encoded, encoding='utf-8')
        load_generated_paw_frames(candidate, source_sha256=source_sha256)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    from desktop_pet.assets import HEAD_TILT_BACKPLATE_SHA256
    import_frames(args.manifest, args.output, source_sha256=HEAD_TILT_BACKPLATE_SHA256)

"""Read-only full-frame grooming diagnostics; never edits or approves artwork."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


def frame_metrics(image: Image.Image) -> dict:
    image = image.convert('RGBA')
    alpha = image.getchannel('A')
    opaque = alpha.point(lambda value: 255 if value >= 128 else 0)
    interior = opaque.filter(ImageFilter.MinFilter(3))
    boundary = ImageChops.subtract(opaque, interior)
    pixels, edges = image.load(), boundary.load()
    white = sum(1 for y in range(image.height) for x in range(image.width)
                if edges[x, y] and min(pixels[x, y][:3]) >= 235)
    return {'rgba_sha256': hashlib.sha256(image.tobytes()).hexdigest(),
            'size': list(image.size), 'bbox': list(opaque.getbbox() or (0, 0, 0, 0)),
            'opaque_pixels': sum(opaque.histogram()[1:]),
            'white_boundary_pixels': white}


def sequence_report(images: list[Image.Image]) -> dict:
    if not images:
        raise ValueError('at least one frame is required')
    if any(image.size != images[0].size for image in images):
        raise ValueError('all frames must share a canvas')
    images = [image.convert('RGBA') for image in images]
    frames = [frame_metrics(image) for image in images]
    transitions = []
    for index, (a, b) in enumerate(zip(images, images[1:])):
        ap, bp = a.load(), b.load()
        changed = sum(ap[x, y] != bp[x, y] for y in range(a.height) for x in range(a.width))
        transitions.append({'from': index, 'to': index + 1,
                            'changed_pixels': changed,
                            'bbox_delta': [y - x for x, y in zip(frames[index]['bbox'], frames[index + 1]['bbox'])]})
    return {'acceptance': 'requires_visual_review',
            'caution': 'White fur can be naturally white. Boundary counts and pixel changes are diagnostics, not automatic rejection or approval.',
            'frames': frames, 'transitions': transitions}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    paths = sorted(args.directory.glob('*.png'))
    images = []
    for path in paths:
        with Image.open(path) as image:
            images.append(image.convert('RGBA'))
    report = sequence_report(images)
    report['files'] = [path.name for path in paths]
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

import hashlib
import json
from pathlib import Path
import pytest
from PIL import Image
from tools.build_feed_frames import build_feed_assets


def manifest(tmp_path, mode='RGBA'):
    source=tmp_path/'source'; source.mkdir()
    records=[]
    for i in range(6):
        im=Image.new(mode,(640,768),(0,0,0,0) if mode=='RGBA' else 'white')
        if mode=='RGBA':
            im.paste((150,90,60,255),(100,212,540,736))
        p=source/f'{i:02}.png'; im.save(p)
        records.append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    path=tmp_path/'manifest.json'
    path.write_text(json.dumps({'version':3,'composite_mode':'whole_cat_frames','canonical':{'canvas':[640,768]},'frames':records}))
    return path


def test_full_frames_are_validated_and_copied_without_face_composition(tmp_path):
    p=manifest(tmp_path)
    result=build_feed_assets(p,tmp_path/'out')
    assert len(result)==6
    assert result[2].sha256==hashlib.sha256((tmp_path/'source/02.png').read_bytes()).hexdigest()


def test_fake_transparency_is_rejected(tmp_path):
    p=manifest(tmp_path,'RGB')
    with pytest.raises(RuntimeError,match='alpha'):
        build_feed_assets(p,tmp_path/'out')

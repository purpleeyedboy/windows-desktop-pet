"""One player and one idle timer select only explicitly supplied raster clips."""
from pathlib import Path
import sys
from types import SimpleNamespace
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from desktop_pet.groom_frames import GroomFramePlayer


def main() -> int:
    neutral = Image.new('RGBA',(640,768))
    left = (neutral,) + (Image.new('RGBA',(640,768),(200,30,40,255)),)*10 + (neutral,)
    right = (neutral,) + (Image.new('RGBA',(640,768),(20,180,80,255)),)*10 + (neutral,)
    choices = iter(('right','left'))
    rng=SimpleNamespace(uniform=lambda *_:90,randint=lambda *_:3,choice=lambda _:next(choices))
    try:
        player=GroomFramePlayer(left,rng=rng,other_sides={'right':right})
    except TypeError:
        raise AssertionError('one grooming player cannot select separately authored sides') from None
    assert player.available_sides==('left','right')
    summaries=player.clip_summaries()
    assert summaries['left']['frame_count']==summaries['right']['frame_count']==12
    assert summaries['left']['rgba_sha256']!=summaries['right']['rgba_sha256']
    for side, clip in (('right',right),('left',left)):
        assert player.choose_side()==side
        assert player.trigger(0,repetitions=3,side=side)
        assert player.sample(.075).tobytes()==clip[1].tobytes()
        assert not player.trigger(.1,repetitions=3,side='left')
        player.interrupt(.2)
    assert not player.trigger(0,repetitions=3,side='unknown')
    left_only=GroomFramePlayer(left,rng=rng)
    assert left_only.available_sides==('left',) and left_only.choose_side()=='left'
    assert not left_only.trigger(0,repetitions=3,side='right'), 'missing right clip must never mirror or borrow left'
    print('Authored side selection shares one player and refuses missing clips')
    return 0

if __name__=='__main__': raise SystemExit(main())

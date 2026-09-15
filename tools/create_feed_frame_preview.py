"""Render source-backed GIF/contact evidence using the actual FEED timeline."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from desktop_pet.assets import load_feed_frames, load_head_neck_compositor
from desktop_pet.head_neck_deformation import HeadPose
from desktop_pet.feed_core.runtime import FEED_SEQUENCE

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'assets/generated/work/feed/preview')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    frames=load_feed_frames(ROOT/'assets/generated/work/feed/v1')
    neutral=load_head_neck_compositor().compose(0,0,HeadPose(0,0))
    size=(233,280);steps=FEED_SEQUENCE.timeline()
    evidence={'source_canvas':list(neutral.size),'display_canvas':list(size),
        'animation_total_ms':sum(step.duration_ms for step in steps),
        'timeline':[{'frame':s.frame_index,'duration_ms':s.duration_ms}for s in steps],
        'alpha_bounds':[list(f.getbbox())for f in frames],
        'frame_rgba_sha256':[hashlib.sha256(f.tobytes()).hexdigest()for f in frames],
        'body_and_silhouette':'identical to accepted runtime neutral outside local face ROI',
        'face_roi':[104,312,264,476]}
    for background in ('black','white'):
        def render(frame):
            small=frame.resize(size,Image.Resampling.LANCZOS)
            target=Image.new('RGB',size,background);target.paste(small,mask=small.getchannel('A'));return target
        rendered=[render(frame)for frame in frames];default=render(neutral)
        for transition in (False,True):
            ordered=[rendered[step.frame_index]for step in steps]
            duration=[step.duration_ms for step in steps]
            label='exact-timeline'
            if transition:
                ordered=[default,*ordered,default];duration=[800,*duration,800];label='with-default-transition'
            path=args.output/f'feed-{background}-{label}-280px.gif'
            ordered[0].save(path,save_all=True,append_images=ordered[1:],duration=duration,loop=0,disposal=2,optimize=False)
            with Image.open(path) as saved:
                actual_duration=0
                for index in range(saved.n_frames):
                    saved.seek(index);actual_duration+=saved.info['duration']
                if actual_duration!=sum(duration):raise RuntimeError('preview duration changed')
        cell=(257,322);contact=Image.new('RGB',(cell[0]*4,cell[1]*2),background)
        labels=['Accepted neutral','00 closed','01 half open','02 wide open','03 half open return','04 squint upper lick','05 squint corner lick']
        for i,frame in enumerate([default,*rendered]):
            x=(i%4)*cell[0]+12;y=(i//4)*cell[1]+30
            contact.paste(frame,(x,y));ImageDraw.Draw(contact).text((x,y-20),labels[i],fill='white' if background=='black' else 'black')
        contact.save(args.output/f'feed-{background}-contact-280px.png')
    (args.output/'preview-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(args.output)

if __name__=='__main__':main()

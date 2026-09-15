# Bilateral grooming rework — evidence and execution contract

Status: **redraw incomplete; not a new animation acceptance build**.

## Resumed work: full-cat input path

A third built-in ImageGen attempt used freshly reconstructed current runtime
`00.png` (640×768), not the old flat cat image. It requested a complete cat lifting
the mostly white image-left forepaw, with the opposite foreleg planted, fixed
head/rump/feet, and genuine transparent RGBA. The pose was produced on the correct
side, but the returned image was again 1145×1374 RGB with a baked checkerboard.
Visual inspection also found a fuller chest and shifted ears/head geometry.
It is rejected and is not included in the active manifest or EXE.

The existing importer only supported a 4×3 sheet; its right-side branch applies
local masks. A minimal separate `full-cat-rgba-v1` manifest path now accepts twelve
already aligned complete runtime PNGs without resizing, crops, color edits or
local masks. Each `frames` entry contains `path` and `sha256`. Inputs must stay
inside the manifest directory, be native-size RGBA with real transparency and
opaque subject pixels, avoid canvas clipping, and exactly match current neutral
pixels at both endpoints. All twelve inputs validate before output writing.
These checks do not establish identity or smooth-motion visual approval.

No production manifest is switched: a compliant new full-cat animation remains
unavailable. Focused tests cover pixel preservation, missing alpha, final-frame
hash failure, wrong neutral endpoints and escaped source paths.

## Verified root causes

- Baseline: `cee957f`. Right/orange foreground paw is explicitly composited by
  `right_replacement_masks`, `_right_local_frame`, and an underbelly patch in
  `src/desktop_pet/groom_import.py`. Its manifest calls this
  `right-local-limb-and-mouth-v1`. This confirms the user's local-patch concern.
- Left/white paw imports entire subjects, but the generated sheet itself changes
  body geometry and fur. A fixed scale/groundline cannot repair those changes.
- Fresh reconstruction of twelve left frames: neutral opaque width 448 px,
  frame 01 width 427 px; frame 03 to 04 top bound moves upward 14 px; final
  transition widens by 21 px. Full-frame transition changes range 132150–150724
  pixels. These are measurements, not a claim all changed pixels are defects.
- Frame `05.png` visibly has a fine white silhouette outline against black.
  White opaque-boundary counts in frames 05 and 09 are 308 and 368, versus 18
  in neutral. Natural white fur can also score here, so this is a triage metric.
- Right frame 05 visibly changes chest tone and limb texture at the compositing
  seam, with an unnatural mouth/tongue region.

## Rebuild plan

1. Preserve all canonical head/body/eye sources and the existing candidate.
2. Use the actual neutral runtime render as identity/geometry reference, not
   a cropped chest/arm patch. Generate each new keyframe as an entire cat.
3. Per side: neutral → initial lift → half lift → near-mouth → tongue contact
   → short lick return → paw lowering → neutral. Add in-between full-cat poses
   specifically between large geometry changes; never conceal them with
   crossfaded double limbs or duplicate frames.
4. Lock nonmoving hind feet, rump, chest volume, opposite foreleg, face position,
   markings, exposure and saturation. Keep the paw-motion silhouette changes
   without independently resizing each frame to its bounding box.
5. Reject baked backgrounds, missing alpha, white halos, anatomy drift and
   significant nonmoving-part change before importing. No automatic local-mask
   fallback may be called a full-cat redraw.
6. Only after full sets pass visual review, add a separately versioned full-frame
   manifest and importer mode; remove local patch use from that new mode. Keep
   old manifests reconstructable for rollback. Preserve neutral endpoints and
   interruption restoration tests.
7. Rebuild independent Windows candidate; record automated QA separately from
   Windows startup and user visual acceptance.

## Generation evidence

Built-in ImageGen was used with the complete 640×768 neutral runtime reference.
The prompt required a single full cat with the orange foreground paw lifted to
the mouth, unchanged opposite foreleg/rump/head geometry and fur color, cute
anatomically natural tongue, actual transparent RGBA, and no outline/atlas.
First output was rejected: 1145×1374 **RGB**, with a baked checkerboard and
changed hind feet/body proportions. No output from this attempt is imported.
No tool-supported model selector was available; no specific model version is
claimed. Source/reference hashes remain unchanged.

A second targeted attempt emphasized real alpha and unchanged grounded limbs.
It also returned 1145×1374 RGB with a baked checkerboard, and lifted the opposite
paw. It was rejected too. These are two actual failed generation attempts, not
usable full-cat frames. The active runtime has not been relabeled or replaced.

## Reproducible diagnostic commands

```sh
python tools/import_groom_frames.py --output qa/groom-rework/left
python tools/import_groom_frames.py --manifest assets/groom/v2.1/manifest-right.json --output qa/groom-rework/right
python tools/groom_rework_qa.py qa/groom-rework/left
python tools/groom_rework_qa.py qa/groom-rework/right
python -m pytest tests/test_groom_rework_qa.py -q
```

The new tool is read-only: it reports full-frame hashes, geometry, transition
changes and white-boundary counts; it cannot declare visual approval.

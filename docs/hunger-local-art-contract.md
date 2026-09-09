# V2.1 hunger graphic art contract

The candidate uses mouth and tear pixels from the recovered four generated
expressions. The body, ears, eyes, head position and head outline come from the
actual accepted runtime neutral on every frame, including start/end restoration.
Frames must be RGBA, share the neutral canvas and anchor, and contain clean
transparent pixels. Original approved assets and head-turn settings stay immutable.

`hunger_graphic_assets.load_hunger_graphic_assets(neutral)` validates and loads
this recovered frame source. It returns finite `AnimationSequence` clips for
Hungry/Severe and a critical expression frame. `HungerGraphicRuntime` selects
clips; it does not draw replacement mouth shapes, resize individual body parts,
or own a second application state.

All visible action frames enter the shared `PetWindow` graphic player, with
explicit frame durations, canonical restoration and real coordinator tokens.
Critical is an orthogonal idle expression. During menu/drag/feed activity it is
hidden without blocking feeding or shutdown. The images remain candidate art
until Windows visual acceptance.

## Fixed body and local expression composition

`scripts/build_hunger_assets.py` composes the actual zero-angle neutral through
`load_head_neck_compositor().compose(0, 0, HeadPose(0, 0))`. Its 640x768 RGBA SHA-256
is `e02f052cb970d2ebed4946ad0f09038adbce4d41da3a730e09e56783054e5eb0`.
Simply padding `canonical-idle.png` is insufficient because its neck pixels
are not identical to the live compositor output.

The repaired full-cat source is now authoring input only. The builder extracts
the existing generated mouth and tear areas, aligns their recorded nose/eye
landmarks, and feathers them onto solid interior pixels of the live neutral.
It does not substitute the generated body's proportions or silhouette. The
complete alpha channel stays byte-identical to the neutral on all four poses.
RGB pixels outside the reviewed runtime mouth/tear rectangles also stay exact:
`(138,386,224,442)`, `(128,355,166,424)`, `(211,352,254,424)` (inclusive bounds).
The runtime manifest records the true neutral hash and these local bounds.

Both build validation and normal loading reject changed alpha or any changed
pixel outside those rectangles. The focused gate also mutates a body RGB pixel
and a mouth alpha pixel in memory and confirms that each is rejected. This
check is independent of the PNG hash check. Five deduplicated runtime PNGs
still provide the canonical pose and four expression poses; sequence timing,
runtime canvas, feet, head-follow behavior and hunger state logic are unchanged.

## Supplied-mask repair (2026-09-09)

The previous blanket 4px erosion removed most of the small collar bell. The
authoring command `scripts/prepare_hunger_source.py --color SOURCE.png --mask MASK.png`
now derives the checker phase from empty border scanlines, removes only connected
checker pixels around the supplied silhouette, and preserves the mask interior.
The inward/outward confidence bands are not used as a replacement silhouette.
The existing cat colors are retained, with zero RGB under fully transparent Alpha.
No image generation, pose repaint, or canonical asset replacement is involved.

The manifest records the actual re-downloaded input file hashes, input RGB/luma
pixel hashes, previous provenance, and exact lossless output hashes. All 594030
previously opaque interior pixels matched the re-downloaded color sheet exactly.
The 29x28 source-space bell ROI contains 633 recovered opaque pixels, compared
with 117 in the eroded source and 520 in the approximate supplied mask. The live
640x768 canvas, bottom anchor, fit bounds and 1700ms sequences remain unchanged.

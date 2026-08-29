# Task R3 Cropped Visual Repair — Localized Authoring Fallback

## Why the authoring approach changes

Four full-canvas image edits failed. The fixed body fill occupies only `(100,365)-(236,551)` on a `512 x 768` canvas, and the eye union occupies only `(60,319)-(185,381)`. The model repeatedly spent detail on regenerating the whole cat while the tiny target region remained soft or eye-like. Do not make another full-canvas attempt.

Use localized, enlarged authoring crops so the requested pixels occupy most of the edit canvas. This changes only scratch authoring inputs; final project pixels are still admitted exclusively through the unchanged fixed masks.

## Scratch crop preparation

Use repository Pillow only to create scratch references under `.superpowers/sdd/organic-head/cropped-repair/`; never commit them.

Body crop box on the canonical canvas: `(70, 335, 266, 581)`; native size `196 x 246`. Create three crops from current `body-fill-guide.png`, canonical, and rejected body source. Scale each crop exactly 4× to `784 x 984` with LANCZOS for photographic images and NEAREST for the neon-green guide mask boundary.

Eye crop box: `(30, 289, 215, 411)`; native size `185 x 122`. Create three crops from current `eye-fill-guide.png`, canonical, and rejected eye source. Scale each crop exactly 6× to `1110 x 732`, using the same photographic/guide resampling rule.

Inspect all six scratch inputs at original resolution before generation.

## Built-in body crop edit

Use built-in `image_gen` with the three local body crop paths via `referenced_image_paths`. Exact prompt:

```text
Use case: precise-object-edit
Asset type: enlarged local hidden shoulder and upper-chest texture patch for a 2D desktop-pet rig
Input images: Image 1 is the 4x enlarged local edit target; replace only its solid neon-green polygon. Image 2 is the matching 4x canonical crop and is the exact authority for this cat's photographic sharpness, short fine Devon Rex waves, orange/white markings, lighting, and grain. Image 3 is the rejected local patch and is only a negative example of blur, painted softness, long vertical woolly tufts, and a plug-like cap.
Primary request: Fill only the neon-green polygon with the anatomically plausible shoulder, upper chest, and torso surface hidden behind this cat's head. Make it look like a direct continuation of the immediately adjacent pixels in Image 2.
Texture: short, fine, close-lying waves at the same sharpness and grain as Image 2. Orange shoulder fur flows naturally downward and backward into the torso. White chest fur stays short and finely waved, with local strand detail and no broad low-detail gray area. The orange-white boundary continues smoothly without a hard ledge.
Invariants: keep the local crop framing, scale, lighting, focus, and anatomy aligned to Image 2. Content outside the polygon is reference context and will be discarded later.
Avoid: no head, face, eye, ear, collar, bell, leg, new anatomy, rounded cap, vertical tuft wall, long woolly curl, circular swirl, hard seam, blur, airbrush, painted texture, plastic texture, hyper-sharp fur, text, watermark, outline, or colored fringe.
```

Inspect only the polygon region after mapping the candidate back to the native `196 x 246` crop. One single-change correction is allowed. Reject if it retains broad blur/gray smear, long vertical tufts, a cap/swirl, a hard orange-white boundary, or visibly mismatched sharpness.

## Built-in eye crop edit

Only after the body candidate passes, use built-in `image_gen` with the three local eye crop paths via `referenced_image_paths`. Exact prompt:

```text
Use case: precise-object-edit
Asset type: enlarged local neutral eye-base underlay for separately movable irises in a 2D desktop-pet rig
Input images: Image 1 is the 6x enlarged local edit target; replace only its two solid neon-green eye regions. Image 2 is the matching 6x canonical face crop and is the exact authority for eyelids, eye corners, facial fur, markings, lighting, focus, and scale. Image 3 is the rejected local underlay and is only a negative example of forbidden iris, dark pupil-like residue, eye-colored rings, and highlights.
Primary request: Fill only the two neon-green regions with plain, neutral, low-detail pale gray-green eyeball base surfaces plus subtle diffuse eyelid shadow. These are hidden bases behind separately movable iris layers, not finished eyes.
Critical requirement: each filled region must be visually uniform through its center. No iris texture, colored iris ring, dark circular center, black blob, pupil, vertical slit, radial spokes, concentric ring, catchlight, glossy highlight, or scene reflection. There must be no recognizable eye symbol after the movable iris is removed.
Invariants: keep eyelids, eye corners, eyelashes, nose, muzzle, facial fur, markings, crop, scale, lighting, and focus aligned to Image 2. Content outside the two green regions is reference context and will be discarded later.
Avoid: iris, pupil, slit, black center, radial pattern, ring, highlight, extra eye, changed expression, clipped eyelid, altered nose fur, blur, painted edge, text, watermark, outline, or colored fringe.
```

Inspect only the two target regions after mapping the candidate back to the native `185 x 122` crop. One single-change correction is allowed. Reject any recognizable iris/pupil/ring/highlight or eyelid/nose intrusion.

## Deterministic placement and Alpha

For each selected generated crop:

1. resize generated RGB to the exact enlarged scratch crop size using LANCZOS if needed;
2. downsample RGB to the exact native crop size with LANCZOS;
3. paste that RGB into its exact crop box on a blank `512 x 768` RGB canvas;
4. body Alpha = existing `masks/body-fill-mask.png`;
5. eye Alpha = pixelwise max of existing eye masks;
6. clear RGB to zero wherever Alpha is zero;
7. save project PNG atomically as `512 x 768 RGBA`.

Verify exact mask-alpha equality, `(0,255)` extrema, transparent RGB zero, 2:3 size, and SHA-256. Create scratch 400% patch views against the canonical adjacent context and inspect them before overwriting project assets.

## Provenance and commit scope

Update `assets/rig/v1/source/authoring.json`: preserve history, append both exact prompts, crop boxes/scales, built-in generated source paths, deterministic crop mapping/Pillow LANCZOS details, mask sources, and new output hashes. Append full evidence to `task-3-report.md`.

Only stage the two AI PNGs and `authoring.json`. Do not stage scratch crops, reports/briefs, R4/R5 outputs, rejected archive, plans/specs, runtime, old QA, or delivery.

Commit message: `fix: localize hidden rig texture authoring`

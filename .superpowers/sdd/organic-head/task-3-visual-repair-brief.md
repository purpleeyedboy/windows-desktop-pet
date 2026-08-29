# Task R3 Visual Repair After Center QA Rejection

## Context and authority

The center math, Alpha, and containment gates pass, but Task R5 rejected the current hidden sources for two visible reasons:

1. the shoulder/chest patch looks soft, painted, rounded, and directionally unlike the canonical short Devon Rex fur;
2. the left eye underlay retains a dark iris/pupil-like form, while the right remains too eye-like.

The rejected iteration is preserved under `qa/rig-v1/rejected/20260829-085501/`. Do not modify it. Do not change Task R2 masks. This repair is limited to the two Task R3 AI color sources and their provenance.

## Required built-in image-edit workflow

Use the built-in OpenAI `image_gen` tool only; no CLI/API. Before each edit, inspect the local target/reference images at original resolution with `view_image`. Generate to the tool's default `$CODEX_HOME/generated_images/...` location first. Do not overwrite project assets until a selected result passes the visual checks below.

### Body edit inputs

- Image 1: `assets/rig/v1/source/guides/body-fill-guide.png` — edit target and fixed-location guide.
- Image 2: `assets/rig/v1/source/canonical-idle.png` — exact identity, fur, lighting, sharpness, markings, scale, and composition reference.
- Image 3: `qa/rig-v1/rejected/20260829-085501/sources/ai/body-fill-raw.png` — rejected negative example; do not imitate its rounded cap, long woolly curls, airbrushed softness, or painted texture.

Use this exact prompt:

```text
Use case: precise-object-edit
Asset type: hidden shoulder, upper-chest, and torso fill source for a 2D desktop-pet rig
Input images: Image 1 is the edit target with one solid neon-green internal region; Image 2 is the exact canonical orange-and-white Devon Rex cat and the authority for identity, fur, markings, lighting, focus, scale, and composition; Image 3 is a rejected negative example whose rounded cap, long woolly curls, airbrushed softness, and painted appearance must not be copied.
Primary request: Replace only the solid neon-green internal region in Image 1 with the anatomically plausible shoulder, upper chest, and torso fur that exists behind the removed head and neck of this exact cat.
Texture and direction: Match Image 2 at pixel-level photographic sharpness and grain. Use short, fine, close-lying Devon Rex waves, not long shaggy or poodle-like curls. Continue the orange shoulder and white chest markings smoothly. Fur strands must follow the shoulder slope naturally downward and slightly backward into the torso, with no circular cap, vertical tuft wall, abrupt swirl, blurred smear, plastic surface, or painterly patch.
Invariants: Preserve all non-green Image 1 content, canvas composition, subject position, scale, legs, feet baseline, body markings, lighting direction, focus, and transparent surroundings aligned to Image 2.
Avoid: no head, face, eye, ear, collar, bell, added leg, text, watermark, outline, colored fringe, background, checkerboard requirement, new object, pose change, crop change, lighting change, rounded plug, long woolly fur, hyper-detailed fur, airbrushed blur, or painted texture.
```

### Eye edit inputs

- Image 1: `assets/rig/v1/source/guides/eye-fill-guide.png` — edit target and fixed-location guide.
- Image 2: `assets/rig/v1/source/canonical-idle.png` — exact identity, eyelid, eye-corner, facial-fur, lighting, scale, and composition reference.
- Image 3: `qa/rig-v1/rejected/20260829-085501/sources/ai/eye-fill-raw.png` — rejected negative example; do not retain its dark left iris/pupil-like form or eye-colored ring.

Use this exact prompt:

```text
Use case: precise-object-edit
Asset type: neutral hidden eye-socket underlay for movable irises in a 2D desktop-pet rig
Input images: Image 1 is the edit target with two solid neon-green iris regions; Image 2 is the exact canonical cat and the authority for eyelids, eye corners, facial fur, markings, lighting, focus, scale, and composition; Image 3 is a rejected negative example showing the forbidden dark iris/pupil-like residue.
Primary request: Replace only the two solid neon-green regions in Image 1 with a neutral, low-contrast pale gray-green eyeball underlay and subtle diffuse eyelid shadow that can sit behind separately movable irises.
Critical eye requirement: Both underlays must read as plain low-detail eye base surfaces, not as finished eyes. They must contain no iris texture, no colored iris ring, no dark circular center, no pupil, no vertical slit, no radial spokes, no concentric ring, no catchlight, no glossy highlight, and no reflected scene. Keep the center of each underlay close in brightness and color to its surrounding underlay; no recognizable eye symbol may remain.
Invariants: Preserve both eye shapes, eye corners, upper and lower eyelids, eyelashes, nose, muzzle, facial fur, markings, proportions, camera, lighting, focus, subject position, scale, and transparent surroundings aligned exactly to Image 2.
Avoid: no iris, pupil, vertical slit, black blob, dark center, radial eye pattern, ring, highlight, extra eye, changed expression, clipped eyelid, altered nose fur, text, watermark, outline, colored fringe, background, new object, pose change, crop change, or lighting change.
```

## Visual selection gate before project overwrite

Inspect each generated result at original resolution. One single-change correction iteration per asset is allowed if needed.

Reject the body result if the target region is blurrier or sharper than canonical, has long woolly curls, a rounded plug/cap, wrong marking direction, an abrupt seam, painted texture, or changes non-target anatomy.

Reject the eye result if either target contains any recognizable iris, pupil/slit, dark central blob, radial/concentric pattern, highlight, or clips eyelids/nose fur.

If either asset still fails after one correction iteration, return `BLOCKED` and do not overwrite project files.

## Deterministic project normalization

For selected outputs, use the user-authorized repository Pillow/NumPy fallback:

- resize only source RGB to `512 x 768` with Pillow LANCZOS;
- body Alpha = `masks/body-fill-mask.png`;
- eye Alpha = pixelwise max of `masks/eye-left-mask.png` and `masks/eye-right-mask.png`;
- clear RGB to zero wherever Alpha is zero;
- save RGBA PNG atomically.

Verify mode, size, exact 2:3, mask-alpha byte equality, alpha extrema `(0,255)`, transparent RGB count zero, and SHA-256.

## Provenance and scope

Update `assets/rig/v1/source/authoring.json` honestly:

- preserve the prior prompts and deterministic Alpha history;
- append this repair iteration's exact body and eye prompts;
- record built-in image generation as the visual source tool;
- record the selected built-in generated-image source paths;
- record the same deterministic Pillow/NumPy fixed-mask normalization;
- update both output SHA-256 values.

Append full generation paths, prompts, visual decisions, normalization commands/results, final hashes, and concerns to `.superpowers/sdd/organic-head/task-3-report.md`.

Only stage and commit:

- `assets/rig/v1/source/ai/body-fill-raw.png`
- `assets/rig/v1/source/ai/eye-fill-raw.png`
- `assets/rig/v1/source/authoring.json`

Do not stage the rejected archive, scratch briefs/reports/scripts, R4 layers, R5 files, plans/specs, old QA, runtime, or `交付/`.

Commit message: `fix: refine hidden rig source textures`

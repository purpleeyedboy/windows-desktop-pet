# Task 3 Report: Masked Rig Fill Sources

## Provenance

Per the preceding implementer's task handoff, both files below were generated with the built-in OpenAI `image_gen` image-editing capability. They are retained unchanged in this task; no PNG pixels were regenerated, overwritten, or edited.

| Source | Local path | PNG properties | SHA-256 |
| --- | --- | --- | --- |
| Body fill | `assets/rig/v1/source/ai/body-fill-raw.png` | 1023 x 1537, RGB | `83ea36a0196124148cf4e67bdcbc63ca82f6d35e247fc4fcccb59ba130db76df` |
| Eye fill | `assets/rig/v1/source/ai/eye-fill-raw.png` | 1023 x 1537, RGB | `c6f879c1f015df4b03f237da334b43ccca182e93aa6f6461ae66ff4604068e43` |

## Exact prompts

### Body fill

```text
Edit the supplied 2:3 cat image guide. Replace only the solid neon-green internal region with the anatomically plausible shoulder, upper chest, and torso fur that would exist behind the removed head and neck of this exact orange-and-white Devon Rex cat. Continue the same short curly fur texture, orange tabby markings, white chest, lighting direction, focus, and photographic detail. Do not add a head, face, eye, ear, collar, bell, leg, text, outline, colored fringe, or background. Preserve the canvas composition and transparent surroundings. The result is a hidden fill source; all non-green content should remain visually aligned with the reference.
```

### Eye fill

```text
Edit the supplied 2:3 cat image guide. Replace only the two solid neon-green iris regions with the natural eye-socket content behind movable irises for this exact cat: pale green-gray eye interior, subtle eyelid shadow, and the original short fur and lighting at each eye. Keep both eye shapes, eye corners, eyelids, face, nose, markings, proportions, camera, and transparent background aligned exactly. Do not add pupils, irises, extra highlights, extra eyes, text, outline, or colored fringe. This is a hidden underlay, not a new expression.
```

## Checks

- Both required output paths exist and decode as PNG at the recorded dimensions and RGB mode.
- `Get-FileHash -Algorithm SHA256` matches both values in `assets/rig/v1/source/authoring.json`.
- `authoring.json` records the exact prompts, tool `OpenAI image generation image edit`, guide/output paths, and the policy `discard all generated pixels outside fixed masks`.

## Concerns

- Provenance is recorded from the preceding implementer's handoff and `authoring.json`; the generated binary files themselves cannot independently attest to the invoking tool. Runtime mask clipping and visual quality remain Task 4 validation work.

## 2026-08-29 Alpha Repair Attempt — BLOCKED

The Important review finding was confirmed: both committed raw fill sources are `1023 x 1537`, mode `RGB`, and show a gray-and-white checkerboard baked into the pixels. The existing `body-fill-raw.png`, `eye-fill-raw.png`, `canonical-idle.png`, `body-fill-guide.png`, and `eye-fill-guide.png` were inspected at original resolution before repair. The guides' green regions remain internal to their intended subject regions, so Task 2 coordinates were not changed.

The built-in OpenAI `image_gen` image-editing capability was used. No CLI or direct image API was used.

### Body repair prompt — first attempt

```text
Use case: background-extraction
Asset type: hidden shoulder/neck fill source for a 2D desktop-pet rig
Input images: Image 1 is the edit target body-fill-raw.png; Image 2 is the canonical cat identity/alignment reference; Image 3 is the original body-fill guide and fixed-mask reference.
Primary request: Make exactly one technical correction to Image 1: remove the baked gray-and-white checkerboard background from the pixels and replace it with genuine alpha transparency. Output an actual transparent RGBA PNG on an exact 2:3 portrait canvas; use exactly 1024 x 1536 pixels if a concrete size is needed.
Invariants: Preserve the existing orange-and-white Devon Rex cat body, the generated hidden shoulder/upper-chest/torso fur behind the absent head and neck, subject location, scale, silhouette, texture, markings, focus, lighting, and alignment exactly. Keep the entire region outside the cat genuinely transparent. The hidden fill content in Image 1 must remain available and visually unchanged. Do not creatively regenerate or redesign the cat.
Constraints: change only the baked checkerboard and canvas dimensions; preserve transparent surroundings and exact composition. actual transparent RGBA PNG, no checkerboard pattern or simulated transparency. Exact aspect-ratio requirement: width * 3 == height * 2.
Avoid: no head, face, eye, ear, collar, bell, leg, text, watermark, outline, colored fringe, added shadow, background, checkerboard, new object, changed pose, changed crop, or changed lighting.
```

Generated candidate:

`C:\Users\rog\.codex\generated_images\01a04963-9b8e-79e0-8fbc-68cf9d544d17\exec-f9ba05b5-7c72-4632-b5c1-28223da0e828.png`

Validation result: `size=(1024, 1536)`, `mode=RGB`, `ratio_ok=True`, `alpha_extrema=None`, `alpha_zero=0`. Rejected before project overwrite.

### Body repair prompt — single correction iteration

```text
Use case: background-extraction
Asset type: hidden shoulder/neck fill source for a 2D desktop-pet rig
Input image: the immediately preceding failed correction output; it already has the required subject and exact 1024 x 1536 canvas.
Single correction only: The preceding output failed because it decoded as RGB and the gray-and-white checkerboard was still baked into the pixels. Erase the entire checkerboard/background outside the cat to alpha 0. Export an actual transparent RGBA PNG, no checkerboard pattern or simulated transparency.
Hard technical requirements: exactly 1024 x 1536 pixels; width * 3 == height * 2; PNG mode RGBA; alpha minimum 0; transparent outer corners and surrounding empty canvas.
Invariants: preserve every visible cat-body pixel, hidden shoulder/upper-chest/torso fur, subject position, scale, silhouette, texture, markings, focus, lighting, crop, and composition exactly. Change only the outside background to genuine alpha transparency.
Avoid: no checkerboard, white/gray matte, background, shadow, head, face, eye, ear, collar, bell, added leg, text, watermark, outline, colored fringe, new object, pose change, crop change, or lighting change.
```

Generated candidate:

`C:\Users\rog\.codex\generated_images\01a04963-9b8e-79e0-8fbc-68cf9d544d17\exec-6b39fc4c-a7a7-470b-98f6-20d25602e0f7.png`

Validation command:

```powershell
& 'C:\Users\rog\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -c "from PIL import Image; p=r'C:\Users\rog\.codex\generated_images\01a04963-9b8e-79e0-8fbc-68cf9d544d17\exec-6b39fc4c-a7a7-470b-98f6-20d25602e0f7.png'; im=Image.open(p); print('size=',im.size,'mode=',im.mode,'ratio_ok=',im.width*3==im.height*2); a=im.getchannel('A') if 'A' in im.getbands() else None; print('alpha_extrema=',a.getextrema() if a else None,'alpha_zero=',sum(1 for x in a.getdata() if x==0) if a else 0)"
```

Output:

```text
size= (1024, 1536) mode= RGB ratio_ok= True
alpha_extrema= None alpha_zero= 0
```

The single permitted correction iteration also failed the required RGBA/alpha gate. Per the task stop condition, processing stopped before the eye candidate, neither project PNG was replaced, `authoring.json` was not changed, and no fix commit was created. The original Task 3 commit remains intact.

## 2026-08-29 Deterministic Alpha Repair — COMPLETE

The user explicitly authorized the deterministic Pillow/NumPy fallback after the repeated built-in image-edit outputs baked a checkerboard into RGB pixels. No image generation, repainting, automatic cutout, or color-threshold segmentation was used. The committed AI files were treated only as RGB color sources; RGB was resized to the canonical `512 x 768` canvas with Pillow LANCZOS, and output alpha was supplied exclusively by the already-reviewed fixed masks. RGB was cleared to `(0, 0, 0)` everywhere output alpha is zero.

### RED check before writing

Command (run from the worktree):

```powershell
& '.\.venv\Scripts\python.exe' '.superpowers\sdd\organic-head\validate_task3_alpha.py'
```

Result (exit code `1`, expected):

```text
body: pass=False size=(1023, 1537) mode=RGB ratio_ok=False alpha_extrema=(255, 255) mask_equal=False transparent_rgb_nonblack=0 sha256=83ea36a0196124148cf4e67bdcbc63ca82f6d35e247fc4fcccb59ba130db76df
eye: pass=False size=(1023, 1537) mode=RGB ratio_ok=False alpha_extrema=(255, 255) mask_equal=False transparent_rgb_nonblack=0 sha256=c6f879c1f015df4b03f237da334b43ccca182e93aa6f6461ae66ff4604068e43
```

Both source files failed the required mode, canonical size, 2:3 ratio, fixed-mask alpha, alpha-extrema, and true-transparency gates.

### Deterministic implementation

The ignored one-off script `repair_task3_alpha.py` wrote each repaired PNG through a temporary sibling file followed by atomic replacement. It used:

- body alpha: `masks/body-fill-mask.png`
- eye alpha: pixelwise maximum of `masks/eye-left-mask.png` and `masks/eye-right-mask.png`
- RGB resampling: Pillow LANCZOS only

`authoring.json` retains the original prompts/tool record and adds the user authorization, reason, toolchain, original `1023 x 1537 RGB` input facts, mask sources, outside-mask and transparent-RGB policies, and updated SHA-256 values.

### GREEN check after writing

The identical command above returned exit code `0`:

```text
body: pass=True size=(512, 768) mode=RGBA ratio_ok=True alpha_extrema=(0, 255) mask_equal=True transparent_rgb_nonblack=0 sha256=34bca962ec505fae2a0d1a9d6ede5ad7ef70aa7b49ca7b89e1dcba268123db38
eye: pass=True size=(512, 768) mode=RGBA ratio_ok=True alpha_extrema=(0, 255) mask_equal=True transparent_rgb_nonblack=0 sha256=e581967924a6bc7549cab70be36f5d4bf0a2d80a3c83070e3e2b22ae12743482
```

This verifies both outputs are exact `512 x 768` RGBA 2:3 PNGs, alpha extrema are `(0, 255)`, each output alpha equals its fixed expected mask byte-for-byte, and every fully transparent pixel has RGB `(0, 0, 0)`.

### Visual inspection

Both repaired PNGs were inspected at original `512 x 768` resolution. The body image contains only the intended hidden shoulder/upper-chest fur patch; the eye image contains only the two intended eye-socket patches. The nonzero-alpha regions contain plausible source fur/eye-socket content and no visible checkerboard pixels. Their small isolated appearance on true transparency is expected for fixed-mask fill sources.

### Commit

The approved three-file change was committed as `3fe889a fix: apply deterministic alpha to rig fill sources`. Post-commit verification reran the same GREEN check and confirmed both `authoring.json` SHA-256 fields still match their respective repaired files.

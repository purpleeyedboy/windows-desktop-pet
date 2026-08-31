# Continuous Head-Neck Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic visual proof that the existing cat can follow a continuous arbitrary-angle target by smoothly deforming one head-and-upper-neck image region, while the approved eyes lead and the head follows, without directional sprites, head cutout translation, or professional rigging software.

**Architecture:** Wrap the approved `NeutralEyeCompositor` with one Pillow-only continuous inverse mesh over a locked rectangular head/neck ROI. The ROI perimeter and chest remain pinned, so every output pixel is sampled from the same eye-composed source frame and the rejected hidden shoulder fill is never exposed. A separate offline preview builder simulates one continuous gaze target, renders normal and slow motion evidence, and publishes only QA artifacts; runtime wiring and EXE packaging remain gated on user visual approval.

**Tech Stack:** Python 3.11+, Pillow 11, pytest 8, standard-library JSON/hash/path utilities. No NumPy, OpenCV, Live2D, Inochi2D, GPU runtime, or GUI authoring tool.

## Global Constraints

- Use only the approved `512×768 RGBA` canonical cat, SHA-256 `48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7`, and the accepted `eye-neutral-v1` compositor.
- Do not create, select, interpolate, crossfade, or package center/left/right/up/down or any finite direction raster assets.
- Do not cut out the head and translate or rotate it as one rigid object.
- Deform only one continuous rectangular ROI `[x=0, y=160, width=320, height=432]`; pixels outside that ROI and pixels outside the fixed dynamic-support polygon must remain decoded-RGBA identical to the eye-composed source frame.
- Use a non-uniform `24×18` cell mesh with `25×19` vertices. Canvas-space X coordinates are `[0,24,36,48,60,72,82,93,108,118,128,139,151,163,176,184,194,205,218,230,242,249,256,264,320]`; Y coordinates are `[160,186,202,223,250,275,300,320,335,351,370,397,425,454,485,520,555,565,592]`. Mesh bboxes are ROI-local integer rectangles; Pillow source quads use upper-left, lower-left, lower-right, upper-right order. ROI geometry is half-open: source quad edges may equal local width `320` or height `432`, while pixel indexing must stay strictly below those limits; canvas Y is converted to ROI-local Y by subtracting `160` exactly once.
- The ROI perimeter, every vertex with `x >= 264`, and every vertex with `y >= 555` are pinned. The protected right-body strip `x=264..319` and lower chest band `y=555..591` must therefore remain decoded-RGBA identical to the eye-only input. The initial single-image envelope is conservative: nose travel no more than `±4` source pixels horizontally and `±3` vertically; skull/eye-region travel no more than `±3` horizontally and `±2` vertically.
- The historical dynamic head-neck support polygon is `[(24,202),(246,202),(263,370),(242,455),(221,564),(105,564),(80,470),(32,430)]`. Vertex displacement is zero on/outside that polygon and rises with a smoothstep over the first 20 pixels inside it; the 20px ramp is required to keep the narrow right-boundary mesh cells inside the fixed `0.80..1.20` area-ratio gate. The large visible shoulder/body region to the polygon's right is not treated as head.
- Fixed semantic points are: ear tips `(36,223)` and `(223,213)`; ear roots `(87,310)` and `(194,312)`; eye anchors `(82,351)` and `(163,347)`; nose `(118,397)`; jaw `(122,451)`; neck roots `(96,454)` and `(205,454)`; mid-neck `(108,515)` and `(207,515)`; chest anchors `(139,555)` and `(207,555)`. All coordinates are canvas-space source pixels. Horizontal-pose gates measure `abs(dx)`; vertical-pose gates measure `abs(dy)`; area/continuity gates use Euclidean magnitude where explicitly named.
- `HeadPose.x > 0` means the rendered cat turns toward screen-right; `HeadPose.y > 0` means screen-down. Because `mesh_for()` is an inverse source sampler, its semantic sampling offsets must have the opposite sign. Synthetic forward-render landmark tests must prove the rendered feature centroid moves with the pose sign rather than merely checking absolute inverse offsets.
- Use a continuous inverse field at arbitrary floating-point `head_x/head_y` values inside the unit disk. No sector names, angle rounding, nearest-state selection, hysteresis, or pose table lookup.
- Compose the accepted eye motion first, then deform the complete eye-composed ROI so eyes, eyelids, face, ears, whiskers, collar, and upper neck remain attached. Pillow MESH does not preserve bytes even for identity quads, so after resampling, restore source pixels wherever the geometric dynamic-support mask is false, wherever `x >= 264`, and wherever `y >= 555`. This writeback mask is derived only from fixed geometry, never from image Alpha.
- Preserve the accepted eye envelope of horizontal `±3.0` and vertical `±2.0` source pixels.
- The preview gaze model uses one normalized target, eye-focus time constant `0.060s`, head time constant `0.220s`, and eye/head compensation `0.35`. Clamp both continuous states to the unit disk.
- Exact all-zero head pose must bypass head resampling. Exact all-zero gaze must decode exactly to the approved center image. For the final 12 preview frames, reset target, focus, head, residual, and rendered values to exact zero rather than waiting for an exponential filter to reach zero.
- Premultiplied-alpha resampling is mandatory. Transparent output pixels must have zero RGB. No black, magenta, purple, or colored fringe is allowed on light, dark, gray, or checker backgrounds.
- Do not modify `assets/keyframes`, existing eye runtime assets, stable build files, current candidate workflow, current EXE, action animation behavior, blink, tilt, ear physics, whisker physics, body/leg/tail motion, or GitHub release state.
- Write preview evidence only under `qa/head-neck-continuous-v1/`. Do not write under any runtime asset directory, and do not package QA evidence.
- This plan stops at the head-follow visual gate. Runtime cursor integration, action lifecycle migration, Windows performance work, candidate naming, packaging, and EXE delivery require a later approved plan.
- The local writing-plans Skill is truncated after its interface template. Follow its available file-boundary, TDD, small-task, frequent-commit, and explicit-interface guidance; record this reduced guidance honestly.

---

### Task 1: Continuous Head-Neck Warp Core

**Files:**
- Create: `src/desktop_pet/head_neck_deformation.py`
- Create: `tests/test_head_neck_deformation.py`
- Create: `.superpowers/sdd/head-neck-continuous-task-1-report.md`

**Interfaces:**
- Consumes: an injected compositor exposing `source_size`, `eye_midpoint`, and `compose(eye_x: float, eye_y: float) -> Image.Image`.
- Produces: immutable `HeadPose(x: float, y: float)` and `ContinuousHeadNeckCompositor(base_compositor)` with `source_size`, `eye_midpoint`, `head_roi`, `mesh_for(pose: HeadPose) -> tuple[tuple[tuple[int,int,int,int], tuple[float,...]], ...]`, `sampling_offset_at(point: tuple[float,float], pose: HeadPose) -> tuple[float,float]`, and `compose(eye_x: float, eye_y: float, pose: HeadPose) -> Image.Image`.
- Later task dependence: Task 2 imports only these public interfaces and does not duplicate mesh math.

- [x] Write failing tests before the production module exists.
- [x] Prove RED by running `python -m pytest -q tests/test_head_neck_deformation.py` and recording the missing-module or missing-interface failures.
- [x] Validate the two eye inputs and both `HeadPose` fields as finite real numbers; reject booleans and head poses outside the unit disk instead of silently selecting or rounding a direction.
- [x] Implement the exact fixed `24×18`-cell, `25×19`-vertex inverse Pillow mesh over the locked ROI. Generate per-vertex source sampling offsets from smooth face, skull, ear, jaw, upper-neck, mid-neck, chest, protected-body, and boundary weights; keep the perimeter, `x >= 264` right-body strip, and `y >= 555` lower band exactly pinned.
- [x] Use distinct continuous horizontal and vertical fields so nose, skull, cheeks, ears, jaw, and neck do not move as one rigid block. Keep the conservative amplitude limits from Global Constraints.
- [x] At unit horizontal pose, require inverse `dx < 0` and `abs(dx)` of `3.0..4.0px` at nose, `2.0..3.0px` at both eye anchors, `1.5..3.0px` at both visible ear tips and both ear roots, and `0.8..2.2px` at both neck roots. Each ear tip/root pair must move with the same sign and differ by at most `1.0px`. Require nose `abs(dx)` to exceed average neck-root `abs(dx)` by at least `1.0px`. At unit vertical pose, require inverse nose `dy < 0` with `abs(dy)` of `2.0..3.0px`. Both chest-anchor offsets, the protected body strip, and the lower band are exactly zero.
- [x] Reject any non-finite mesh coordinate, source coordinate outside the ROI, non-convex or orientation-flipped quad, or quad whose source/output area ratio falls outside `0.80..1.20`.
- [x] Transform premultiplied-alpha ROI pixels with `Image.Transform.MESH` and bicubic resampling, convert back to valid straight RGBA, normalize resampling-only near-opaque Alpha `252..254` to `255` without changing straight RGB, clear RGB wherever Alpha is zero, then replace the ROI. Before replacement, byte-copy the eye-only source for every pixel outside the fixed dynamic-support polygon and for the protected `x >= 264` / `y >= 555` strips; use a fixed geometric writeback mask, never an image-Alpha paste mask. The near-opaque normalization applies only to the warped candidate before static writeback, so protected source bytes and exact-center bypass remain unchanged.
- [x] Bypass the head transform whenever `head_x == 0.0 and head_y == 0.0`; the eye-only output must be byte-identical to the injected compositor output.
- [x] Prove the head warp is actually rendered: `compose(0,0,HeadPose(1,0))` and `compose(0,0,HeadPose(0,1))` must each differ from the matching eye-only source at at least `500` decoded ROI pixels, differ at zero pixels outside the ROI, outside the dynamic support, or inside either protected strip, and be byte-identical to an independent premultiplied-MESH-plus-geometric-writeback oracle built from the returned `mesh_for()` value.
- [x] Test exact center identity, eye-only identity, arbitrary fractional continuity, axis crossing, diagonal poses, unit-disk rejection, finite coefficients, no inverted source quads, half-open ROI/local coordinate conversion, signed inverse offsets plus signed forward-render centroid motion, pinned ROI edges, protected right-body/lower-chest identity, decoded identity outside both ROI and dynamic support, transparent-RGB clearing, and semitransparent-pixel count ratio `0.80..1.25` relative to the same eye-only source.
- [x] Add synthetic Alpha-edge coverage proving premultiplied resampling does not create the straight-alpha dark fringe failure.
- [x] Scan production imports to prove no `numpy`, `cv2`, OpenCV, direction-sprite loader, or external editor dependency was introduced.
- [x] Run the focused tests, existing neutral-eye compositor tests, applicable non-Tk regressions, `python -m py_compile`, and `git diff --check`.
- [x] Write the Task 1 report with RED/GREEN commands, timings, scope confirmation, and remaining visual risks.
- [x] Commit Task 1 as one independently reversible implementation commit and one report-only follow-up only if the report needs the implementation commit SHA.

### Task 2: Coordinated Continuous Preview and QA Publisher

**Files:**
- Create: `tools/build_head_neck_continuous_preview.py`
- Create: `tests/test_head_neck_continuous_preview.py`
- Create: `qa/head-neck-continuous-v1/head-neck-follow.gif`
- Create: `qa/head-neck-continuous-v1/head-neck-follow-4x.gif`
- Create: `qa/head-neck-continuous-v1/landmark-overlay.gif`
- Create: `qa/head-neck-continuous-v1/contact-sheet-light.png`
- Create: `qa/head-neck-continuous-v1/contact-sheet-dark.png`
- Create: `qa/head-neck-continuous-v1/contact-sheet-gray.png`
- Create: `qa/head-neck-continuous-v1/contact-sheet-checker.png`
- Create: `qa/head-neck-continuous-v1/seam-closeups-400pct.png`
- Create: `qa/head-neck-continuous-v1/center-difference.png`
- Create: `qa/head-neck-continuous-v1/stats.json`
- Create: `.superpowers/sdd/head-neck-continuous-task-2-report.md`

**Interfaces:**
- Consumes: Task 1 `ContinuousHeadNeckCompositor`, approved `NeutralEyeCompositor`, fixed canonical and eye source roots.
- Produces: immutable `PreviewPose(index, target_x, target_y, focus_x, focus_y, head_x, head_y, eye_x, eye_y)`, `coordinated_preview_poses() -> tuple[PreviewPose, ...]`, `build_preview(eye_asset_dir: Path, canonical_path: Path, output_dir: Path) -> dict[str, object]`, and the exact allow-listed QA artifact set above.
- Human gate: the user approves or rejects these artifacts before any runtime or EXE task begins.

- [x] Write failing preview-path, deterministic-output, safety, and rollback tests before creating the builder.
- [x] Prove RED with `python -m pytest -q tests/test_head_neck_continuous_preview.py`.
- [x] Generate one uniquely defined 240-frame, `dt=1/30s` timeline. Define `smoothstep(u)=u*u*(3-2*u)`. Frames `0..11` target `(0,0)`. For frames `12..29`, with `j=0..17` and `u=(j+1)/18`, target is `(0.85*smoothstep(u),0)`. For frames `30..149`, with `k=0..119` and `theta=2*pi*k/120`, target is `(0.85*cos(theta),0.85*sin(theta))`; positive screen Y points downward, so increasing theta is visually clockwise. Let `last_orbit` be frame 149 target. For frames `150..167`, with `j=0..17` and `u=(j+1)/18`, target is `last_orbit*(1-smoothstep(u))`. Frames `168..227` target `(0,0)`. Frames `228..239` force target, all states, residual, and rendered values to exact zero.
- [x] Simulate exactly one target per frame. For each non-forced frame, update focus and head with `alpha = 1 - exp(-dt/tau)` using `tau_focus=0.060s` and `tau_head=0.220s`; radial-clamp each state; compute `residual = focus - 0.35*head`; radial-clamp residual before mapping to eye source pixels `eye_x=3.0*residual_x`, `eye_y=2.0*residual_y`.
- [x] Define the step oracle as 30 post-update frames starting from exact zero with constant target `(1,0)`. The focus must be strictly ahead of the head until both settle; the first zero-based frame reaching `x >= 0.9` must be at most `4` for focus and at least `15` for head, with focus at least 10 frames earlier. Across the preview, successive target distance must be at most `0.075`, successive head-state distance at most `0.055`, and axis/orbit-wrap steps obey the same bounds. At frame 227, the maximum Euclidean magnitude among focus, head, and residual must be at most `0.0001`; frames `228..239` are exact center.
- [x] Encode normal and four-times-slow GIFs from the same source frames on matte RGB `(32,32,36)`. The normal frame durations repeat `(30,30,40)ms` for exactly `8000ms`; slow durations repeat `(120,120,160)ms` for exactly `32000ms`. Quantize using one fixed WEB palette with dither disabled, optimization disabled, loop zero, and disposal method 2. The slow preview changes timing only; it must not rerun the simulation. Decode both GIFs and compare their 10ms-tick frame schedule against the fixed-palette source timeline. Encode and decode-verify `landmark-overlay.gif` with the same normal timing, matte, palette, dither, loop, optimization, and disposal contract.
- [x] Render the landmark overlay from the same frames and fixed semantic points. Contact sheets use a fixed `3×3` grid of frames `0,30,45,60,75,90,105,120,135`, corresponding to center plus eight 45-degree orbit samples. These are QA images only and must never be consumed by production code.
- [x] Produce light, dark, gray, and checker contact sheets plus 400-percent eye-rim, ear-root, whisker, jaw, neck, collar, and chest closeups.
- [x] Produce an exact center difference image and stats containing input hashes, output hashes excluding `stats.json` itself, ROI, exact vertex grids, constants, pose extrema, semantic displacement minima/maxima, step response, mesh orientation/area bounds, outside-ROI/protected-strip identity, transparent-RGB counts, enclosed-transparent-hole counts, Alpha-support deltas, head-only pixel differences against matching eye-only frames, eye-crop edge-energy ratios, and a statement that runtime assets were unchanged. Define transparency strictly as `Alpha == 0`. Record both 4-connected and 8-connected components after flood-filling transparency connected to the ROI perimeter. The 4-connected canonical telemetry baseline is 119 enclosed components, 357 enclosed pixels, largest 21; the 8-connected canonical telemetry baseline is 15 components, 37 pixels, largest 6. Neither raw count is a direct visual gate because subpixel antialiasing can close a one-pixel/diagonal exterior channel without creating a visible hole. Define a significant blocking hole as an 8-connected enclosed transparent component of area at least 16 source pixels; canonical has zero, and every frame must have zero. The 16-pixel threshold is an empirical quantization guard: all current strict-Alpha maxima are at most 11 pixels, and independent light/dark/gray/checker 400-percent sequences show no enclosed background island or flash. Do not modify RGBA merely to satisfy topology metrics: the rejected NEAREST exterior-mask experiment cut 420 valid antialiased pixels and still failed the 4-connected metric. Use a synthetic premultiplied-edge oracle for the automated dark-fringe gate; treat legitimate pupil/collar dark pixels separately and expose light/dark/gray/checker sheets for the final human fringe gate.
- [x] Require visible non-rigid motion so a zero-warp implementation cannot pass: use the Task 1 semantic displacement minima and nose-minus-neck differential; at horizontal and vertical extrema, compare each rendered frame with an eye-only frame using exactly the same `eye_x/eye_y` and require at least `500` changed decoded ROI pixels attributable to the head, while pixels outside the dynamic support and inside the protected strips remain exact. Require zero decoded changes outside the ROI, outside the dynamic support, or inside the protected strips; zero transparent-RGB violations; Alpha-positive support count ratio `0.97..1.03`; semitransparent count ratio `0.80..1.25`; zero significant blocking holes of at least 16 source pixels under 8-connectivity; exact center identity; and fixed eye-crop Pillow `FIND_EDGES` energy ratio `0.80..1.15` versus the same eye-only frame at audit extrema. Record all 4-connected and 8-connected hole metrics as diagnostics. Record total rendered eye-anchor travel and require it not exceed `6.0px` horizontally or `4.0px` vertically before human review.
- [x] Snapshot and hash every required input byte once before decoding. Stage all artifacts in a destination-local temporary directory, validate the complete allowlist, then install transactionally with individual atomic renames: rename the existing destination to a backup, rename the staged directory into place, and remove the backup. This is intentionally not described as an atomic replacement of a non-empty directory; a brief destination gap is allowed. Reject output/input overlap after non-strict resolution. At initial validation, reject an output path that is a symlink or has any existing symlink ancestor, reject symlinked/non-regular canonical or required eye inputs, and reject an existing output that is not a regular directory. This is a static preflight contract, not a claim of cross-platform TOCTOU resistance. On injected installation failure restore the previous complete output, and preserve one recoverable backup if restoration also fails.
- [x] Build twice and require byte-identical outputs. Verify inputs are unchanged before and after both builds.
- [x] Test that no files are written under `assets/rig/v1/runtime`, no directional runtime PNGs are created, and the output contains only the allow-listed QA files.
- [x] Run Task 1 and Task 2 focused tests, existing eye preview/compositor tests, applicable non-Tk regressions, `python -m py_compile`, and `git diff --check`.
- [x] Write the Task 2 report with build timings, exact metrics, generated artifact hashes including the separately computed `stats.json` hash, scope confirmation, and the remaining human visual decision.
- [x] Commit Task 2 as one independently reversible implementation/evidence commit and one report-only follow-up only if required.

## Required Reviews and Stop Gate

- After each task, generate a review package from the recorded task base through task head and dispatch a fresh task reviewer for both specification compliance and code quality.
- Fix every Critical and Important finding with a separate fresh fixer, rerun the covering tests, and return the same reviewer for closure.
- After both tasks, dispatch a fresh broad reviewer over the whole branch. Record unresolved Minor findings in `.superpowers/sdd/progress.md`.
- Show the user the normal preview, slow preview, four background sheets, and seam closeups.
- Keep head-follow runtime integration and EXE work blocked until the user confirms: motion is visibly continuous and non-rigid; eyes lead naturally; head/neck motion is large enough but not rubbery; chest and body stay planted; no holes, black seams, double edges, fringe, whisker breaks, or collar/bell floating appear; final center is exact.

## Decision Receipt

- Decision: use one continuous full-ROI inverse mesh over the existing eye-composed canonical frame.
- Key assumption: a conservative single-image deformation envelope is sufficient; this does not claim true large-angle yaw or reveal unseen anatomy.
- Deliberately not built: directional sprites, head cutout translation, rejected hidden-shoulder fill, new generated art, Live2D, runtime timer migration, click-action warping, packaging, installer, signing, release.
- Evidence required: deterministic automated gates, independent task and branch review, and explicit user visual approval of the generated motion evidence.

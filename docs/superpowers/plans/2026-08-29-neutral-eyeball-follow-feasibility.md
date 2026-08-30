# Neutral Eyeball Follow Feasibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that the cat can look left, right, up, and down without moving the eyelids or eye rims and without exposing black holes, black seams, or duplicated eye edges.

**Architecture:** Keep the canonical face, eyelids, eye corners, and dark eye rims fixed. Build a neutral diffuse eyeball surface with no iris, pupil, slit, ring, or highlight beneath each aperture, then deform the original iris, pupil, and corneal highlight together with one premultiplied-alpha aperture-relative warp. The displacement reaches its requested value at each eye's movement anchor and falls smoothly to zero at the stationary aperture boundary, so no translated cutout edge or trailing underlay crescent is exposed. This increment is offline-only and cannot unblock R5 until its static visual evidence is explicitly accepted.

**Tech Stack:** Python 3.11+, Pillow, NumPy, OpenCV limited to offline authoring and validation, pytest, built-in image generation used only for the neutral-eye candidate input.

## Global Constraints

- The immutable canonical source is `assets/rig/v1/source/canonical-idle.png`, RGBA, `512×768`, SHA-256 `48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7`.
- Generated content may contribute only inside the two stationary eye-interior masks. Every pixel outside their union must remain byte-identical to the canonical source.
- Eyelids, eye corners, dark eye rims, surrounding face fur, head, body, pose, canvas, and alpha silhouette remain fixed.
- The neutral underlay contains diffuse globe color and curvature only: no iris, pupil, vertical slit, ring, focal highlight, residual green iris structure, dark hole, flat colored oval, or four-petal gradient.
- Each moving eye surface keeps its original iris, pupil, and corneal highlight together. The pupil must never translate independently from the iris and highlight.
- Motion is clipped by a stationary eye-interior aperture and uses premultiplied-alpha resampling with an aperture-relative displacement field. Displacement is maximal at each eye's movement anchor and exactly zero at the aperture boundary. Initial anchor-displacement limits are horizontal `±1.5` source pixels and vertical `±1.0` source pixels.
- The zero pose must be produced by the real layer-composition path and must decode exactly to the canonical source: `changed_pixels=0` and `maximum_channel_delta=0`.
- Static evidence must include full-cat center/left/right/up/down poses and magnified eye close-ups. It fails on any black arc, black gap, duplicated rim, sticker-like crescent, static highlight remnant, or eye-surface seam.
- R5 remains blocked. Do not begin five-direction head assets, blink, tilt, runtime integration, packaging, or EXE work in this plan.
- Do not create a dynamic GIF until the static layer contact sheet passes the visual gate.

---

### Task 1: Neutral Eye Layers and Static Direction Proof

**Files:**
- Create: `assets/rig/v1/source/ai/neutral-eyeball-generated-v1.png`
- Create: `assets/rig/v1/source/eye-neutral-v1/underlay.png`
- Create: `assets/rig/v1/source/eye-neutral-v1/eye-left.png`
- Create: `assets/rig/v1/source/eye-neutral-v1/eye-right.png`
- Create: `assets/rig/v1/source/eye-neutral-v1/eye-left-mask.png`
- Create: `assets/rig/v1/source/eye-neutral-v1/eye-right-mask.png`
- Create: `assets/rig/v1/source/eye-neutral-v1/authoring.json`
- Create: `tools/build_neutral_eye_layers.py`
- Create: `tests/test_neutral_eye_layers.py`
- Create: `qa/neutral-eye-v1/candidate/center.png`
- Create: `qa/neutral-eye-v1/candidate/left.png`
- Create: `qa/neutral-eye-v1/candidate/right.png`
- Create: `qa/neutral-eye-v1/candidate/up.png`
- Create: `qa/neutral-eye-v1/candidate/down.png`
- Create: `qa/neutral-eye-v1/candidate/layer-contact-sheet.png`
- Create: `qa/neutral-eye-v1/candidate/stats.json`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: `assets/rig/v1/source/canonical-idle.png` and the generated neutral-eye candidate.
- Produces: `build_assets(canonical_path: Path, neutral_candidate_path: Path, output_dir: Path) -> dict`, `compose_pose(asset_dir: Path, eye_x: float, eye_y: float) -> Image.Image`, and `build_contact_sheet(asset_dir: Path, qa_dir: Path) -> dict`.
- Produces immutable authored assets with their mode, size, bounds, source hash, and output SHA-256 values recorded in `authoring.json`.

**Acceptance Criteria:**
- The generated candidate is treated only as a source of eye-interior neutral texture; no whole-image generated pixel survives outside the two eye-interior masks.
- Eye-interior masks exclude eyelids, corners, dark rims, tear-line reflections, and face fur. They are tighter than the rejected `45×56` and `46×57` masks and have soft antialiased boundaries fully inside the fixed dark rim.
- `underlay.png` is a full-canvas RGBA canonical derivative whose only changed pixels are within the two masks and whose alpha channel is identical to canonical.
- `eye-left.png` and `eye-right.png` contain only their masked original eye surfaces on transparent backgrounds; transparent RGB is zero.
- Center composition uses the same compositor as moving poses and is pixel-exact canonical.
- Extreme poses keep anchor displacement within `±1.5` horizontal and `±1.0` vertical source pixels; both eyes use the same normalized target while retaining their own pixel anchors and aperture-relative falloff.
- The displacement field is zero at every aperture-boundary pixel, and extreme poses expose no trailing underlay crescent.
- New near-black pixels belonging to a pupil may move inside the aperture, but no new near-black pixels may appear in a boundary ring around either aperture.
- The contact sheet visually proves a fixed rim and eyelid with natural globe curvature behind the moving eye surface.

**Steps:**

- [ ] Use the built-in image editor on the canonical source to create one versioned neutral-eye candidate. Change only the interior of both eyes by removing the green iris structure, vertical pupil, and focal corneal highlights; preserve the fixed eyelids, corners, rims, surrounding fur, pose, canvas, and transparency.
- [ ] Inspect the generated candidate at full-cat scale and magnified eye scale. Reject it before coding if it contains dark holes, remaining pupil or iris features, flat ovals, symmetric petal gradients, or changed rims.
- [ ] Copy the accepted generated input to `assets/rig/v1/source/ai/neutral-eyeball-generated-v1.png` without overwriting prior source files.
- [ ] Write `tests/test_neutral_eye_layers.py` first. Cover canonical hash enforcement, exact zero-pose recomposition, outside-mask byte identity, canonical alpha preservation, mask containment inside fixed eye interiors, zero transparent RGB, bounded offsets, shared eye target, fixed boundary-ring darkness, deterministic hashes, and required evidence files.
- [ ] Run `python -m pytest tests/test_neutral_eye_layers.py -q` and record the expected RED failure caused by the missing builder module or missing public functions.
- [ ] Implement the smallest `tools/build_neutral_eye_layers.py` that satisfies the tests. Use explicit reviewed eye-interior geometry, generated neutral pixels only within the masks, and a premultiplied-alpha aperture-relative warp whose displacement is maximal at the movement anchor and falls smoothly to zero at the stationary aperture boundary. The iris, pupil, and highlight share the same field.
- [ ] Run `python -m pytest tests/test_neutral_eye_layers.py -q` until GREEN, then run it a second time to prove deterministic output hashes.
- [ ] Generate center, four extreme poses, statistics, and a contact sheet containing full-cat poses plus magnified eye close-ups. Do not generate a GIF.
- [ ] Inspect `layer-contact-sheet.png` at normal size and the eye close-ups at high magnification. If any seam or horror-film black gap appears, keep Task 1 blocked and archive the evidence as rejected rather than tuning around the test.
- [ ] Commit the generated input, tests, builder, authored layers, and QA evidence. Run independent task review using the task brief, implementation report, and full diff package.
- [ ] If the reviewer is clean and the visual evidence passes, append the commit range and review status to `.superpowers/sdd/progress.md`; otherwise record Task 1 as blocked without changing R5.

### Task 2: Deterministic Continuous Eye-Follow Preview

**Dependency:** Task 1 static evidence has explicit visual approval.

**Outcome:** Produce an offline-only deterministic preview that maps a scripted target path to both eyes with a `60ms` exponential time constant at `30Hz`, respects the Task 1 movement bounds and stationary apertures, returns exactly to center, and emits timing/containment statistics plus a reviewable GIF. This task still does not authorize head movement, blink, tilt, runtime integration, packaging, or EXE work.

**Files:**
- Create: `tools/build_neutral_eye_preview.py`
- Create: `tests/test_neutral_eye_preview.py`
- Create: `qa/neutral-eye-v1/preview-v1/eye-follow.gif`
- Create: `qa/neutral-eye-v1/preview-v1/stats.json`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: `tools.build_neutral_eye_layers.compose_pose(asset_dir: Path, eye_x: float, eye_y: float) -> Image.Image`, Task 1 `authoring.json`, both stationary eye masks, and the immutable canonical source.
- Produces: `target_for_frame(frame_index: int) -> tuple[float, float]`, `preview_offsets() -> tuple[tuple[float, float], ...]`, and `build_preview(asset_dir: Path, canonical_path: Path, output_dir: Path) -> dict`.
- The CLI accepts `--asset-dir`, `--canonical`, and `--output-dir`; validation failure raises an error and exits non-zero rather than writing a misleading passing report.

**Deterministic Trajectory Contract:**
- Simulate exactly `90` source frames at `30Hz` with fixed `dt=1/30` seconds and exponential gain `alpha = 1 - exp(-dt / 0.060)`.
- Requested targets are frame-indexed and piecewise constant: frames `0..5` center, `6..20` left `(-1.5, 0.0)`, `21..35` right `(1.5, 0.0)`, `36..50` up `(0.0, -1.0)`, `51..65` down `(0.0, 1.0)`, and `66..89` center.
- Apply the same smoothed `(eye_x, eye_y)` to both eyes through the existing Task 1 compositor. Do not add per-eye offsets, independent pupil motion, easing libraries, or runtime cursor input.
- Start from state `(0.0, 0.0)`. For frames `0..83`, update each axis once as `state = state + alpha * (target - state)` and render that updated state. Frame `83` must be within `5e-5` of center on each axis; frame `84` bypasses the recurrence and assigns exact `(0.0, 0.0)`, then frames `85..89` hold exact center. All six final source frames must be pixel-exact canonical.
- GIF source timing uses the repeating centisecond-compatible duration pattern `(30, 30, 40)` milliseconds, whose total is exactly `3000ms` for the `90` simulated frames. The encoder may coalesce only adjacent palette-identical frames. Validation converts the 90 matte frames through the specified fixed web palette first, expands that encoded RGB schedule and the decoded GIF schedule onto `10ms` ticks, and requires pixel-identical RGB at every tick, decoded total duration `3000ms`, and infinite loop metadata `loop=0`. It does not require the lossy GIF to equal the unquantized matte RGB.
- Composite source RGBA frames onto a fixed dark RGB matte `(31, 33, 36)` only for GIF encoding. Convert every matte frame with the same Pillow fixed web palette, `dither=Image.Dither.NONE`; save with `optimize=False` and `disposal=2`. All containment and canonical-exact checks operate on the unflattened full-resolution RGBA source frames.

**Acceptance Criteria:**
- The step response uses the exact `60ms` exponential formula; no frame-dependent hand tuning or overshoot is permitted.
- Every requested and smoothed offset remains inside horizontal `±1.5` and vertical `±1.0` source pixels.
- Before rendering, fail closed unless canonical SHA-256 equals `48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7`, `authoring.json` records that same canonical hash and motion limits, and its output hashes/modes/sizes match the actual underlay, two surfaces, and two masks. Required modes and sizes are full-canvas `512×768`: underlay/surfaces `RGBA`, masks `L`.
- Define each stationary aperture support as mask value `>0`, union the two binary supports, and define each tested outer boundary ring exactly as `MaxFilter(7)(support) - support`. For all `90` RGBA source frames, every RGBA byte outside the support union is canonical-exact, the full alpha channel is canonical-exact, and no ring pixel becomes near-black when canonical was not, where near-black means `max(R,G,B) <= 24`.
- The final six RGBA frames are pixel-exact canonical with `changed_pixels=0` and `maximum_channel_delta=0`.
- `stats.json` records the constants, requested target and smoothed offset for every source frame, all `90` source durations, decoded GIF durations/count/loop, observed maxima, containment maxima, final-center metrics, the GIF SHA-256, `authoring.json` SHA-256, and every actual immutable input hash. It must not attempt to contain its own self-referential file hash.
- Two builds in separate temporary directories produce byte-identical `eye-follow.gif` and `stats.json` under the same execution environment.
- The committed GIF and statistics are byte-identical to a fresh build. Visual review fails on any black arc, black gap, duplicated rim, static underlay crescent, asynchronous eye motion, abrupt final snap, or visible palette flicker.
- Build and validate both files inside a unique staging sibling under `output_dir.parent`, so publication renames stay on one filesystem. If no prior output directory exists, rename the complete staging directory directly into place. Otherwise rename the existing output directory to a unique sibling backup, rename staging into place, and restore the backup if that second rename fails. An injected between-rename failure must leave the original output directory byte-identical; a successful publish must leave no staging or backup directory.
- R5 remains blocked regardless of this task result.

**Steps:**

- [ ] Write `tests/test_neutral_eye_preview.py` first for the exact `90`-frame target schedule and recurrence/snap order, shared offsets, motion bounds, input hash/mode/size rejection, exact final six frames, precisely defined all-frame containment/rings, source-versus-decoded `10ms` GIF timeline equivalence, fixed palette settings, required statistics, deterministic double build, committed-output reproducibility, and transactional rollback under an injected between-rename failure.
- [ ] Run `python -m pytest tests/test_neutral_eye_preview.py -q` and capture the expected RED failure caused by the missing preview module.
- [ ] Implement the smallest `tools/build_neutral_eye_preview.py` using only Python, Pillow, and the existing Task 1 compositor; add no dependency and modify no runtime module.
- [ ] Make validation fail closed before publication. Stage and validate the complete directory, then use the specified backup-and-rename transaction with rollback rather than independent per-file replacement.
- [ ] Run the focused preview tests until GREEN, then run `python -m pytest -q` once for regression coverage.
- [ ] Generate `qa/neutral-eye-v1/preview-v1/eye-follow.gif` and `stats.json`, then rebuild in a temporary directory and compare both files byte-for-byte.
- [ ] Inspect the GIF at normal size and magnified eye scale. Keep N2 blocked if there is any seam, palette flicker, asynchronous eye motion, or visible final snap.
- [ ] Commit code, tests, GIF, statistics, and the progress update. Generate the SDD review package and obtain independent spec-compliance and code-quality approval before marking N2 complete.

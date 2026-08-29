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

**Outcome:** Produce an offline-only deterministic preview that maps a scripted target path to both eyes with a `60ms` exponential time constant at `30Hz`, respects the Task 1 movement bounds and stationary apertures, returns exactly to center, and emits timing/containment statistics plus a reviewable GIF. Before implementation, expand this task into TDD-sized steps and exact file paths. This task still does not authorize head movement, blink, tilt, runtime integration, packaging, or EXE work.

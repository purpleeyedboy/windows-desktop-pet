# Runtime Eye-Follow Visible Source Probe Implementation Plan

> Required workflow: use the repository subagent-driven-development skill task by task, with test-first implementation, independent review after every task, and final whole-increment review.

Goal: make the approved neutral eyes visibly follow the Windows cursor at arbitrary angles with a larger, continuous `±3.0` horizontal and `±2.0` vertical source-pixel range, while preserving deterministic click actions and keeping organic-head R5 blocked.

Architecture: extract the reviewed neutral-eye inverse warp into one cached Pillow compositor shared by authoring evidence and runtime. Keep cursor math in `EyeMotionController`. Add a pure runtime session for ownership, recentering, and failures. Give action playback cancellable, transactional ownership. Make `PetWindow` only the Tk/renderer adapter.

Tech stack: Python 3.11+, Pillow 11, Tk `after`, Win32 `GetCursorPos`, existing `UpdateLayeredWindow` renderer, pytest 8.

## Authorization and Baseline

- `CLOUD_HANDOFF.md` and the old progress ledger block visible runtime work before the former R5 center visual gate. Since then, the user explicitly approved the neutral-eye repair, accepted continuous arbitrary-angle tracking as the next direction, said “开始下一步吧”, and now said “继续”. This plan treats that newest trusted instruction as a narrow override for an independent neutral-eye source probe only.
- The override does not approve organic head movement, five-direction head assets, blink, idle tilt, packaging, release, or EXE work. R5 remains `blocked` throughout this increment.
- The local checkout contains exact GitHub blobs for all 18 real action images under `assets/keyframes/{jump,squash,shake}/00.png` through `05.png`. Their dimensions and blob hashes were verified against remote commit `48c9cb56ecc82029625929d267d6568fcfa0c756` before this plan.
- Before publishing, re-read the remote branch head. If it moved, stop and reconcile rather than overwriting another change.
- Local hydration commits contain files already present remotely. They are baselines, not changes to republish. A final Git Data update must use the current complete remote tree and add only the true changed blobs.

## Global Constraints

- Do not generate, edit, recolor, crop, or replace visual assets. Keep every existing file under `assets/keyframes/`, `assets/rig/v1/source/`, and `qa/` byte-for-byte unchanged.
- This is explicitly a source-tree probe. Loading authoring assets from `assets/rig/v1/source/eye-neutral-v1` is not a production or packaging contract and must not be presented as one.
- Keep the original six-file action asset validation. For the probe’s logical playback only, frame 0 and frame 5 use the same cached neutral-center composition; logical frames 1 through 4 use existing action images 01 through 04 by object identity. Do not delete or rewrite physical 00/05 files.
- Do not use whole-image crossfades. Recenter only independently composited eyes before action ownership begins.
- Cursor mapping stays continuous and formula-derived. Do not introduce 8-way or 16-way pose sprites. Source limits remain horizontal `±3.0` and vertical `±2.0`.
- Sampling stays on the UI thread with a `33ms` start-to-start target, frame-rate-independent smoothing time constant `60ms`, and maximum integration `dt` of `100ms`. Scheduling uses an absolute monotonic deadline, one active token, late-callback coalescing, and no catch-up burst; render time must not be added on top of another unconditional 33ms delay.
- Runtime composition uses Pillow only. Do not import `tools`, NumPy, OpenCV, cv2, Live2D, Qt, OpenGL, or add dependencies.
- Output remains straight-alpha `RGBA 512x768`. The layered renderer performs the only BGRA premultiplication. Canonical Alpha and RGB outside the fixed aperture supports must remain unchanged.
- Dragging and resizing stay live. Eye screen geometry derives from authoritative `_window_rect`, source size, and compositor eye midpoint, including negative monitor coordinates.
- A valid click pauses sampling, recenters from the last successfully displayed pose, then starts the six logical action frames. The intended recenter duration is `0.132` monotonic seconds. Tk may deliver late, so exact center must appear on the first callback whose elapsed time is at least `0.132`; never claim wall-clock delivery at exactly 132ms.
- Recenter/action repeated clicks do nothing. They do not advance action order, add timers, replay animation, or show a bubble.
- Action finish does not repaint. Logical frame 5 is already neutral. Synchronize the paused controller to exact center, then resume exactly one sampling loop from the current cursor.
- Window shutdown cancels eye sampling, recentering, animation, and bubble callbacks. Stale callbacks cannot sample, compose, render, mutate ownership, or reschedule.
- Update `last_displayed_pose` only after the display callback succeeds. A composition or display failure must enter a distinct disabled fallback once, preserve the last successfully displayed image and adapter cache, cancel eye/recenter timers, and leave legacy click actions usable with original physical action frames 00 through 05. Do not retry eye composition or flood error dialogs.
- Action selection is transactional: inspect the next action without advancing; commit only after playback accepts ownership. Failed playback leaves the sequence unchanged.
- Automated equality cannot approve motion naturalness. The `neutral → 01` and `04 → neutral` joins remain user visual gates.

## Task 2: Cached Shared Neutral-Eye Compositor

Files:

- Create `src/desktop_pet/neutral_eye_compositor.py`
- Create `tests/test_neutral_eye_compositor.py`
- Modify `tools/build_neutral_eye_layers.py`
- Modify `tools/build_neutral_eye_preview.py`
- Modify `tests/test_neutral_eye_layers.py`
- Modify `tests/test_neutral_eye_preview.py`
- Create `.superpowers/sdd/runtime-eye-follow-task-2-report.md`
- Modify `.superpowers/sdd/progress.md`

Interfaces:

- `NeutralEyeCompositor.load(asset_dir: Path) -> NeutralEyeCompositor`
- `source_size: tuple[int, int]`, currently `(512, 768)`
- `eye_midpoint: tuple[float, float]`, derived from both movement anchors and currently `(122.5, 349.0)`
- `compose(eye_x: float, eye_y: float) -> Image.Image`
- Preserve `tools.build_neutral_eye_layers.compose_pose(...)` as a compatibility wrapper.
- Make preview construction load one compositor and reuse it for all frames.

Acceptance:

- Before extracting the old implementation, freeze independent raw-RGBA SHA-256 goldens for center, four cardinals, four diagonals, and at least three fractional poses. The new tests compare against those fixed values, not a wrapper that calls the new code.
- `load` validates authoring metadata, required output names and committed SHA values, exact mode/size, exact motion limits, finite in-canvas anchors, nonempty binary supports, anchors strictly inside their supports, and at least one positive boundary distance per eye.
- No image or JSON I/O occurs after construction. Returned images are independent copies.
- Construction precomputes crops, support masks, source Alpha, premultiplied RGB, fixed boundaries, and smoothstep displacement weights once.
- All golden poses are byte-identical. Center is canonical-exact. Every pose preserves full Alpha, changes no RGB outside support union, pins boundaries, and adds no near-black outer-ring pixel.
- NaN, infinity, and offsets outside `±3.0/±2.0` raise `ValueError` before composition.
- A warm cloud CI regression check of 30 non-center source compositions completes within `0.60s`; record elapsed time. This is not evidence of end-to-end 30fps.
- Preserve the existing magenta-underlay seam test as an independent proof that displaced eye pixels cannot expose the underlay. Add caller-mutation isolation as a separate test; committed hash validation cannot replace either contract.
- Direct source-tree CLI use remains supported without an editable install. Subprocess smoke tests from repository root, with `PYTHONPATH` removed, run both authoring tools through `--help` and prove their runtime compositor import fallback.
- Runtime module contains no forbidden imports. Existing builder/preview tests remain green, and a temporary preview-v2 rebuild is byte-identical to committed evidence. Do not publish regenerated assets or QA files.

Steps:

- [ ] Write fixed golden and validation tests; run and record RED.
- [ ] Implement the minimal cached compositor and authoring compatibility wrapper.
- [ ] Reuse one instance in preview generation and preserve output bytes.
- [ ] Run focused tests, applicable full tests, forbidden-import scan, `git diff --check`, and temporary evidence comparison.
- [ ] Commit, write the SDD report, package the exact diff, obtain independent review, fix every Critical/Important finding, and update the ledger.

## Task 3: Controller Synchronization and Pure Runtime Session

Files:

- Modify `src/desktop_pet/eye_follow.py`
- Modify `tests/test_eye_follow.py`
- Create `src/desktop_pet/eye_runtime.py`
- Create `tests/test_eye_runtime.py`
- Create `.superpowers/sdd/runtime-eye-follow-task-3-report.md`
- Modify `.superpowers/sdd/progress.md`

Interfaces:

- Add `EyeMotionController.synchronize_pose(eye_x, eye_y)`. It is valid only while paused; it validates finite in-range values, updates internal and last-emitted pose, and never emits or schedules.
- Add exact-center settle: when the center target enters the stability threshold, emit exact `(0.0, 0.0)` once if the displayed pose is not already exact.
- Add a Tk-free `RuntimeEyeSession` with states `following`, `recentering`, `playing`, `disabled`, and `stopped`, one eye controller, one generation-tagged recenter token, last successful displayed pose, and injected compose/display/schedule/cancel/clock callbacks. Controller pause is an internal condition, not a public session state.

Acceptance:

- Tests cover paused-only synchronization, invalid input, no emission/scheduling, resume from center, and one exact-center settle emission.
- `EyeMotionController` schedules against an absolute monotonic next deadline. Fake-clock tests prove callback starts target 33ms spacing when work consumes 0, 7, or 20ms; at 40ms they prove missed absolute deadlines are skipped and the recorded start interval reflects lateness without a catch-up burst. It never schedules a negative delay and still owns at most one token. Smoothing uses actual elapsed start-to-start time capped at 100ms.
- `start()` successfully displays center before starting exactly one tick. If display fails, the session disables once and starts no timer.
- Geometry equals `rect.x + midpoint.x * rect.width / source_width` and `rect.y + midpoint.y * rect.height / source_height`, with `display_height = rect.height`; cover drag, resize, and negative coordinates.
- `pause_and_recenter()` pauses sampling first. It interpolates monotonically from last successfully displayed pose with no overshoot and has at most one token.
- Tests exercise callbacks at elapsed 33, 66, 99, and 132ms, a callback after 132ms, and delayed/coalesced callbacks. Exact center is emitted on the first elapsed callback at or beyond the duration.
- Starting at center completes synchronously with no recenter token.
- Only successful display updates last pose. Compose/display exceptions invoke one injected disable callback, stop future eye work, preserve last display, and do not escape the UI callback.
- Disabled state no longer owns clicks or action images. It returns an explicit fallback result so the window can use the transactional legacy path with original physical frames 00 through 05. It never calls the compositor again.
- Stale callbacks after cancel, transition, failure, or stop cannot compose, display, or reschedule.
- This task does not own action selection or import Tk/Pillow asset loaders.

Steps:

- [ ] Write controller deadline/synchronization and pure-session tests first; run and record RED.
- [ ] Implement synchronization, exact-center settle, absolute-deadline scheduling, and the session state machine without UI or asset responsibilities.
- [ ] Run focused and applicable regression tests plus `git diff --check`.
- [ ] Commit, report, package, independently review, fix all Critical/Important findings, and update the ledger.

## Task 4: Transactional Action Ownership and Cancellation

Files:

- Modify `src/desktop_pet/model.py`
- Modify `tests/test_model.py`
- Modify `src/desktop_pet/animation.py`
- Modify `tests/test_animation.py`
- Modify `src/desktop_pet/eye_runtime.py`
- Modify `tests/test_eye_runtime.py`
- Create `.superpowers/sdd/runtime-eye-follow-task-4-report.md`
- Modify `.superpowers/sdd/progress.md`

Interfaces:

- Replace eager action selection in the integration path with `ActionCycle.peek()` and `ActionCycle.commit(expected)`. Keep compatibility only where existing public tests require it.
- Give `AnimationController` ownership of a generation-tagged scheduled token and `stop()`. A canceled or stale callback cannot show a frame, finish, or schedule another callback.
- Extend `RuntimeEyeSession` with action-request, logical-frame selection, accepted-play, failed-play, and animation-finished transitions through injected callbacks.

Acceptance:

- Failed or rejected play does not advance action order, show a bubble, or strand the eye session paused. It restores one following loop.
- Successful accepted play commits exactly once. Repeated requests during recenter/playing do nothing.
- For all three actions, logical frames 0 and 5 are the same cached neutral-center object; logical 1–4 are real hydrated frame objects 01–04. The six indices and final 90ms hold remain unchanged.
- Bubble text is selected and shown only after recenter completes and play accepts ownership.
- Finish synchronizes exact center, transfers ownership, and resumes one loop without repainting.
- `AnimationController.stop()` cancels its current token. Old generation callbacks after stop/new playback cannot render or finish.
- Shutdown ordering leaves no eye, recenter, animation, or bubble callback alive.
- After an eye composition failure, three successive accepted fallback clicks still produce `jump`, `squash`, and `shake`, each using physical 00 through 05, with one matching bubble and finish callback. Shutdown from fallback still cancels animation and bubble work.

Steps:

- [ ] Write transactional cycle, cancellation, real-frame identity, and session ownership tests; run RED.
- [ ] Implement the smallest transactional and cancellable contracts.
- [ ] Run focused and applicable regression tests plus `git diff --check`.
- [ ] Commit, report, package, independently review, fix all Critical/Important findings, and update the ledger.

## Task 5: PetWindow Source-Probe Wiring and Safe Fallback

Files:

- Modify `src/desktop_pet/assets.py`
- Modify `tests/test_assets.py`
- Modify `src/desktop_pet/window.py`
- Modify `tests/test_window.py`
- Modify `src/desktop_pet/main.py`
- Modify `tests/test_main.py`
- Create `.superpowers/sdd/runtime-eye-follow-task-5-report.md`
- Modify `.superpowers/sdd/progress.md`

Interfaces:

- Add a source-probe loader for `assets/rig/v1/source/eye-neutral-v1`, clearly named/documented as non-packaged.
- Inject compositor and cursor provider into `PetWindow`; keep the pure session independent of Tk and Win32 rendering.
- Wire current `_window_rect` geometry, source composition, existing resize/renderer path, action callbacks, bubble lifecycle, and close lifecycle.
- `main()` attempts the probe when assets validate. Initial load failure follows the existing fatal startup path. Runtime compose/render failure disables eye following once and preserves legacy actions without closing the pet.

Acceptance:

- Window initialization displays the cached neutral center, then starts one eye loop.
- Pose callbacks compose at source resolution and render against current `_window_rect`. Drag/resize/negative coordinates use live geometry.
- Action ownership prevents eye callbacks overwriting action frames. The window displays the logical neutral boundaries and real 01–04 frames in order.
- Runtime failure is reported once, stops eye work, preserves the last successful image, and leaves transactional legacy click cycling operational with physical 00 through 05. No retry loop or repeated dialog.
- Image, resized-image, rectangle, and related render caches commit only after `renderer.render(...)` succeeds, or are restored from an exact snapshot on failure. Tests inject a transient failure and prove internal state still matches the physical last-successful frame before a later legacy action succeeds.
- Consecutive renderer failures are counted and any successful render resets that count. A second consecutive failure marks rendering unavailable and prevents further render attempts while preserving the last screen/cache state; eye work and animation stop, but the menu/exit path remains usable. The promise that legacy actions continue applies only after a one-off composition failure or transient renderer failure.
- All exit paths call eye-session stop, animation stop, and bubble destroy/cancel before root destruction.
- Main/assets tests identify this as a source probe, not a packaged resource guarantee.
- Headless pure tests provide most coverage. Tk tests run only with a display and are reported honestly. Windows-only renderer tests stay skipped elsewhere.
- No packaging or EXE work occurs.

Steps:

- [ ] Write asset, window-adapter, atomic-render rollback, transient/persistent failure, fallback-action, shutdown, and main wiring tests first; run RED.
- [ ] Implement the smallest adapter wiring and one-time fallback.
- [ ] Run focused tests, all applicable tests, forbidden-scope scan, `git diff --check`, and a source launch smoke test when the environment permits.
- [ ] Commit, report, package, independently review, fix every Critical/Important finding, and update the ledger.
- [ ] Produce one whole-increment review package from the true remote baseline through Task 5 and dispatch the most capable final reviewer.

## Post-Code Gates and Publication

Source completion is not visual acceptance. Before claiming the source probe passes:

- On Windows, test 180, 280, 420, and 520 display heights. After a 5-second warm-up, run three measured 10-second rounds per size using the same deterministic trajectory: horizontal sweep, vertical sweep, both diagonals, then one circle, with segment timing fixed in the measurement script.
- Measure every motion callback from callback entry through successful `UpdateLayeredWindow` return. Record p50/p95/max, achieved successful update rate, deadline coalesces, process CPU normalized to one logical core, and process working set at warm-up and each round end. Per-size gate: callback p95 at or below 33ms, at least 27 successful updates per second, average normalized process CPU no more than 85%, and working-set growth no more than 20 MiB from post-warm-up through the final round. A source-probe failure at any size blocks publication and triggers profiling, not threshold relaxation.
- Test drag, resize, negative-coordinate monitor movement, close during following/recenter/action, cursor-read failure, and injected composition/display failure.
- On both light and dark desktops and at all four sizes including 520, the user must inspect eye amplitude, smoothness, rim seams, black arcs, shimmer, synchronization, all three `neutral → 01` entries, and all three `04 → neutral` exits. Automated hashes do not substitute for this decision.
- If any action join looks abrupt, keep the probe blocked. Do not mask it with crossfade and do not generate new assets in this increment.
- Keep R5 `blocked` regardless of source results. Do not begin five-direction head, blink, tilt, runtime release, packaging, or EXE work without a later explicit user decision.
- Only after all code reviews are clean should the changed source/tests/docs be committed to the remote branch using the current complete remote tree. Report source status and remaining human/Windows gates precisely.

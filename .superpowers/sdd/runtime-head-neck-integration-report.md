# Runtime Continuous Head-Neck Integration Report

Date: 2026-08-31
Base commit: `f05aeff8a67890178dd1d586f8c7d4883dc121f6`
Branch: `codex/head-neck-continuous-preview`

## Outcome

The user-approved doubled continuous head and upper-neck deformation is integrated into the production source runtime. One live cursor vector drives arbitrary-angle eye and head motion; there are no direction bins or directional head images.

## Runtime Contract

- Cursor sampling remains one 33 ms UI-thread loop.
- Eye focus keeps the approved 60 ms time constant.
- Head state uses the approved 220 ms time constant.
- Eye/head compensation remains 0.35.
- Head render gain remains 1.225 and is radial-clamped.
- The deformation core remains at the user-approved 2.0 gain.
- Exact center bypasses head resampling and is cached for action frame zero and five.
- Action requests recenter both eye and head channels before playback.
- Composition or display failure retains the prior disabled-once physical-action fallback.

## Pixel-Preserving Performance Work

- Reused each eye pixel's bilinear coordinates for Alpha and RGB instead of recalculating them four times.
- Restricted the hot head warp to the padded region that can influence visible dynamic pixels; the public full mesh and all safety validation remain available to tests.
- Existing raw-pixel goldens, independent full-ROI oracle comparisons, deterministic preview outputs, center identity, transparency gates, and protected-region gates all remain green.
- Recorded warm 60-pose cloud benchmark: 1.533594171 seconds total, 25.55990285 ms per composed frame, 39.12377938 frames per second.
- Pre-optimization comparison run: 34.49528463 ms per composed frame.
- Center raw-RGBA SHA-256: `775551951b58abb62221bb5e48d1d6077966c9d1690dcfeb54460a5f63842e30`.

## Verification

- Applicable non-Tk suite after final optimization: 381 passed, 4 skipped in 267.89 seconds.
- Headless `PetWindow` suite: 29 passed, 23 display-dependent tests deselected.
- Continuous deformation focused suite: 42 passed.
- Controller, runtime session, asset, main, cached-center action, and exact-center focused gates passed.
- Python compilation passed for production modules, tools, and changed tests.
- `git diff --check` passed.
- No asset, QA image, workflow, spec, directional sprite, or generated-art file changed.

## Known Baseline Limitation

The tracked `tests/test_interpolate_action.py` cannot be collected on this branch because its pre-existing `tools/interpolate_action.py` module is absent. It is unrelated to this integration and was not recreated or modified. The full applicable suite explicitly excluded that test and the display-dependent `tests/test_window.py`; the headless subset of the latter was run separately.

## Deferred

No blink, tilt, directional materials, new art, packaging, EXE, signing, release, or GitHub Actions work was started.

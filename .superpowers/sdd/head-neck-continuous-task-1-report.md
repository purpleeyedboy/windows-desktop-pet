# Continuous Head-Neck Task 1 Report

This report records the original conservative deformation-core contract. The
current core uses the later user-requested double-amplitude contract documented
in `head-neck-double-amplitude-report.md`.

## Scope

Task 1 is limited to the continuous Pillow head/neck deformation core, its
focused tests, and this report. Task 2 preview/QA publishing, runtime wiring,
assets, packaging, and unrelated Git history are intentionally unchanged.

Implementation commit: `38b22af`.

## TDD evidence

### RED

Command:

```text
python -m pytest -q tests/test_head_neck_deformation.py
```

Result before the production module existed: exit code 2 during collection,
with `ModuleNotFoundError: No module named
'desktop_pet.head_neck_deformation'`. This is the expected missing-feature
failure.

After the plan was corrected to its final 24-by-18 topology, signed semantic
offsets, fixed dynamic polygon, protected strips, and geometric writeback
contract, the tests were revised before production code. Running the same
command against the superseded implementation produced exit code 1 with
`13 failed, 26 passed`. The failures covered the topology, missing public
`sampling_offset_at`, pinned geometry, independent render oracle, and Alpha
preservation gates. This is the RED evidence for the final contract.

### GREEN and verification

The implementation provides the immutable `HeadPose` and the public
`ContinuousHeadNeckCompositor` interfaces. It uses the exact 24-by-18 mesh,
the fixed semantic field and 20-pixel polygon smoothstep, signed inverse
sampling, the right-body/lower-band protection, premultiplied Bicubic MESH,
and geometric source writeback. Exact center bypasses head resampling.

The Alpha plateau correction also followed RED/GREEN. A new focused test
first failed because a warped dynamic `A=253` pixel remained 253. The minimal
change maps `A>=252` to 255 only after warped pixels are converted back to
straight RGBA. It does not recalculate straight RGB. Geometric writeback then
restores polygon-exterior and protected-strip bytes, and zero-Alpha RGB remains
cleared. The independent test oracle performs the same separately implemented
normalization.

Final commands and results after the exact 20-pixel boundary-ramp correction:

```text
PYTHONPATH=src:. python -m pytest -q tests/test_head_neck_deformation.py
41 passed in 2.70s

PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_deformation.py \
  tests/test_neutral_eye_compositor.py
77 passed in 7.07s

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m pytest -q \
  tests/test_animation.py tests/test_assets.py tests/test_eye_follow.py \
  tests/test_eye_follow_candidate_packaging.py tests/test_eye_runtime.py \
  tests/test_layered_window.py tests/test_main.py tests/test_model.py \
  tests/test_neutral_eye_compositor.py tests/test_neutral_eye_layers.py \
  tests/test_neutral_eye_preview.py tests/test_repository_attributes.py \
  tests/test_windows_eye_follow_candidate_workflow.py \
  tests/test_windows_source_validation_workflow.py
316 passed, 4 skipped in 78.20s

python -m py_compile src/desktop_pet/head_neck_deformation.py \
  tests/test_head_neck_deformation.py
git diff --check
```

The compile and diff-check commands exited zero. The production dependency
scan found no NumPy, OpenCV, Live2D, or Inochi2D import. The 316-test non-Tk
regression above was run after the final 20-pixel correction. A literal full
`pytest -q` cannot collect because the pre-existing
`tests/test_interpolate_action.py` imports absent `tools.interpolate_action`.
A tracked-suite run excluding that file reached `385 passed, 4 skipped` before
20 real-Tk fixture errors caused by the headless environment's missing
`$DISPLAY`. Neither unrelated blocker was modified.

The implementation and its tests are committed separately from Task 2 so the
deformation core remains independently reversible.

## Performance

Read-only in-memory measurements used CPython 3.12.13 and Pillow 11.3.0 on the
Linux KVM worker. Values are p50/p95/max milliseconds:

| Operation | p50 | p95 | max |
|---|---:|---:|---:|
| Cached-weight `mesh_for` | 3.104 | 5.473 | 7.077 |
| Center bypass including moving-eye composition | 10.099 | 16.649 | 45.307 |
| Full-size horizontal head composition | 21.534 | 27.655 | 38.081 |
| Full-size diagonal eye-plus-head composition | 35.036 | 44.031 | 50.944 |

Caching the fixed 25-by-19 vertex field reduced an earlier `mesh_for` median
from 13.563ms to the value above without changing output. These are offline
source-size preview numbers and exclude window resize, BGRA conversion, DIB,
and `UpdateLayeredWindow`; they are not a 33ms runtime acceptance claim. A
future runtime must use cached output-resolution ROI assets/buffers and be
benchmarked end to end on Windows.

At the audit poses, mesh source/output area ratio stayed within
`0.854047..1.141446`. Unit horizontal inverse offsets were nose -3.400001,
eyes -2.815410/-2.712671, ear tips -1.751499/-1.695514, ear roots
-2.604881/-2.528961, and neck roots -2.131167/-1.818371 pixels. Unit vertical
nose offset was -2.5 pixels; protected chest offset was exactly zero.

## Remaining risks

- Automated geometry and pixel oracles do not establish that the motion looks
  natural. Task 2 background sheets, slow motion, seam closeups, and explicit
  human visual approval remain mandatory.
- Four-connected exact-zero telemetry can report a 48-pixel enclosed component
  when a fractional warp closes a narrow fur/collar channel that was connected
  to exterior background. Read-only diagnostics found that forcing a warped
  exterior mask with NEAREST removes anti-aliasing yet still leaves a legitimate
  25-pixel transformed inner component. That pixel modification was rejected;
  downstream validation is expected to use 8-connect blocking with 4-connect
  telemetry. H1 pixels and thresholds were not relaxed for this issue.
- The plateau normalization is deliberately narrow (`252..254` only) and is
  tested against static geometric writeback. It still requires review on light,
  dark, gray, and checker backgrounds.
- Full-size diagonal composition exceeds a 33ms frame on this worker. Runtime
  integration and packaging remain blocked and outside Task 1.
- The single-image warp cannot reveal unseen anatomy and may still produce
  unnatural whisker, ear-root, collar, or neck deformation at visual extrema.

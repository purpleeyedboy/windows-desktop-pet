# Task 2 Report: Cached Shared Neutral-Eye Compositor

## Scope

- Added the Pillow-only `desktop_pet.neutral_eye_compositor.NeutralEyeCompositor`.
- Kept `tools.build_neutral_eye_layers.compose_pose(...)` as a compatibility wrapper.
- Changed preview construction to load one compositor and reuse it for all 90 frames.
- Added no window, session, action, packaging, or visual-asset changes. R5 remains blocked.

## RED

Before production changes, the old `compose_pose` implementation was used to freeze
12 independent raw-RGBA SHA-256 values: center, four cardinals, four diagonals, and
three fractional poses.

Command:

```text
python -m pytest -q tests/test_neutral_eye_compositor.py tests/test_neutral_eye_preview.py::test_preview_has_shared_offsets_containment_and_final_canonical
```

Result:

```text
27 failed, 2 passed in 0.35s
```

The failures were the expected missing behavior: the new compositor module did not
exist and preview did not expose or reuse `NeutralEyeCompositor`.

After independent review, regression tests were added before the fix for Pillow 11
API compatibility, fixed output hashes, same-bytes decoding, shared preview
snapshots, strict anchor raster semantics, CLI source resolution, and float
overflow. The focused reviewer regression command produced:

```text
13 failed, 9 passed, 73 deselected in 1.51s
```

All 13 failures matched the newly required behavior rather than test setup errors.

## GREEN and Regression Verification

Focused initial GREEN:

```text
python -m pytest -q tests/test_neutral_eye_compositor.py tests/test_neutral_eye_preview.py::test_preview_has_shared_offsets_containment_and_final_canonical
29 passed in 3.29s
```

Final applicable neutral-eye suites after independent-review fixes:

```text
PYTHONWARNINGS=ignore::DeprecationWarning python -m pytest -q tests/test_neutral_eye_compositor.py tests/test_neutral_eye_layers.py tests/test_neutral_eye_preview.py
95 passed in 47.67s
```

Final full non-Tk repository suite:

```text
PYTHONWARNINGS=ignore::DeprecationWarning python -m pytest -q --ignore=tests/test_window.py
146 passed, 3 skipped in 47.84s
```

The host runtime contains Pillow `12.3.0`, which is outside the declared
`Pillow>=11,<12` range and deprecates `getdata()`. Warnings were suppressed only
to keep the final output readable. A focused compatibility test statically proves
that production, tools, and Task 2 tests contain no `get_flattened_data` reference,
then monkeypatches that post-Pillow-11 API to fail and successfully loads/composes.
All pixel iteration uses explicit `tuple(image.getdata())` or
`list(image.getdata())`, which is available in the declared Pillow 11 range. The
dependency bound was not changed.

Tk tests remain unavailable because this environment has no `$DISPLAY`; window
tests are outside Task 2 and were not changed.

The focused tests cover metadata and output validation, finite/in-range input,
source geometry, independent caller results, no compose-time image/JSON I/O,
fixed boundaries, Alpha, outside-support RGB containment, near-black outer-ring
containment, the independent magenta-underlay seam proof, all frozen goldens,
single preview load/reuse, and both direct source-tree CLI help paths.
Review-fix coverage additionally proves synchronized PNG/metadata tampering is
rejected, every input is read once, decoding uses the hashed bytes, preview stats
and frames share one snapshot, fractional boundary anchors are rejected through
eroded-support raster semantics, the positive-boundary-distance error branch is
reached, and integer-to-float overflow becomes `ValueError`.

## Performance

One compositor was loaded, one non-center pose was used to warm it, then 30
non-center source compositions were timed with `perf_counter()`:

```text
elapsed_seconds=0.216146891
budget_seconds=0.600000000
```

This is a source-composition regression check only, not evidence of end-to-end
30 fps or Windows renderer performance.

## Temporary Preview-v2 Comparison

`build_preview(...)` was run into a `TemporaryDirectory`; no regenerated evidence
was committed.

```text
eye-follow.gif: equal=True bytes=2574297 sha256=66adaaabd232c71b4e6b35a7be46f9bc2d080a578aea441fa900ae3dc8b6dbdf
stats.json: equal=True bytes=22221 sha256=e219ad4cab9b02ae3e72662a0401234fb307d9ab19eac94deffc8e8ff51b3172
```

Both temporary files were byte-identical to `qa/neutral-eye-v1/preview-v2`.

## Static and Scope Checks

```text
forbidden_imports=[]
direct_cli_help=passed
direct_cli_compositor_path=/workspace/scratch/4bfcae99ab40/windows-desktop-pet/src/desktop_pet/neutral_eye_compositor.py
asset_or_qa_tracked_changes=0
git_diff_check=passed
```

The forbidden-import scan covered `tools`, NumPy, OpenCV/cv2, Tk, ctypes/Win32,
Live2D, Qt, and OpenGL imports in the runtime compositor.

## Self-review and Remaining Risks

- All 12 raw-RGBA hashes match the pre-extraction implementation exactly.
- Construction caches crops, binary supports, source Alpha, premultiplied RGB,
  boundary flags, and smoothstep displacement weights. `compose()` performs no
  file or JSON reads and returns a fresh image.
- Load rejects invalid canonical/warp/motion metadata, missing or mismatched
  output records, any deviation from the five approved output SHA values,
  hash/mode/size mismatches, invalid anchors, empty supports, anchors not strictly
  inside eroded support, and invalid boundary-distance geometry.
- `ValidatedNeutralEyeSnapshot` reads each JSON/PNG once, hashes and decodes the
  same bytes through `BytesIO`, and supplies both preview statistics and the one
  reused compositor. The canonical preview image follows the same single-read
  hash/decode rule.
- The magenta-underlay seam proof uses the isolated in-memory compositor
  construction path. Public `load()` remains fixed-hash strict.
- The compatibility wrapper intentionally constructs a compositor per call;
  preview uses the cached path directly and loads exactly once per build.
- This remains a source-tree authoring probe. It is not a packaged-resource or
  production deployment contract.
- Tk/window behavior and the Windows end-to-end performance/visual gates were not
  exercised in this headless Task 2 environment. R5 and all organic-head work
  remain blocked.

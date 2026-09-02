# Approved Head and Body Runtime Integration Report

## Scope and baseline

- Requirement source: `docs/superpowers/plans/2026-09-02-approved-head-body-integration.md`.
- Local baseline: `493ad45` (`baseline: materialize remote head subset`).
- Materialized from remote commit: `62c2023264910c983903254eeedc07a08545c433`.
- No existing delivery EXE or rejected QA evidence was modified.
- The two approved PNGs were never encoded, transformed, resized, cropped, or overwritten. They were read only for hashing, decoding, and composition.

## TDD evidence

### Approved runtime assembler RED

Command:

```text
python -m pytest -q tests/test_build_approved_runtime_assets.py
```

Result before `tools/build_approved_runtime_assets.py` existed:

```text
ERROR tests/test_build_approved_runtime_assets.py
ImportError: cannot import name 'build_approved_runtime_assets' from 'tools' (unknown location)
1 error in 0.08s
```

The test already asserted exact approved hashes and dimensions, exact body-backplate bytes, deterministic output, approved composite equality outside the eye-mask union, preservation of previous-underlay pixels where the union mask is fully opaque, and unchanged approved source bytes across two builds.

### Approved runtime assembler GREEN

The first post-implementation run exposed a test-only mask interpretation error:

```text
1 failed, 1 passed in 0.28s
```

The assertion had used the inverse of a soft grayscale mask as “outside.” It was corrected to select only pixels where the union mask is zero; production code was unchanged. The corrected focused result was:

```text
2 passed in 0.28s
```

After adding strict previous/derived underlay hash validation and an idempotent path for an already-derived underlay, the focused result remained:

```text
2 passed in 0.27s
```

Fresh review found that the checked-in derived underlay made this version of the test exercise only the idempotent branch. The final test fixture is the exact previous underlay blob extracted from baseline commit `493ad45`, with SHA-256 `28bc087f2d45a9e2dc2774c96a0b853b55b65795726d0eecb374d90310c5aac9`. It forces the first build through the specified composite and the second through the idempotent path.

The same review requested exact mask validation. A byte-changed mask test was added first and produced the expected RED:

```text
1 failed, 2 passed in 0.41s
```

After locking both approved mask hashes in the assembler, focused GREEN was `3 passed in 0.30s`. A subsequent transaction review requested fault recovery between the two output replacements. The injected second-replace failure test first produced:

```text
1 failed, 3 passed in 0.45s
```

After adding an adjacent rollback copy of the exact previous underlay, the focused result was:

```text
4 passed in 0.40s
```

A direct second build of the checked-in derived directory returned the same hashes:

```text
underlay.png: d83230b60fe753b7344ae0b349d0c1409b47dc2002df66c5689765fcb0ca2495
body-backplate.png: 527eaad70a84c611f0839bc3898b5c00f41df383c191771c7e07a1af588e5ce8
```

### Candidate packaging RED

After updating only packaging/workflow tests to the required new names, before changing production packaging files:

```text
python -m pytest -q tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py
3 failed, 6 passed, 1 skipped in 0.09s
```

The three expected failures identified the old spec EXE name, old PowerShell candidate name, and old workflow artifact/path.

### Candidate packaging GREEN

After updating the spec, PowerShell script, and workflow:

```text
python -m pytest -q tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py
9 passed, 1 skipped in 0.04s
```

The skip is the existing real-Windows-junction cleanup test on a non-Windows host.

### Integration progression

After updating the runtime locks and assets, a diagnostic run of the neutral-eye and asset suites produced:

```text
11 failed, 39 passed in 2.54s
```

Five failures were expected new runtime golden changes, one was the obsolete filled-neck backplate assertion, and five were missing-file references caused by the materialized baseline subset. Golden assertions were updated to the approved runtime result, the backplate assertion now requires the exact approved body bytes, and a temporary local diagnostic parameterized only old authoring tools actually present in the materialized subset. That diagnostic produced `46 passed, 2 skipped in 3.18s`; the missing-file test accommodations were not retained.

The first required full matrix then found the remaining direct reference to the unmaterialized `canonical-idle.png` in the head/neck alpha invariant test:

```text
1 failed, 112 passed, 3 skipped in 5.38s
```

The temporary missing-file accommodations were then reverted so the remote repository's existing canonical and authoring-tool tests remain intact for the complete CI checkout. The head/neck test's canonical path, the neutral compositor's `CANONICAL` reference and canonical comparisons, the fixed authoring-tool parameters, and the original relevant-path list are unchanged from baseline. The new builder is the only addition to that relevant-path list.

### Final runnable local GREEN matrix

Command:

```text
python -m pytest -q tests/test_build_approved_runtime_assets.py tests/test_neutral_eye_compositor.py tests/test_assets.py tests/test_head_neck_deformation.py tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py -k "not all_golden_poses_preserve_alpha_containment_boundaries_and_outer_ring and not supported_pillow_api_does_not_require_post_pillow_11_methods and not authoring_tool_help_supports_direct_source_tree_execution_without_pythonpath and not direct_script_diagnostic_uses_repository_compositor_before_fake_installed_package and not alpha_and_transparent_rgb_invariants_are_preserved"
```

Result:

```text
112 passed, 1 skipped, 7 deselected in 4.60s
```

The skip is the existing real-Windows-junction test. Seven tests were deselected only because their unchanged baseline behavior directly opens one of the unmaterialized files listed under limitations. The exact unfiltered planned matrix was run before the test restorations and demonstrated the missing-file failures, but it is not claimed as a final local GREEN result. The complete checkout's CI must run the unfiltered command.

## Implementation

- Added a Pillow-only offline assembler with exact immutable head/body hashes and `HEAD_OFFSET = (24, 204)`.
- Validates the approved RGBA dimensions and hashes, existing RGBA underlay, and both 512x768 L masks.
- Locks and validates both eye-mask SHA-256 values before either idempotent or composition output handling.
- For the locked previous underlay, alpha-composites the head over the approved body without resampling, applies `Image.composite(previous_underlay, approved_composite, max(eye-left-mask, eye-right-mask))`, and clears RGB only where final alpha is zero.
- Recognizes only the locked previous or locked derived underlay hash, making a second build byte-identical instead of reapplying soft-mask blending.
- Writes adjacent temporary PNGs, decode-verifies both, verifies exact body bytes and the derived underlay hash, then atomically replaces only `underlay.png` and `body-backplate.png`. An adjacent exact-byte rollback file restores the previous underlay if the second replacement fails, preventing mixed old/new outputs.
- Updated authoring provenance with exact source paths, hashes, dimensions, offset, composition rule, and derived hashes.
- Updated only the underlay lock in `neutral_eye_compositor.py` and the backplate lock in `assets.py`.
- Preserved eye surfaces and masks byte-for-byte and refreshed the runtime pose goldens.
- Renamed the new candidate to `桌面宠物-头颈素材更新版.exe` and the hosted artifact to `desktop-pet-approved-head-neck-assets` without changing prior delivery files.

## Final hashes and dimensions

| File | Mode / dimensions | SHA-256 |
|---|---:|---|
| `assets/rig/v1/source/approved/猫头-精准抠图.png` | RGBA 230x241 | `6e57c1be03db1a97a484576f6f88be8639d8f01bbfe5b0d792c68e3d985864e6` |
| `assets/rig/v1/source/approved/猫身-原像素保留-仅补头部缺口.png` | RGBA 512x768 | `527eaad70a84c611f0839bc3898b5c00f41df383c191771c7e07a1af588e5ce8` |
| `assets/rig/v1/source/eye-neutral-v1/underlay.png` | RGBA 512x768 | `d83230b60fe753b7344ae0b349d0c1409b47dc2002df66c5689765fcb0ca2495` |
| `assets/rig/v1/source/eye-neutral-v1/body-backplate.png` | RGBA 512x768 | `527eaad70a84c611f0839bc3898b5c00f41df383c191771c7e07a1af588e5ce8` |

The generated backplate was additionally verified with `cmp` to be byte-for-byte identical to the approved body.

Unchanged eye file hashes:

- `eye-left-mask.png`: `27bee30342e67cab45d77a14ad7eebb0125f72d4b19039b5c3c1bf506623a81c`
- `eye-left.png`: `6140a3a4085d8514795ea2c17ee2173964553c604f0d096a120a508fa9f7308c`
- `eye-right-mask.png`: `fba54f4eb10884d5a284ea6c16cd762d0786f61e09ddc5297e99d793c3a092e4`
- `eye-right.png`: `9528b5f3c985b8366003fd77d413ff564b50ae547c705e5e6aee85fc86542906`

## Static checks

- `python -m py_compile` over every changed Python file: PASS (no output).
- `git diff --check`: PASS (no output).
- `git diff 493ad45 --check`: PASS (no output); after the amended commit, `git diff 493ad45..HEAD --check` is the equivalent committed-range gate.
- Final local environment: Python 3.12.13, Pillow 11.3.0, pytest 8.4.2.

## Limitations and release gates

- The repository-level development workflow included independent subagent review. Its initial findings on core-path test coverage and mask validation were fixed and re-reviewed; a later transaction finding was covered by a RED/GREEN fault-injection test and rollback implementation.
- This baseline is an intentionally materialized related-file subset. It does not contain `assets/rig/v1/source/canonical-idle.png`, `tools/build_neutral_eye_layers.py`, `tools/build_neutral_eye_preview.py`, `tests/test_neutral_eye_layers.py`, or `tests/test_neutral_eye_preview.py`; no substitutes were invented.
- Local verification ran on Python 3.12.13 rather than the planned hosted Python 3.11. The workflow remains pinned to Python 3.11 and Pillow major version 11.
- No Windows EXE was built or claimed locally.
- No workflow was pushed or run, so hosted artifact archive contents, EXE size, and EXE SHA-256 remain unverified release gates.
- Real mouse tracking, blink, tilt, drag, resize, menu, single-instance behavior, and light/dark wallpaper appearance remain real Windows desktop user-acceptance gates.

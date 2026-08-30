# Task N2 Report: Deterministic Continuous Eye-Follow Preview

## Scope

Implemented the offline-only N2 vertical slice in `tools/build_neutral_eye_preview.py` with the authored Task 1 compositor as its sole renderer. No runtime, head-direction, blink, tilt, packaging, or EXE files were changed. R5 remains blocked.

## TDD record

The required initial command was run before the module existed:

```text
python -m pytest tests/test_neutral_eye_preview.py -q
```

The first environment attempt reported `No module named pytest`; `pytest 8.4.2` was installed into the active interpreter without changing project dependency files. The same required command was then rerun and recorded the intended RED:

```text
5 failed in 0.07s
ImportError: cannot import name 'build_neutral_eye_preview' from 'tools'
```

After implementation, focused verification was run:

```text
PYTHONWARNINGS=ignore python -m pytest tests/test_neutral_eye_preview.py -q
6 passed in 22.28s
```

The one required final full-suite command was also run:

```text
PYTHONWARNINGS=ignore python -m pytest -q
```

The execution bridge returned its live progress stream after 30 seconds (32 passing dots) while the process continued, then exited without returning a final summary. The existing pytest `lastfailed` cache lists two Task 1 underlay-boundary tests; this report does not claim a full-suite pass without a captured final pytest summary. N2 focused tests are fully green.

## Produced files

- `tools/build_neutral_eye_preview.py`
- `tests/test_neutral_eye_preview.py`
- `qa/neutral-eye-v1/preview-v1/eye-follow.gif`
- `qa/neutral-eye-v1/preview-v1/stats.json`
- `.superpowers/sdd/progress.md`

The preview was rebuilt through its CLI; the artifacts selected for commit have these hashes:

```text
ef1724afcdc91a6a1495f256261d15ce9698512a6d5398a7dff56588aa801689  eye-follow.gif
f7c8372a0798c5d495ad2a86e574c02bf810194bd5fe63a1c5a27a52c9bedb04  stats.json
```

## Contract checks implemented

- Exact 90-frame, 30 Hz recurrence using `1 - exp(-(1/30)/0.060)`; frame 84 is the explicit exact-center snap and frames 84–89 are canonical-exact.
- Shared `(eye_x, eye_y)` input to Task 1 `compose_pose` for every frame, with target and smoothed bounds validation.
- Fail-closed canonical, `authoring.json`, output hash, mode, and size validation before output staging.
- All 90 RGBA frames are checked for support-union containment, full-alpha equality, and the specified stationary outer-ring near-black condition.
- GIF is matte-composited, fixed web-palette quantized without dithering, saved with `optimize=False`, `disposal=2`, and `loop=0`; its expanded 10 ms decoded schedule is compared to the fixed-palette source schedule.
- JSON contains frame targets/offsets, source durations, decoded GIF metadata, maxima, containment, final center metrics, GIF hash, authoring hash, and every immutable input hash (without a self-hash).
- Staging replacement has tested rollback after an injected between-rename failure. Focused tests also prove two separate builds and the committed output are byte-identical.

## Visual review

Reviewed the generated GIF at normal size and a 4× eye crop (center and an in-motion frame). The fixed apertures show no black arc, gap, duplicated rim, static underlay crescent, or palette flicker; both eyes move coherently and the six final source frames are exact center. The GIF is deliberately web-palette encoded, so expected posterization is visible in the full-cat preview.

## Self-review / concerns

Implementation and focused tests meet the N2 contract. The only remaining concern is the unavailable final summary from the one full-suite invocation; the focused N2 suite is green, but the two pre-existing Task 1 entries in pytest's `lastfailed` cache should be independently confirmed by the integrating agent before declaring a repository-wide pass.

## Post-review fix: RGB-only validation and successful replacement

Review identified that Pillow's default RGBA `getbbox()` checks only alpha, allowing an RGB-only difference with an unchanged alpha channel to bypass both the outside-support containment check and the final-six-frame canonical check. Two new direct validator tests were written first:

- An RGB-only mutation outside the support union must raise containment validation failure.
- An RGB-only mutation inside support in frame 84 must raise final-six-frame canonical failure.

Before the fix, the required focused command produced the expected RED:

```text
python -m pytest tests/test_neutral_eye_preview.py -q
2 failed, 7 passed, 2340 warnings in 23.94s
```

Both failures were `DID NOT RAISE` for the two RGB-only mutations. The implementation now calls `getbbox(alpha_only=False)` for the outside-support and final-frame RGBA difference checks, so RGB as well as alpha differences are considered. A third regression test creates an existing output directory with a sentinel, performs a successful replacement, verifies sentinel removal plus GIF/stats consistency, and confirms no matching staging or backup sibling remains.

After the fix:

```text
python -m pytest tests/test_neutral_eye_preview.py -q
9 passed, 2431 warnings in 26.11s

python -m pytest -q
38 passed, 3015 warnings in 50.37s
exit code: 0
```

Warnings were intentionally not suppressed. They are Pillow `Image.Image.getdata` deprecations for Pillow 14, predominantly in the pre-existing Task 1 compositor and its tests; 91 arise from this preview tool's exact changed-pixel counter. No warnings indicate a test failure or a containment regression. The previous full-suite-summary concern is resolved by the captured exit-0 full run above.

## Final review fix: output isolation and failed-restore preservation

Two final-review Important findings were repaired with focused tests written first.

- `build_preview` now resolves aliases and rejects an output path that equals, contains, or is inside the immutable asset directory or canonical source path. It also rejects an existing output that is a symlink or not a directory before any input rendering, staging creation, or directory transaction starts.
- Directory replacement now has an explicit `installed` state. A backup is removed only after staging has been installed successfully. If installing staging fails and restoring the backup also fails, staging is cleaned up but the backup is preserved and the raised `OSError` names its retained path.

The new path test covers output equal to the asset directory, nested in it, an ancestor of both asset and canonical input, an existing ordinary file, and (where supported) both an unrelated directory symlink and a symlink alias to the asset directory. It snapshots every Task 1/canonical input hash and guards `_replace_output`, proving rejection happens before a transaction. The failed-restore test injects failure on both the staging installation rename and the backup restoration rename, then verifies the uniquely named backup still contains the original sentinel.

The expected RED before the implementation fix was:

```text
python -m pytest tests/test_neutral_eye_preview.py -q
2 failed, 9 passed, 2431 warnings in 29.27s
```

The failures were the transaction-start guard for an overlapping output and an error that did not name the retained backup. After the fix, warnings remained unsuppressed:

```text
python -m pytest tests/test_neutral_eye_preview.py -q
11 passed, 2431 warnings in 26.81s

python -m pytest -q
40 passed, 3015 warnings in 50.81s
exit code: 0
```

The warning source remains the existing Pillow `getdata` deprecation family described above. Future non-blocking review items recorded in progress are: the GIF oracle partly shares encoder assumptions, validation/rendering is not protected against external time-of-check/time-of-use edits, and the full 90-frame in-memory list is a peak-memory optimization opportunity.

# Task N3 Report: Amplified Arbitrary-Angle Eye-Follow Proof

## RED

Command:

```bash
python -m pytest tests/test_neutral_eye_layers.py tests/test_neutral_eye_preview.py -q
```

Result: `22 failed, 25 passed, 2815 warnings in 47.85s`.

The failures were the expected old-behavior failures: old `±1.5/±1.0` metadata and compositor rejection at the new extremes, missing `cursor_target` and activation-radius constant, the old stepped target schedule, missing mapping statistics, and the absent committed `preview-v2` outputs. They were not setup or syntax errors.

## Implementation

- `tools.build_neutral_eye_layers.MOTION_LIMITS` is exactly `{"x": 3.0, "y": 2.0}` and is used by the compositor and static contact-sheet extrema.
- Regenerated authoring metadata records those limits; authored PNG hashes and pixels remained unchanged.
- `cursor_target(dx, dy, activation_radius)` rejects non-finite coordinates/radius and non-positive radius, returns exact zero for zero input, and otherwise uses `distance = hypot(dx, dy)`, `strength = min(distance / activation_radius, 1.0)`, then `(3.0 * dx / distance * strength, 2.0 * dy / distance * strength)`.
- Preview-v2 uses named positive finite `VIRTUAL_CURSOR_ACTIVATION_RADIUS = 100.0`, formula identifier `radial-clamped-elliptical-v1`, the 57-sample virtual-cursor circle on frames 6..62, center targets on 0..5 and 63..89, exponential updates through frame 83, and exact-zero frames 84..89.

## Verification

Focused command:

```bash
python -m pytest tests/test_neutral_eye_layers.py tests/test_neutral_eye_preview.py -q
```

Result: `47 passed, 3015 warnings in 51.29s`.

Full command:

```bash
python -m pytest -q
```

Result: `47 passed, 3015 warnings in 51.97s`.

Independent reproducibility build used a separate `mktemp -d` output directory and byte-compared both generated files with `qa/neutral-eye-v1/preview-v2/`; both comparisons matched.

- `eye-follow.gif`: `66adaaabd232c71b4e6b35a7be46f9bc2d080a578aea441fa900ae3dc8b6dbdf`
- `stats.json`: `0d1788e3368334c2d037f5e3535cbb6eb80244d793bf2593276e9a171a46585f`

Containment metrics are all zero: outside-support changed pixels, alpha changed pixels, and new near-black boundary-ring pixels. Final-center frames 84..89 have `changed_pixels=0` and `maximum_channel_delta=0`. Observed requested maxima are `3.0` x and `2.0` y; smoothed maxima are `2.9402262826882923` x and `1.9602204308185094` y.

## Commit and Scope

Implementation/evidence commit SHA: `51f2524def59de7937dd582ede6594f9b70be0b1`.

Changed Task N3 files:

- `.superpowers/sdd/progress.md`
- `.superpowers/sdd/neutral-eye-task-3-report.md`
- `assets/rig/v1/source/eye-neutral-v1/authoring.json`
- `qa/neutral-eye-v1/preview-v2/eye-follow.gif`
- `qa/neutral-eye-v1/preview-v2/stats.json`
- `tests/test_neutral_eye_layers.py`
- `tests/test_neutral_eye_preview.py`
- `tools/build_neutral_eye_layers.py`
- `tools/build_neutral_eye_preview.py`

Visual inspection was not performed; automated containment, exact-center, timeline, and byte-reproducibility validation were performed. No N3-specific concerns remain; the test suite reports existing Pillow `getdata` deprecation warnings.

Runtime cursor acquisition, head assets, blink, tilt, packaging, EXE, and R5 completion were not started.

## Independent-Review Fix Follow-up

RED command:

```bash
python -m pytest tests/test_neutral_eye_layers.py -q
```

Result: `2 failed, 30 passed, 590 warnings in 25.99s`. The failures were intentional: the submitted candidate evidence still declared the old `±1.5/±1.0` extrema, and the contact-sheet caption had no `MOTION_LIMITS`-derived helper. The new regression test also demonstrates the prior RGBA `getbbox()` blind spot: a pure RGB change with unchanged alpha has a default bounding box of `None`, but is detected with `alpha_only=False`.

Fixes:

- Rebuilt the committed `qa/neutral-eye-v1/candidate/` evidence with the current builder. Its exact static extrema, statistics, and contact sheet now use `±3.0/±2.0`; preview-v1 remains unchanged.
- Changed the five-pose fixed-region test to use `MOTION_LIMITS` extrema, and made the aperture-containment assertion RGB-aware with `getbbox(alpha_only=False)`.
- Added `motion_limit_caption()`, formatting the footer directly from `MOTION_LIMITS` rather than hardcoding values.

Focused command:

```bash
python -m pytest tests/test_neutral_eye_layers.py tests/test_neutral_eye_preview.py -q
```

Result: `50 passed, 3021 warnings in 52.06s`.

Full command:

```bash
python -m pytest -q
```

Result: `50 passed, 3021 warnings in 52.31s`.

Independent `mktemp -d` rebuilds byte-compared all seven candidate files and both preview-v2 files successfully.

- Candidate `center.png`: `c73ce65333b14a4d42fde5bb6cb2fe33c4212ab763e619b0e806ec311c2e9178`
- Candidate `left.png`: `d34d6468b3d44f2d8bb4860cdbd2c426adbbd12b3e6c26458e5b7270a241bbcc`
- Candidate `right.png`: `1ce97de3a08af044ad92454711e553a691d3a2e42c2fcee40ba01162efa9c1fe`
- Candidate `up.png`: `c1815545366519de8b94c387fb201b861e40677826dba9282aa4a65ff9177b28`
- Candidate `down.png`: `25a06fb19e3dbc53d3dbb924ab3d41ab24ea18a2deb503e68e6d9ebfac913aab`
- Candidate `layer-contact-sheet.png`: `94737ee674e772ffe9635f47ed1e42abc5fedd2b5dde0e8fc9dcbc1b44823329`
- Candidate `stats.json`: `c3a4a161fe2f3ea6295f1a98e7e5294fd327a23de9011f9fcc73fd4f35735297`
- Preview-v2 `eye-follow.gif`: `66adaaabd232c71b4e6b35a7be46f9bc2d080a578aea441fa900ae3dc8b6dbdf`
- Preview-v2 `stats.json`: `0d1788e3368334c2d037f5e3535cbb6eb80244d793bf2593276e9a171a46585f`

Independent-review fix commit SHA: `05198b8996c9996efff596072165c69cd8e9ac04`.

## Final-Branch Review Fix Follow-up

RED command for maximum finite cursor coordinates:

```bash
python -m pytest tests/test_neutral_eye_preview.py -q
```

Result: `8 failed, 18 passed, 2431 warnings in 27.43s`. The eight new `sys.float_info.max` axial and signed-diagonal cases returned non-finite values under the prior multiplication/hypotenuse order.

RED command for the stale R5 evidence status:

```bash
python -m pytest tests/test_neutral_eye_layers.py::test_contact_sheet_writes_required_static_evidence_and_stats -q
```

Result: `1 failed, 47 warnings in 2.21s`; it correctly found the obsolete `BLOCKED pending explicit static visual approval` status.

`cursor_target` now normalizes finite nonzero coordinates by `max(abs(dx), abs(dy))`, computes the unit direction from the scaled vector, and derives saturation without materializing an overflowing distance. All finite coordinate/radius inputs remain accepted. The largest-finite single-axis and all four signed-diagonal inputs now produce finite, bounded, directionally correct results. Existing zero, proportional, saturation, and continuity coverage remains green.

The candidate `r5_status` now states: `N1 static eye layers accepted; organic-head R5 center visual gate remains unapproved and blocked.` Candidate evidence was deterministically regenerated. Its PNG evidence hashes remained unchanged; its `stats.json` changed only for the corrected status. Preview-v2 was independently rebuilt: `eye-follow.gif` remained byte-identical, while `stats.json` changed only because the safe equivalent floating-point calculation records slightly different target/offset decimal representations.

Focused command:

```bash
python -m pytest tests/test_neutral_eye_layers.py tests/test_neutral_eye_preview.py -q
```

Result: `58 passed, 3021 warnings in 51.35s`.

Full command:

```bash
python -m pytest -q
```

Result: `58 passed, 3021 warnings in 51.53s`.

Independent `mktemp -d` rebuilds byte-compared all seven candidate files and both preview-v2 files successfully. Relevant output SHA-256 values:

- Candidate `stats.json`: `91ee82b3cd3387f15140c509cbdd0f5be0ac6e4dfc8b2a559ffe82c5140388ab`
- Preview-v2 `eye-follow.gif`: `66adaaabd232c71b4e6b35a7be46f9bc2d080a578aea441fa900ae3dc8b6dbdf`
- Preview-v2 `stats.json`: `e219ad4cab9b02ae3e72662a0401234fb307d9ab19eac94deffc8e8ff51b3172`

Final-branch fix commit SHA: `970bdc27938b566cd6b26004c9e2eaaed29e383f`.

The existing validate/render TOCTOU issue remains a scope-deferred Minor; it was not expanded in this fix.

# Continuous Head-Neck Task 2 Report

This report records the original conservative-amplitude evidence. The current
published QA package supersedes its artifact hashes; see
`head-neck-amplitude-adjustment-report.md` for the user-approved 1.225 render
gain and current hashes.

## Scope

Task 2 is an offline, deterministic QA preview only. It adds the preview
builder, focused tests, and the ten-file evidence package under
`qa/head-neck-continuous-v1/`. The build revalidated that the runtime asset
tree was unchanged, created no directional runtime assets, and did not wire
the deformation into the Windows runtime or an EXE.

Human visual approval has not been granted. Runtime integration and packaging
remain blocked.

Implementation and evidence commit: `fc511d1`. Post-review repository-output
confinement fix: `09e6c73`.

## TDD evidence

### RED

The evidence-review correction first added
`test_metric_summaries_preserve_signed_orientation_and_semantic_bounds` before
changing the builder. Command:

```text
PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_continuous_preview.py::test_metric_summaries_preserve_signed_orientation_and_semantic_bounds
```

It failed with one failure in 0.46 seconds. The first missing contract was
`KeyError: 'signed_source_area_max'`. This established that the prior JSON
recorded absolute mesh area bounds but did not expose the signed orientation
bounds required for independent audit. The same test also specifies explicit
per-point and overall semantic displacement minima and maxima.

The path-safety correction separately added runtime-output and broken-symlink
tests before changing production. The two directed tests initially failed:
the protected runtime tree was accepted as an output, and there was no runtime
tree snapshot interface from which to derive the unchanged claim. The final
three-test safety group passed in 0.21 seconds after the minimal correction.

A final reviewer then proved that other repository directories such as `src`,
`.git`, and `assets/keyframes` could still be selected as output. A new test
first failed with `DID NOT RAISE`. The final preflight permits only the exact
`qa/head-neck-continuous-v1` path inside the repository while retaining
external temporary-directory builds. The three directed path tests then
passed in 0.26 seconds.

### GREEN

The builder now retains its existing absolute area gates and additionally
records the signed source area, signed area ratio, and orientation-sign range.
It also summarizes the already computed four-cardinal semantic samples without
changing the trajectory, filters, mesh, deformation, or rendered pixels.

Focused metric test:

```text
PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_continuous_preview.py::test_metric_summaries_preserve_signed_orientation_and_semantic_bounds
```

Result: `1 passed in 0.36s`.

Independent temporary-directory build test plus the metric test:

```text
PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_continuous_preview.py::test_metric_summaries_preserve_signed_orientation_and_semantic_bounds \
  tests/test_head_neck_continuous_preview.py::test_build_has_exact_allowlist_mesh_gates_and_scope
```

Result: `2 passed in 67.93s`.

Final complete Task 2 suite after all path-safety, metric, report, and evidence
corrections:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_continuous_preview.py
```

The final post-review run, including repository-output confinement, completed
with `14 passed in 194.58s`.

Applicable pre-existing non-Tk regression paths were also rerun after the
20-pixel deformation correction and all Task 2 corrections: `316 passed,
4 skipped in 78.20s`. The four skips are platform-gated Windows tests.

Final deterministic evidence build:

```text
PYTHONPATH=src:. python tools/build_head_neck_continuous_preview.py \
  --asset-dir assets/rig/v1/source/eye-neutral-v1 \
  --canonical assets/rig/v1/source/canonical-idle.png \
  --output-dir qa/head-neck-continuous-v1
```

Result: exit code zero; wall time `65.836s`.

Static verification:

```text
PYTHONPATH=src:. python -m py_compile \
  tools/build_head_neck_continuous_preview.py \
  tests/test_head_neck_continuous_preview.py
git diff --check
```

Both commands exited zero.

## Exact metrics

### Mesh geometry and orientation

- ROI: `[0,160,320,432]`
- Topology: 25 by 19 vertices, 24 by 18 cells
- Absolute source area: `70.0..1960.0`
- Absolute source/output area ratio: `0.8540474111728453..1.1414460222066607`
- Signed source area: `-1960.0..-70.0`
- Signed source/output area ratio: `-1.1414460222066607..-0.8540474111728453`
- Orientation sign: `-1..-1`, consistent with the required upper-left,
  lower-left, lower-right, upper-right source-quad ordering; no flip occurred

### Semantic displacement summary

All values are source pixels and are magnitudes over the four unit-cardinal
poses. Overall minimum is `0.0` at the pinned chest points; overall maximum is
`3.4000009560634434` at the nose.

| Semantic point | Minimum | Maximum |
|---|---:|---:|
| left ear tip | 0.7421522995677924 | 1.7514984957986572 |
| right ear tip | 0.7184375050483227 | 1.6955138465961124 |
| left ear root | 1.63035671038861 | 2.6048805566328426 |
| right ear root | 1.6033024328489813 | 2.52896105224264 |
| left eye | 1.8112884451664586 | 2.815410299429206 |
| right eye | 1.7276279076815881 | 2.712671086040876 |
| nose | 2.5 | 3.4000009560634434 |
| jaw | 1.4520186647899573 | 2.3076392344559227 |
| left neck root | 1.3144548380458616 | 2.1311665868809473 |
| right neck root | 1.117958651741991 | 1.818371215852784 |
| left mid-neck | 0.07677617245487647 | 1.1084048961603532 |
| right mid-neck | 0.08429793203177452 | 1.2465948653665864 |
| left chest | 0.0 | 0.0 |
| right chest | 0.0 | 0.0 |

Horizontal nose minimum is `3.4000009560634434`. Horizontal neck-root average
is `1.9747689013668657`, with range
`1.818371215852784..2.1311665868809473`. Nose minus neck-root average is
`1.4252320546965778`, proving non-rigid differential motion.

### Timeline, motion, and image gates

- Target extrema: horizontal `0.85`, vertical `0.85`
- Focus magnitude maximum: `0.8464616786387498`
- Head magnitude maximum: `0.8071218629025431`
- Eye residual extrema: horizontal `1.8218251004786383`, vertical
  `1.1535296723074335`
- Maximum target step: `0.07054183813443077`
- Maximum head-state step: `0.052096227285752916`
- Step response: focus reaches 90 percent at frame 4, head at frame 15, lead
  `11` frames
- Head-only changed pixels at audit extrema: horizontal negative `52842`,
  horizontal positive `52877`, vertical negative `50171`, vertical positive
  `49548`
- Eye-crop edge-energy ratio range:
  `0.9857894588738498..1.0419006539975073`
- Total rendered eye-anchor travel: horizontal `3.931979993816433`, vertical
  `2.5709727906091584`
- Outside ROI, outside dynamic support, protected right strip, and protected
  lower band: maximum changed pixels `0` for each
- Transparent RGB violations: `0`
- Alpha-positive support ratio:
  `0.9975258352014872..1.0059461971676964`
- Semitransparent support ratio: `0.8103049907578558..1.0`
- Rendered eight-connected enclosed transparent holes: maximum 15 components,
  42 pixels total, largest 11, significant components of at least 16 pixels
  `0`
- Rendered four-connected telemetry: maximum 119 components, 357 pixels total,
  largest 48, significant components `3`; this remains diagnostic only under
  the approved quantization rule
- Frames 228 through 239: exact center identity, changed pixels `0`, maximum
  channel delta `0`
- Normal GIF duration: `8000ms`; slow GIF duration: `32000ms`; loop value `0`

## QA artifact hashes

The `outputs` object inside `stats.json` intentionally excludes `stats.json`
to avoid a self-hash. The final row is the separately computed SHA-256 of the
finished JSON file.

| Artifact | SHA-256 |
|---|---|
| center-difference.png | 04e6bdc8c9b4e94186c8d71fe4e665bba653c9053e4cc3c8a3159ce4923c5f4d |
| contact-sheet-checker.png | 09cca4ef9097108217ddc47dc99d1df07e6f926a1993167d984f19dba03f2037 |
| contact-sheet-dark.png | 67f95d6f9e0da794bdd29812179ea76e89fe7a47dbcc56d58fcf23e60b523d4c |
| contact-sheet-gray.png | 091b0bd372b582050b9baef9825147a86d4ae23397e4102c69f3e2367cc0a899 |
| contact-sheet-light.png | 687df92b6fa00e0ff4d5338ca69a402baa112fc03141c68ff190a1f36ee5e505 |
| head-neck-follow-4x.gif | 3b56be8d965ab6fb9db0fb429bf7a0e4d6f74b13df1f9c5598b37da427065fa5 |
| head-neck-follow.gif | af754182c8a8eb0651ff93ea2c3db34d5f0e91509aa3a5bb0514933d22520f6c |
| landmark-overlay.gif | a0f206b06fe37624b1083856217bce71a557362813c936dff5d47aa4c7c16b56 |
| seam-closeups-400pct.png | a4a6b3dedfcb5cf09e3dddc34f5743a8c5598db55d9666c843ef8e31ee8cf303 |
| stats.json, separately computed | b713c0ffff8bbeeb3a56d16b33b5a0e84a9607e7555c35c98531719dbc611c32 |

## Remaining human visual decisions

Automated gates cannot approve either of these questions:

1. Whether the perceived amplitude, continuous arbitrary-angle motion, and
   eye-leads/head-follows timing look natural rather than too subtle, rubbery,
   or delayed.
2. Whether the ear roots, eye rims, whiskers, jaw, collar, and neck remain free
   of objectionable stretching, seams, dark fringes, holes, or background
   flashes on the light, dark, gray, and checker evidence, especially in the
   four-times-slow GIF and 400-percent closeups.

Until the user explicitly approves both visual questions, Task 2 is evidence
only and must not be described as runtime-ready.

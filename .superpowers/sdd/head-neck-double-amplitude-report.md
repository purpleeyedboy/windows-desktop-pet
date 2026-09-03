# Continuous Head-Neck Double-Amplitude Report

## Scope and decision

The user explicitly requested that the current head/neck deformation be
doubled again. The deformation core therefore applies an exact `2.0` gain on
top of the already approved `1.225` offline render-state gain. Eye offsets,
eye/head time constants, arbitrary-angle cursor path, body protection,
direction-free rendering, and exact-center behavior are unchanged.

This remains offline QA only. Runtime integration, packaging, workflows,
keyframes, eye assets, and EXE files are unchanged.

Implementation and rebuilt evidence commit: `27cb976`.

## TDD and safety evidence

Tests were changed before production to require an exact `2.0` deformation
gain, doubled semantic travel, and a non-flipped `0.60..1.40` strong-warp mesh
area envelope. RED command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_deformation.py::test_user_requested_deformation_gain_is_exactly_double \
  tests/test_head_neck_deformation.py::test_sampling_offsets_meet_signed_fixed_semantic_travel_contract \
  tests/test_head_neck_deformation.py::test_every_mesh_is_finite_in_bounds_convex_and_within_area_limits
```

RED result: `2 failed, 6 passed in 0.41s`. The gain interface was absent and
the nose still measured the old `3.4000009560634434px` unit displacement.

After the minimal core change, all 42 deformation tests passed in 2.03 seconds.
The first real 240-frame build then stopped at the old total rendered-eye-anchor
envelope, correctly exposing the consequence of moving the eye sockets with a
larger head warp. The actual totals were measured at horizontal
`7.190584938050609px` and vertical `4.670333387551542px`. The evidence envelope
was updated to `8.0px` by `5.5px`; the eye texture offsets themselves were not
increased. The second real build completed successfully.

Final verification:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_continuous_preview.py
15 passed in 189.17s

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_deformation.py tests/test_neutral_eye_compositor.py
78 passed in 6.22s

python -m py_compile src/desktop_pet/head_neck_deformation.py \
  tools/build_head_neck_continuous_preview.py \
  tests/test_head_neck_deformation.py \
  tests/test_head_neck_continuous_preview.py
git diff --check
```

Compilation and diff checking exited zero.

## Current metrics

- Core deformation gain: `2.0`
- Offline render-state gain: `1.225`
- Horizontal negative extremum nose travel: `6.6929077048293735px`
- Horizontal negative extremum neck-root travel: `4.195188900585429px` and `3.5794528428130503px`
- Vertical extrema nose travel: approximately `4.92px`
- Mesh source/output area ratio: `0.6424158441225021..1.3466952718629581`
- Mesh orientation: unchanged and never flipped
- Head-only changed pixels: `50706..53862`
- Alpha-positive support ratio: `0.9904997539504621..1.0096506096560773`
- Semitransparent support ratio: `0.8163123844731978..1.0`
- Eight-connected significant enclosed transparent holes of at least 16px: `0`
- Eye-crop edge-energy ratio: `0.9280049566294919..1.0496029800999902`
- Total rendered eye-anchor travel: horizontal `7.190584938050609px`, vertical `4.670333387551542px`
- Outside ROI, outside dynamic support, protected strips, and transparent-RGB violations: `0`
- Forced center frames 228 through 239: exact canonical identity

Manual inspection of the light and dark sheets plus 400-percent closeups found
no new interior black seam, detached ear root, neck gap, or body drift. This
strength is intentionally much less conservative and can read as rubbery; only
the user can approve that visual tradeoff. The pre-existing thin cool silhouette
halo remains visible under magnification and is not described as fixed.

## Current QA hashes

| Artifact | SHA-256 |
|---|---|
| center-difference.png | 04e6bdc8c9b4e94186c8d71fe4e665bba653c9053e4cc3c8a3159ce4923c5f4d |
| contact-sheet-checker.png | e55a1a0869524b7c0a5febf07bd6f97eb3be8f59917613a4477d6cc8bf36eb1e |
| contact-sheet-dark.png | 6f6c2318083c852b66103b370d72e528da61a4e649c85f35a5a6d263f0494a86 |
| contact-sheet-gray.png | f3a642f0a3ab14363b1bad7d5f8b0f31232136b3ad9753e2a31159561e539a92 |
| contact-sheet-light.png | b60e742368d46e2744cb7793e2f729d77670d35a464055e1d14c30e7396b742a |
| head-neck-follow-4x.gif | bcd9bb9db82934a143dbdd48e75469e6ceff59012d3a5e5ab4d30202d8cbd63f |
| head-neck-follow.gif | 84dd44fa53fbc5291055b8011fa346133faf61f91fdaf663116d4892f972b606 |
| landmark-overlay.gif | d854336d91e98efe6211398e1de4851824c71fef2bda3944baa30261297c8de0 |
| seam-closeups-400pct.png | ccec6e28a0d2c59afbea70d508e9b4dd417907b85792698eddce896b053185fd |
| stats.json, independently computed | 58936383ef142e7c5c300c9e3a47108f6e0c0101737111520e2d62d89739ed1b |

## Stop gate

Runtime head-follow integration and a new EXE remain blocked until the user
reviews this double-amplitude preview and explicitly approves the stronger
motion and fringe quality.

# Continuous Head-Neck Amplitude Adjustment Report

This report records the intermediate 1.225 render-gain increment. The current
published QA package supersedes these hashes with the later user-requested
double deformation documented in `head-neck-double-amplitude-report.md`.

## Scope and decision

The user approved a moderate increase to the offline head/neck deformation
amplitude. This increment changes only the mapping from the already-smoothed
head state to the offline deformation pose. It does not change the eye motion,
focus/head time constants, 240-frame target path, deformation mesh core,
runtime integration, packaging, workflows, keyframes, or any EXE.

The reviewed render gain is `1.225`. The maximum smoothed head-state magnitude
remains `0.8071218629025431`; the maximum rendered deformation pose becomes
`0.9887242820556152`, still inside the compositor unit disk. The eye residual
continues to use the original unamplified head state, so eye amplitude and the
11-frame eye-lead timing remain unchanged.

Implementation and rebuilt evidence commit: `81cb4d9`.

## TDD evidence

The new focused test was written before production support. RED command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_continuous_preview.py::test_reviewed_render_gain_increases_head_without_changing_filter_state
```

RED result: one failure in 0.27 seconds with `AttributeError` because
`HEAD_RENDER_GAIN` did not exist.

After the minimal implementation, the same test passed in 0.27 seconds. Final
verification after rebuilding the evidence:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_continuous_preview.py
15 passed in 195.20s

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m pytest -q \
  tests/test_head_neck_deformation.py tests/test_neutral_eye_compositor.py
77 passed in 6.57s

python -m py_compile tools/build_head_neck_continuous_preview.py \
  tests/test_head_neck_continuous_preview.py
git diff --check
```

Compilation and diff checking exited zero.

## Current metrics

- Render gain: `1.225`
- Maximum rendered head magnitude: `0.9887242820556152`
- Maximum rendered head step: `0.06381787842504727`
- Mesh source/output area ratio: `0.8212098328270169..1.1732832104541058`
- Estimated horizontal nose travel at the preview extremum: `3.3616635042722343px`
- Estimated horizontal average neck-root travel: `1.9525019642297106px`
- Head-only changed pixels: `49925..53112`
- Alpha-positive support ratio: `0.9971977691508557..1.0068620482257093`
- Semitransparent support ratio: `0.8103049907578558..1.0`
- Eight-connected significant enclosed transparent holes of at least 16px: `0`
- Eye-crop edge-energy ratio: `0.9763908039508118..1.0614505580685367`
- Total rendered eye-anchor travel: horizontal `4.435234723775556px`, vertical `2.895404275217224px`
- Outside ROI, outside dynamic support, protected right strip, protected lower band, and transparent-RGB violations: `0`
- Forced center frames 228 through 239: exact canonical identity

Manual inspection of the light/dark contact sheets and 400-percent closeups
found no new interior black seam, detached ear root, neck gap, or body drift.
The thin cool dark silhouette halo already identified in the conservative
preview remains visible at 400 percent and therefore remains part of the human
visual decision rather than being described as fixed.

## Current QA hashes

The `stats.json` output table excludes its own hash. Its independent SHA-256
is listed last.

| Artifact | SHA-256 |
|---|---|
| center-difference.png | 04e6bdc8c9b4e94186c8d71fe4e665bba653c9053e4cc3c8a3159ce4923c5f4d |
| contact-sheet-checker.png | e9f73fff8f4eaae5a567d295a1b28938e168094fd50a94edd73a68a0cbda8395 |
| contact-sheet-dark.png | 56181055702d9237506adefb0e2c8e9d2e3a87baa554802810d16fd3b4b13161 |
| contact-sheet-gray.png | 7e97ca9c7008a0694e8e52bb1b6f3636e6eb9825d411f53a4b66c2b77e6a5729 |
| contact-sheet-light.png | 85dd936f71044677701936707efd855a5e2aa5e1ca2adc07e2577e111e690e99 |
| head-neck-follow-4x.gif | 27f35afe1d5c6bcd8d85d4eca062f506ee606400dee419e2b4241f3aa36db077 |
| head-neck-follow.gif | b274f881191b69e2a3e06720dd53c20d0b988f4588accd408e8d4bc447b522b4 |
| landmark-overlay.gif | 200e8bbf5b931ec2e7869409bb65e94dbb023914bbe40df0accac983beaad248 |
| seam-closeups-400pct.png | 7df8ee7a576bd859f47e9ae1c2c32c042db25fb63e98f90b5c1f5f9e58e3e120 |
| stats.json, independently computed | 1a0ce1141111165b9e6f280a8441489effba71e8a0027013b9bebdc9c02a8c99 |

## Stop gate

This remains an offline visual proof. Runtime head-follow integration and a
new EXE remain blocked until the user reviews the increased-amplitude GIF and
explicitly approves its motion and fringe quality.

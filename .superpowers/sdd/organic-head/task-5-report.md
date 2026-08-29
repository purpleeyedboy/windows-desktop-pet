# Task 5 Report: Center Visual QA and User Gate

Status: **BLOCKED — visual rejection; no commit created**

## TDD receipt

- RED: `tests/test_rig_center_qa.py` was written before the production module. The focused run stopped at collection with the expected `ModuleNotFoundError: No module named 'tools.rig_center_qa'`.
- GREEN: after the minimal generator was added, `tests/test_rig_center_qa.py` passed: `1 passed in 0.77s`.
- The first two GREEN attempts did not exercise the implementation because pytest could not access its sandboxed temporary directory. The same test was then rerun with authorized system-temp access and passed.

## Real `center-stats.json` summary

- Artifacts: `center-contact-sheet.png`, `center-backgrounds.png`, `center-closeups.png`, `center-difference.png`, `center-stats.json`.
- Exact recomposition: `matches=true`, `changed_pixels=0`, `maximum_channel_delta=0`.
- Alpha: `alpha_zero_rgb_violations=0`, `outer_border_transparent=true`, `canonical_composite_alpha_matches=true`; canonical, four layers, and composite are each RGBA 512×768 with zero hidden-RGB violations and transparent outer borders.
- Canonical SHA-256: `48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7`.
- Layer SHA-256:
  - body base: `05f87dc73bc2afad2934d091e89b7d3ac6c5fce960227d7af1309ece25451deb`
  - head/neck: `b1fe1a14208a63506b1c0b1a5b34db02a21e94554c1ff8f2e2cd427a433556ff`
  - left eye: `efcf482cf657f1360680fc8de73f8985447a80e6d1001d436f01ae7a53e5da69`
  - right eye: `3ccbc026cd84f9deeff32b0d6e760500fd17952e314cc47d0f734ec0b76fb9ae`
  - composite: `38c39b03c36eff983a023fc98ab6fbfefaad6098a43d729e000017a48fbfb55c`
- Mask boxes: left `[60, 325, 105, 381]`; right `[139, 319, 185, 376]`.
- Mask SHA-256: left `8e499cb53f4f144c412a36193835bd4737582f8035d1ed8d8e7ab1f15f31dbdd`; right `ad2b6f7e88702d5074e801840aa410347549db5e9bcbe329e84974851937484f`.
- AI containment: body fill outside mask `0`; eye fill outside masks `0`; `passed=true`.

## Focused verification

- `tests/test_rig_center_contract.py tests/test_build_rig_center_guides.py tests/test_assemble_rig_center.py tests/test_rig_center_qa.py`: `11 passed in 4.02s`.
- Runtime scan of `src/desktop_pet/*.py` for `numpy|cv2|opencv`: `NO_MATCHES`.

## QA artifact inventory

| Artifact | Dimensions / mode | SHA-256 |
|---|---:|---|
| `center-contact-sheet.png` | 1030×284 RGB | `10b18f4cf89f585fcf13107d1f639341917628cd881c2dd9620c768ff197374d` |
| `center-backgrounds.png` | 587×1260 RGB | `34c8057056d692362c993e2db9701dcb83700161acd4c094e8bfa7bd7ae16ec7` |
| `center-closeups.png` | 1872×1576 RGB | `bd5aa77cc4e67cb9b5af97de33e5b05410f6a3104402924582ba2a78dc3b01d7` |
| `center-difference.png` | 512×768 RGB | `8df9e719931d126d51fa607d315c3bc743fbf2d3ccb5b0d75b2d7f3208672cf5` |
| `center-stats.json` | 2876 bytes JSON | `8a17151d662f1f2299d264cdf63ef6f9b9b242e6a2073589ba938b425860a6b8` |

All four PNG artifacts were independently inspected at original resolution. The JSON artifact was independently read and checked against the interface fields.

## Visual rejection checklist

- **REJECT — reconstructed shoulder/chest fur:** the body-base panel in `center-contact-sheet.png` contains a conspicuous rounded shoulder/chest fill. Its soft, painted appearance and texture direction/sharpness do not blend naturally with the surrounding fur.
- **REJECT — eye underlay:** the head/neck panel in `center-contact-sheet.png` retains a dark iris/pupil-like form in the left eye socket. The right underlay is also visibly eye-colored instead of reading as neutral hidden socket fill.
- Head/neck cut line, transparent gap, double dark edge, or new pink/purple fringe: the exact center composite and 400% canonical/composite comparisons show no new center difference; however this does not override the two rejected source-layer findings above.
- Eye-patch clipping of eyelids/nose fur: no center-composite difference was visible or measured, but the underlay rejection prevents approval.
- Recombined center identity: pixel-exact and visually identical in the QA comparison.
- Feet baseline or pixels outside approved masks: no composite change was visible; exact recomposition and containment counters are zero.
- Difference image: uniformly black, consistent with zero decoded drift.

## Commit and concerns

- Commit: none. The brief forbids committing a visually rejected increment.
- R2/R3/R4 assets and masks were not modified.
- The rejected evidence remains in `qa/rig-v1/` for controller review. No directional pose work was started.
- Required next action: controller assigns rollback/repair of the two Task 3 AI fill sources or Task 2 internal masks, then reruns Tasks 4–5. The current R5 implementation and evidence are intentionally left uncommitted.

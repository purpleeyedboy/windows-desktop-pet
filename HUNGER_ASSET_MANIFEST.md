# V2.1-HUNGER Asset and Runtime-Layer Manifest

## Reused approved binary assets (byte-preserved)

- `assets/rig/v1/source/eye-neutral-v1/{authoring.json,body-backplate.png,eye-left-mask.png,eye-left.png,eye-right-mask.png,eye-right.png,head-cutout.png,underlay.png}` packaged at `assets/rig/v1/runtime/eye-neutral-v1`.
- Existing `assets/keyframes`, `assets/bubble`, `assets/fonts`, and `assets/dialogue` trees.

## New runtime-only local layers (no binary asset files)

- Mouth interior: deterministic RGBA ellipse anchored below the current-pose eye midpoint.
- Tongue: deterministic lower-mouth RGBA ellipse.
- Tears: two deterministic RGBA drop layers anchored below current-pose eye boxes.
- Layers are recreated from the current approved compositor frame on every presentation frame; no accumulated transform or source-byte mutation occurs.

These program-drawn layers remain a functional fallback, not accepted final
art.  The replaceable layer/anchor contract is documented in
`docs/hunger-local-art-contract.md`; no new binary asset is included here.

## Call chain

`run_desktop_pet.py` → `desktop_pet.main.main` → PR5 `create_application_services` → shared UTC/StateStore/ActivityCoordinator → `HungerService.snapshot` → `HungerRuntime._tick` → coordinator token/version validation → `PetWindow.present_hunger` → `compose_hunger_effect` → `LayeredWindowRenderer.render`.

## Current integration status

The runnable entry point creates one `ApplicationServices`, adapts its one
`AtomicJsonStore` through `SharedHungerStatePort`, and uses its `RuntimeContext`
and `ActivityCoordinator`. The source handoff identity is recorded as
`e178f371bd2da1c0b4e892609acfdf79bfcab450`; this records provenance and does
not claim that commit as a Git ancestor of this branch.

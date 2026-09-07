# V2.1-HUNGER Asset and Runtime-Layer Manifest

## Reused approved binary assets (byte-preserved)

- `assets/rig/v1/source/eye-neutral-v1/{authoring.json,body-backplate.png,eye-left-mask.png,eye-left.png,eye-right-mask.png,eye-right.png,head-cutout.png,underlay.png}` packaged at `assets/rig/v1/runtime/eye-neutral-v1`.
- Existing `assets/keyframes`, `assets/bubble`, `assets/fonts`, and `assets/dialogue` trees.

## New runtime-only local layers (no binary asset files)

- Mouth interior: deterministic RGBA ellipse anchored below the current-pose eye midpoint.
- Tongue: deterministic lower-mouth RGBA ellipse.
- Tears: two deterministic RGBA drop layers anchored below current-pose eye boxes.
- Layers are recreated from the current approved compositor frame on every presentation frame; no accumulated transform or source-byte mutation occurs.

## Call chain

`run_desktop_pet.py` → `desktop_pet.main.main` → PR5 `create_application_services` → shared UTC/StateStore/ActivityCoordinator → `HungerService.snapshot` → `HungerRuntime._tick` → coordinator token/version validation → `PetWindow.present_hunger` → `compose_hunger_effect` → `LayeredWindowRenderer.render`.

## Current integration gate

`foundation_commit=PENDING_PR5`; `build_hunger.ps1` intentionally refuses packaging until the approved PR5 foundation module exists and the same foundation commit is recorded. This prevents an old-cat or parallel-state candidate from being published as complete.

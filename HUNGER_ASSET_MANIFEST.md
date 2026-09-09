# V2.1-HUNGER Asset and Runtime-Layer Manifest

## Reused approved binary assets (byte-preserved)

- `assets/rig/v1/source/eye-neutral-v1/{authoring.json,body-backplate.png,eye-left-mask.png,eye-left.png,eye-right-mask.png,eye-right.png,head-cutout.png,underlay.png}` packaged at `assets/rig/v1/runtime/eye-neutral-v1`.
- Existing `assets/keyframes`, `assets/bubble`, `assets/fonts`, and `assets/dialogue` trees.

## Required authored local-frame asset set

- Runtime requires `assets/hunger/v1/manifest.json` plus its listed transparent
  PNG local frames for `hungry`, `severe`, and `critical` sequences.
- Every decoded frame must use the approved 512×768 canvas and bottom-center
  `[256,768]` anchor and provide an explicit
  `duration_ms`; the loader rejects missing, empty, or wrong-sized frames.
- Runtime placement is the rig's explicit no-scale transform: the authored
  512×768 frame is placed at `[64,0]` inside the 640×768 padded head-follow
  canvas. No 512/640/672 width is treated as interchangeable.
- Full frames replace the display during the expression so old and new mouths
  cannot overlap. Interruption returns to the current live approved pose and
  never transforms a prior output frame.

The prior program-drawn ellipse/polygon mouth, tongue, and tear substitute has
been removed from the runtime. The required authored frames are not present in
this commit because this execution environment has no image-generation tool;
the build script now refuses to package until validated frames are supplied.

## Call chain

`run_desktop_pet.py` → `desktop_pet.main.main` → PR5 `create_application_services` → shared UTC/StateStore/ActivityCoordinator → `HungerService.snapshot` → `HungerRuntime._tick` → coordinator token/version validation → `PetWindow.present_hunger` → `compose_hunger_effect` → `LayeredWindowRenderer.render`.

## Current integration status

The runnable entry point creates one `ApplicationServices`, adapts its one
`AtomicJsonStore` through `SharedHungerStatePort`, and uses its `RuntimeContext`
and `ActivityCoordinator`. The source handoff identity is recorded as
`e178f371bd2da1c0b4e892609acfdf79bfcab450`; this records provenance and does
not claim that commit as a Git ancestor of this branch.

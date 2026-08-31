# Runtime Continuous Head-Neck Integration Plan

Date: 2026-08-31

## Goal

Integrate the user-approved continuous head and upper-neck inverse deformation into the existing Windows mouse-follow runtime. Preserve arbitrary-angle cursor tracking, 60 ms eye response, 220 ms head response, 1.225 head render gain, 0.35 eye/head compensation, and the approved doubled deformation core.

## Scope

- Runtime source integration only.
- Reuse `ContinuousHeadNeckCompositor`; do not generate or select directional images.
- Preserve exact center, recenter-before-action, action playback, renderer fallback, drag/resize geometry, and shutdown ownership.
- Keep blink, tilt, new art, packaging, EXE, signing, and release out of scope.

## Task 1: Coordinated continuous motion

- [x] Add a backward-compatible coordinated eye/head output mode to `EyeMotionController`.
- [x] Drive both filters from the same live cursor vector.
- [x] Prove exact constants, arbitrary-angle continuity, eye lead, radial limits, center convergence, pause/resume, and exact center synchronization.

## Task 2: Runtime ownership and composition

- [x] Extend `RuntimeEyeSession` with an explicit opt-in head-follow mode.
- [x] Track and recenter eye and head poses transactionally.
- [x] Route the coordinated pose through a cached-center adapter into `ContinuousHeadNeckCompositor`.
- [x] Prove compose/display failures retain the existing disabled fallback and leave no live scheduler owner.

## Task 3: Production wiring and verification

- [x] Load the neutral eye compositor once, wrap it with the continuous head-neck compositor, and enable head-follow in `PetWindow`.
- [x] Run focused controller, session, window, asset, deformation, and main tests.
- [x] Run the applicable non-Tk regression suite, compilation, forbidden directional-asset scan, and `git diff --check`.
- [x] Record source performance and progress. Do not build an EXE in this increment.

## Acceptance

- One live cursor vector controls arbitrary continuous angles.
- Eyes visibly lead; head and neck follow smoothly with the approved amplitude.
- Center is pixel exact and action frames still start and end at the cached center.
- No direction-count quantization, new generated assets, head cutout translation, blink, tilt, or packaging work is introduced.

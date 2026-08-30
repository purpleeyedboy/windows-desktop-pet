# Runtime Eye Follow — Whole-Increment Final Review Report

## Scope

- True remote baseline before publication: `48c9cb56ecc82029625929d267d6568fcfa0c756` on `codex/desktop-pet-6-frame-alpha`.
- Local reviewed head: `9685acb`.
- Meaningful review range: `894cabf..9685acb`, excluding `assets/keyframes/**` because `069c4be` only hydrates 18 PNGs already present at the remote baseline.
- R5, visual assets, QA evidence, dependencies, packaging, release, and EXE work remained out of scope.

## Review result

Six independent read-only review assignments covered:

1. continuous arbitrary-angle cursor mapping, smoothing, geometry scaling, and aperture clamping;
2. cached deterministic neutral-eye composition;
3. eye-session scheduling, lifecycle, fallback, and reentrancy;
4. action ownership, cancellation, frame identity, and phrase ordering;
5. hidden neutral-first startup, render-plus-geometry transactions, fallback, and shutdown;
6. full-increment scope, test quality, hydration boundaries, and publication safety.

The initial whole-increment review found two Important defects:

- eye and recenter schedulers did not close ownership under synchronous callbacks or scheduler exceptions;
- cancel callbacks could reenter while old lifecycle state was visible, overwrite stop, or leave paused/following state without a valid token.

No Critical findings were reported.

## Repairs

Commit `03d9041` added:

- scheduling sentinels, per-attempt slots, fired gates, post-return ownership checks, and generation invalidation;
- safe disabled/FALLBACK convergence for start, tick, recenter, completion, and action-finish scheduling hazards;
- token detachment before external cancellation;
- terminal/stopped publication before stop cleanup;
- recenter reservation before pause cancellation so nested request, pause, and resume calls are rejected;
- stale-callback isolation after before-queue and after-queue scheduler failures.

Commit `9685acb` aligned the Window integration test with the safe initial scheduler-failure contract: a successfully presented neutral frame may fall back to physical `jump/00`, while the unknown queued callback remains inert and close still completes eye → animation → bubble → root.

## Verification

- Eye controller and runtime focused: `148 passed`.
- Headless PetWindow integration: `27 passed`, `23 deselected`.
- Applicable non-Tk suite: `297 passed`, `3 skipped`.
- `git diff --check`: clean.
- Worktree after implementation commits: clean.
- Final original-finder re-reviews: Approved, `0 Critical / 0 Important / 0 Minor`.
- Final combined integration review: Approved, `0 Critical / 0 Important / 0 Minor`.

The host uses Pillow 12.3 and emitted 1,107 future deprecation warnings for `getdata()`. The project declares `Pillow>=11,<12`; real Pillow 11, real Tk/Windows renderer, multi-monitor, four-size performance, and human visual checks remain external gates.

## Publication constraint

Do not push or replay the local ancestry directly. Re-read the remote branch head and create the publication commit from the remote complete tree, overlaying only meaningful source, test, tool, plan, report, and progress blobs. Do not publish the local hydration commits or rewrite the 18 remote-existing action PNGs.

## Remaining status

R5 remains blocked. The current result is a source-checkout-only visible runtime probe. Head directions, blink, head tilt, packaging, release, and EXE work remain prohibited until the outstanding Windows and human visual gates are completed and separately approved.

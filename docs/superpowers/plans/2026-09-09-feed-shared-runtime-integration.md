# FEED shared runtime integration — 2026-09-09

This repair makes the existing six generated poses executable through the actual
V2.1 foundation. It is a candidate implementation, not Windows visual acceptance.

## Basis and ownership

- Feature source: PR13 `73a991d` (original FEED branch through `ab2c0cd`).
- Foundation: `f617765`; real graphic activity fix: `e361579`; context-menu priority protection: `6af8446`.
- One `ApplicationServices` is created by `main`; `PetWindow` and `FeedRuntime`
  receive that same object. No `foundation.api`, capability discovery, alternate
  state store, alternate runtime queue, or alternate STA worker is created.
- `FeedDragDropService` replaces the diagnostic OLE target before `PetWindow`
  registers its HWND. It retains Copy-only, single-path native snapshots.
- `HungerService` and `SharedHungerState` are the same two modules used by the
  hunger candidate. In a combined build, inject the existing hunger service into
  `FeedRuntime(..., hunger=...)`; do not create a second hunger owner.

## File transaction

Final owned confirmation -> final file identity/quote validation -> durable
Prepared -> shared STA operation -> verified COM progress receipt -> durable
RecycleConfirmed -> one atomic hunger/anchor/operation-ID commit -> durable
RewardApplied and Completed -> shared FEED_ANIMATION player.

Unknown/untrusted outcomes and stale callbacks enter NeedsReview without reward.
A failed durable write restores activity and retains the previous durable stage.
Replay never reissues a recycle operation, never infers success from a missing
path, and requires matching source identity plus trusted receipt before a reward.
A 30-second UI timeout quarantines in-flight Shell work; late evidence is review
only. Debug animation invokes no transaction, reward, identity inspection or file
operation. Only local Windows fixed-disk files accepted by the existing inspector
can reach confirmation; the inspector runs again on the worker before Shell.

## Animation and assets

The six-source text bundle is unchanged. The manifest now uses the compositor's
measured 640 x 768 canvas instead of the incompatible 672 x 768 canvas. Extraction
uses uniform scale and bottom alignment. Actual pose order is closed, half-open,
wide-open, returning half-open, upper-lip lick and corner lick. Playback opens and
closes the mouth three times, then holds the two squint-and-lick poses. There is
no separate swallow stage. Playback uses the foundation's body channel and exact
neutral restoration, including cancellation and stale-callback protection.

The first integrated whole-cat source was rejected because it was narrower and
more front-facing than the accepted neutral. The fixed-body local-face follow-up
below supersedes that source in production. The accepted original head/body
remain intact. User visual acceptance of the updated expression remains pending.

## Verification

`python tools/build_feed_frames.py` reconstructs only six runtime frames from the
unchanged SHA-verified text sources. Generated frames/previews remain ignored.

`python tools/check_feed_foundation_gate.py` uses actual ApplicationServices,
SharedState, HungerService, ActivityCoordinator, PetWindow graphic methods and
AnimationController in a temporary directory. File identity/results are injected;
no real user file is inspected or recycled. It checks confirmation cancellation,
trusted reward-before-animation, duplicate results, bad receipt, failed reward
write with retry, stale completion, debug isolation, frame canvas, and restoration.

`tools/check_feed_business.py` and `tools/check_feed_recovery.py` are scoped,
non-destructive contract checks. The old pytest suite is not a build gate.

The PyInstaller spec inputs and hidden imports are checked locally. Windows
IFileOperation callbacks, native OLE/DPI interactions and a real EXE launch still
require a Windows runner; this Linux environment does not establish those claims.

The Windows build now also runs `tools/check_feed_exe_startup.ps1`: a fresh
temporary APPDATA/LOCALAPPDATA, eight seconds of process survival, and a marker
written only after the real Tk event loop is active with six registered frames.
It verifies no transaction/reward was created and closes only its own process
tree. A failure to create a desktop/event loop fails this gate; launch readiness
does not establish visual or native recycle acceptance. This script is authored
but cannot be executed in the current Linux environment.

## Follow-up: fixed-body local graphic frames

The whole-cat generated source was rejected after review showed a 28–29%
body-width change. The new manifest version 2 builds every frame over the exact
accepted runtime neutral. Four ImageGen edits of canonical-idle provide only
local mouth/jaw/eyelid texture patches. The body, head contour, ears, paws, and
all alpha pixels remain byte-identical to neutral; only face ROI
(104,312)-(264,476) can change. The unchanged closed frame and a repeated real
half-open key pose complete six indexed frames. Frame timing remains 1.9 seconds.

`feed-face-patches.base64.txt` stores only the four small generated face patches
(about 299 KB text); legacy whole-cat source is retained for provenance but is
not used by the new importer. `local-face-provenance.json` records generation
constraints and approved-reference hash. The shared build gate now enforces
neutral identity outside the face ROI and exact silhouette preservation.
`tools/create_feed_frame_preview.py` renders actual-timeline black/white GIFs and
contact sheets, including an optional 800 ms neutral pause at each end to inspect
transitions. Those pauses are preview-only.

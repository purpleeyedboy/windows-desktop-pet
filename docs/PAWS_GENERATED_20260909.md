# Dual forepaw generated-frame candidate

The runtime uses six newly generated photographic poses: half lift, lift, and
downward press for each cat-own forepaw. The approved default is reused at both
ends. Fifteen timed positions select these poses; this is not a claim of fifteen
different newly painted images per paw. No limb deformation runs during playback.

`assets/paws/v1/generated-frames.json` stores only cropped RGBA replacement pixels,
their coverage masks, source-generation hashes, and the finite pose map. Each
patch contains the generated belly exposed behind the moving limb. Replacement
removes the standing limb before displaying the new pose; alpha overlay alone is
not used. Head, far torso and the opposite forelimb remain the original pixels.
The existing `frames.json` is preserved for recovery history and excluded from the
EXE. All 158 approved asset hashes remain unchanged.

The importer uses a solid magenta transport background and retains the largest
high-confidence cat component plus adjacent antialiased pixels. It reads approved
images only. Generation source paths are supplied in a separate authoring manifest;
the runtime pack records their SHA-256 values and registration shifts. Reproduce
with `python tools/import_generated_paw_frames.py manifest.json output.json qa-dir`.
Manifest entries are `{"left": [["half.png", 0, 14], ["lift.png", 0, 14],
["press.png", 0, 14]], "right": [["half.png", 0, 18], ["lift.png", 0, 18],
["press.png", 0, 18]]}`. Coordinates are relative to the 640 by 768 rendered
reference; patches are stored in its centered 512 by 768 body coordinates.

The actual main entry creates one `ApplicationServices`, passes it into the
window, drains its queue on Tk, and saves its current state on exit. Normal clicks
and debug entries both post `input.paw` into that queue. The adapter owns one
versioned `BODY_ACTION` token; interruption physically cancels timers and restores
the live base. Stale completions cannot overwrite later activities.
Before the first pose it uses the existing head/eye recenter handoff, because the
lifted limb crosses the lower chest. The independent paw timer keeps running
while eye-follow pulses are paused. Completion, interruption and exit resume
following, and recentering never changes the click's captured cursor origin.

Cursor verification uses only an in-memory cursor. Each action starts a new fixed
trajectory, clamps total positive-y displacement to 20–70 physical pixels (35 at
nominal 32-pixel cursor height), respects the original monitor and existing clip,
and abandons cursor movement when the user takes over. It does not inject buttons.

Checks: `python tools/verify_paws_runtime.py` exercises the real window/queue/
controller/frame path, preemption, stale callbacks, repeated cursor actions,
source hashes, head and opposite-paw invariants. The shared graphic contract also
checks 640-pixel logical-neutral anchors after the e0eefbd core repair. Windows
Actions adds a seven-second isolated process-tree check requiring the identified
visible Tk window. It never triggers a paw or moves the real CI cursor.

Trigger: click and release the same front paw, or right-click the cat, open
`调试`, and double-click `左前肢按压` / `右前肢按压` (Enter also works).
The independent build explicitly enables test/debug metadata. Production feature
configuration keeps debug disabled by default.

Visual review at actual display height remains pending on Windows. The action
uses three distinct generated poses per side, so the transition is intentionally
brief and stepped; shoulder/belly fur can change locally with the bending limb.

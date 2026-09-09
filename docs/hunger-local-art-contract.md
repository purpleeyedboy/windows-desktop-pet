# V2.1 hunger authored-frame contract

The approved head, body, eye and Alpha sources are immutable inputs. Hunger
expressions are separate transparent RGBA local frames under
`assets/hunger/v1/`; they must never replace those approved defaults.

`manifest.json` has this lossless runtime shape:

```json
{
  "canvas": [640, 768],
  "sequences": {
    "hungry": [{"file": "hungry/00.png", "duration_ms": 100}],
    "severe": [{"file": "severe/00.png", "duration_ms": 100}],
    "critical": [{"file": "critical/00.png", "duration_ms": 100}]
  }
}
```

Hungry and severe sequences each require at least five genuinely authored
poses and exactly 1700ms total duration: opening 350ms, hold up to 1000ms, and
closing 350ms. Critical requires at least two authored tear poses and loops by
its listed durations. A 30FPS renderer may display a frame repeatedly; it does
not imply 30 unique source images.

Every PNG uses the common 640×768 canvas and transparent background. Local
frames contain the complete moved expression area: mouth cavity, tongue,
muzzle/fur repair, and (where applicable) tears. Vacated pixels must be repaired
inside the local frame so no old muzzle, double tongue, ghost tear, or seam
remains. Lighting, fur texture, scale, and perspective must match the approved
default pose.

At runtime `HungerFrameLibrary` chooses frames only from manifest order and
per-frame duration. `PetWindow.present_hunger` composites the selected authored
frame over the current approved live head/eye pose. Cancellation discards the
overlay and re-renders the live default pose; transforms never accumulate.

The current repository does not yet contain these authored frames because this
execution environment exposes no image-generation tool. The loader and Windows
packager deliberately fail when the manifest or any frame is missing. This is
an explicit incomplete art dependency, not a geometric placeholder and not a
claim of completed hunger animation.

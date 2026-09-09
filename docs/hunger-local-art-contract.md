# V2.1 hunger authored-frame contract

The approved head, body, eye and Alpha sources are immutable inputs. Hunger
expressions are separate transparent RGBA full frames under
`assets/hunger/v1/`; they must never replace those approved defaults.

`manifest.json` has this lossless runtime shape:

```json
{
  "version": 1,
  "frame_type": "full-frame",
  "encoding": "base64-png",
  "canvas": [512, 768],
  "anchor": [256, 768],
  "runtime_canvas": [640, 768],
  "runtime_offset": [64, 0],
  "canonical_idle_sha256": "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7",
  "sequences": {
    "hungry": [{"file": "hungry/00.png.base64", "phase": "open", "duration_ms": 100, "png_sha256": "..."}],
    "severe": [{"file": "severe/00.png.base64", "phase": "open", "duration_ms": 100, "png_sha256": "..."}],
    "critical": [{"file": "critical/00.png.base64", "phase": "loop", "duration_ms": 100, "png_sha256": "..."}]
  }
}
```

Hungry and severe sequences each require at least five genuinely authored
poses and exactly 1700ms total duration: opening 350ms, hold up to 1000ms, and
closing 350ms. Critical requires at least two authored tear poses and loops by
its listed durations. A 30FPS renderer may display a frame repeatedly; it does
not imply 30 unique source images.

Every decoded PNG uses the canonical 512×768 authoring canvas, bottom-center
anchor `[256,768]`, and transparent background. At display time it is placed at
`[64,0]` on the head-follow compositor's 640×768 padded canvas without scaling;
this is the explicit coordinate transform already used by the approved rig. A
640- or 672-wide generated source is
accepted only when the import recipe supplies an explicit crop box producing
exactly 512×768; implicit scaling is forbidden. Full frames contain the complete
cat and moved expression area, so the old mouth is replaced rather than layered
under the new mouth. Lighting, fur texture, scale, and perspective must match the
approved default pose.

At runtime `HungerFrameLibrary` losslessly decodes PNG or base64-PNG resources
and chooses frames only from manifest order and per-frame duration.
`PetWindow.present_hunger` replaces the display with the selected authored full
frame during the expression. Cancellation discards it and re-renders the current
approved live pose; transforms never accumulate.

Import command:

```powershell
python scripts/import_hunger_frames.py --recipe C:\handoff\hunger-import.json `
  --input-dir C:\handoff\frames --output-dir assets\hunger\v1 `
  --qa-dir $env:TEMP\desktop-pet-hunger-qa --encoding base64-png
```

The import recipe uses the same top-level `version`, `canvas`, `anchor`, and
three sequence names; `docs/hunger-import.example.json` is directly usable after
placing the named generated RGBA files in the input directory. Each input entry is
`{"source":"hungry-open-01.png","phase":"open","duration_ms":100}`. Hungry
and severe phases must be ordered `open`, `hold`, `close`, with respective
totals of 350ms, 1000ms, and 350ms. Critical entries use `"phase":"loop"`.
Durations must be positive multiples of 10ms so the generated GIF preserves the
runtime timing exactly. If a generated source is
wider than 512 pixels, that entry must additionally provide an explicit
`"crop_box":[left,top,right,bottom]` whose result is exactly 512×768. The
importer never rescales a frame.

The command emits the runtime manifest/resources plus `hunger-frame-list.json`,
`hunger-contact-sheet.png`, and one duration-accurate GIF per sequence under the
chosen QA directory. QA images are not runtime assets and need not be committed.

The current repository does not yet contain these authored frames because this
execution environment exposes no image-generation tool. The loader and Windows
packager deliberately fail when the manifest or any frame is missing. This is
an explicit incomplete art dependency, not a geometric placeholder and not a
claim of completed hunger animation.

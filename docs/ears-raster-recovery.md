# Ear raster recovery

Recovered from the visible diff of cloud task `task_e_6a9ab44946c083229874237e163ea43e`, latest reported commit `a787e5a05f4812e6a0b0dc13b9f96026d4040d80`, onto remote PR 9 source `63422c256a259439ecba1957a34347ce14b9b46f`.

The full NEW-file DOM rows supplied the ear manifest, raster loader/adapter, preview builder and runtime verifier. The keyframe JSON was parsed from the complete rendered NEW-file text; every embedded PNG decoded successfully. No partial modified-file diff was treated as a complete source file. The eye/window/head-compositor integration here is a local adaptation to the remote source API; the cloud modified-file panels did not finish loading. The cloud authoring baker was not recovered and is not a runtime dependency.

Each side has 12 timed entries (7 distinct lossless PNG crops), totaling 550 ms, with a 500 ms cooldown. Repeated shake poses deliberately reuse the same raster image. All crops originate from the unchanged canonical 512×768 artwork, SHA-256 `48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7`. Runtime playback decodes these graphics; it does not deform an ear procedurally.

The local integration composites each crop before existing head movement, updates the ear alpha during head rotation, invalidates the center cache and redraws the existing eye/head pose. Cancellation clears compositor state even after the adapter is inactive. Old timer callbacks cannot advance a newer ear action.

Validation:

- `python tools/verify_ears_runtime_wiring.py`: actual cache/session rendering, head rotations ±18°, exact neutral recovery, both ear timelines, cooldown, high-priority recovery, stale callbacks and 100 alternating queued requests. It bootstraps the checkout source path and uses fake cursor/schedulers without desktop input.
- `python tools/build_ears_preview.py --output <contact.png> --animation <continuous.gif>`: exports the full timeline for review outside the repository.
- Windows candidate workflow additionally launches the packaged EXE in an isolated temporary profile and requires the identified visible Tk window. This verifies startup only; visual and real interaction acceptance remains separate.

No preview binaries or redundant decoded runtime frames are committed.

## Shared foundation follow-up

The first recovered ear candidate still contained the earlier `e178f371` services/persistence implementation. A later bounded comparison found the missing backup/journal recovery, legacy migration, rotating logs, authoritative shared state, frame-playback APIs and menu-priority fix. This follow-up incorporates the actual shared code from local core commit `6af8446` (remote PR 5 commit `4eda8964ccee8ccd0bd0e2bddb9670618924f90e`), retaining only the ear-specific activity/config extension and the ear compositor/session methods. The metadata now identifies that real shared source.

`verify_ears_foundation_recovery.py` verifies migration without changing the legacy inputs, corrupt-primary backup recovery, pending journal recovery, redacted rotating logs and authoritative state on window close, using only temporary synthetic files. Shared graphic and ear-specific playback checks both remain enabled in the ear builder.

The shared frame-anchor change also needed a compatibility adjustment: old six-frame action endpoints are replaced by the existing 640px-wide center frame, while their physical frames and manifest are 512px-wide. Logical endpoints retain their actual image-center anchor; other authored frames continue to use manifest anchors. This prevents introducing horizontal displacement into the already working baseline.

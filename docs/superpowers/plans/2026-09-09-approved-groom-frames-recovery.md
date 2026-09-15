# Approved Groom Frames Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development, systematic-debugging, desktop-pet-repo-controller, desktop-pet-visual-qa, desktop-pet-windows-release, and verification-before-completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the user-approved, cat-left-paw twelve-frame grooming animation as a real idle/debug runtime action and an independently named Windows candidate.

**Architecture:** Preserve one reconstructable approved RGBA 4-by-3 source sheet and a compact hash/geometry manifest. A deterministic importer validates the delivered color/Alpha hashes, protects enclosed paw-line pixels from becoming holes, crops the twelve cells, normalizes them to a 512-by-768 art canvas with one foot anchor, and places that canvas at `(80, 0)` in the 672-by-768 runtime canvas. The existing coordinated eye tick owns timing; while grooming is active it replaces the entire rendered frame so no dynamic head/eye layer can create overlays.

**Tech Stack:** Python 3.11, Pillow 11, Tk `after`, PyInstaller 6, PowerShell.

## Global Constraints

- Preserve canonical idle SHA-256 `48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7` and all approved head/body/eye sources.
- Implement only the shown cat-left-paw animation; do not mirror the whole cat to fabricate the other side.
- Do not commit generated runtime frames, encoded duplicates, GIFs, or contact sheets; rebuild and validate them deterministically before packaging.
- Do not run the old pytest gate; use focused new contracts and static/build checks.
- Keep Windows build evidence, artifact hash evidence, and real-desktop acceptance as separate gates.

---

### Task 1: Approved source import and Alpha reconstruction

**Files:**
- Create: `assets/groom/v2.1/source/groom-left-approved.png`
- Create: `assets/groom/v2.1/manifest.json`
- Create: `tools/import_groom_frames.py`
- Test: `tests/test_import_groom_frames.py`

- [ ] Write and run failing contracts for attachment dimensions/hashes, 4-by-3 order, enclosed black-line fill, 512-by-768 art placement, `(80, 0)` runtime placement, canonical endpoints, and deterministic output hashes.
- [ ] Combine the delivered color and Alpha sheets without retouching the approved color art; retain the enclosed paw line as opaque pixels.
- [ ] Implement the deterministic importer and make the focused contracts pass.

### Task 2: Full-frame playback and runtime ownership

**Files:**
- Create: `src/desktop_pet/groom_frames.py`
- Modify: `src/desktop_pet/assets.py`
- Modify: `src/desktop_pet/eye_runtime.py`
- Modify: `src/desktop_pet/window.py`
- Test: `tests/test_groom_frames.py`
- Test: `tests/test_groom_runtime.py`

- [ ] Write and run failing playback tests for exact frame progression, real idle trigger, debug trigger, full-frame replacement, first/last canonical restoration, and interruption handoff.
- [ ] Add the smallest frame loader/controller and connect it to the existing single ambient tick and input arbitration.
- [ ] Make the focused contracts pass without changing approved motion-rig assets.

### Task 3: QA and independent Windows candidate

**Files:**
- Modify: `desktop_pet_idle_lick.spec`
- Modify: `build_idle_lick_candidate.ps1`
- Modify: `.github/workflows/windows-idle-lick-candidate.yml`
- Modify: `V2.1_LICK_BUILD.md`
- Modify: `BASELINE_V2.1.md`

- [ ] Generate untracked black/white continuous previews and measure endpoint brightness, bounds, edge alignment, source/runtime sizes, and hashes.
- [ ] Rebuild frames before PyInstaller, validate action-frame hashes, require one exact independently named EXE, and emit its size/SHA-256.
- [ ] Run fresh focused/static/package checks, review the diff size, commit on the current branch, and create a PR without merging.

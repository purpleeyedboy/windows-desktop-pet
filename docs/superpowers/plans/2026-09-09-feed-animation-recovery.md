# Feed Animation Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the V2.1 FEED success animation with reconstructible masked source art, real full-frame playback, and Windows packaging checks without duplicating the shared foundation.

**Architecture:** Track one line-wrapped base64 text bundle containing the supplied color and mask PNG bytes plus a compact JSON manifest. A deterministic Pillow build tool verifies decoded hashes, finds the mask's six large connected subjects, normalizes them to a shared 672×768 foot-aligned canvas, and writes ignored runtime/QA outputs. `PetWindow` owns a dedicated feed playback sequence which suppresses eye/head repaint while active and restores the most recent neutral pose when finished or interrupted; the existing foundation remains the sole owner of FEED transactions, activity, state, hunger, and trusted recycle evidence.

**Tech Stack:** Python 3, Pillow, Tk scheduling, pytest focused tests, PyInstaller/PowerShell Windows packaging.

## Global Constraints

- Do not merge main, destructively reset, operate on real user files, or run the legacy pytest gate.
- Reward and animation remain downstream of the existing trusted recycle receipt and atomic idempotent reward path.
- The feed motion is open mouth → two or three large chews → squint-and-lick → restore; no swallow and no geometric/legacy-jump substitute.
- Source art stays byte-for-byte tracked; generated RGBA frames and previews are ignored and rebuilt before packaging.
- Windows acceptance, real recycle behavior, and user visual acceptance remain separate pending gates.

---

### Task 1: Deterministic source-to-frame builder

**Files:**
- Create: `assets/feed/v1/source/feed-color.png`
- Create: `assets/feed/v1/source/feed-mask.png`
- Create: `assets/feed/v1/manifest.json`
- Create: `tools/build_feed_frames.py`
- Test: `tests/test_build_feed_frames.py`

**Interfaces:**
- Consumes: two exact 1024×1536 source PNGs and six large mask components.
- Produces: `build_feed_assets(manifest_path, output_root)` and six validated 672×768 RGBA PNGs.

- [ ] Write focused tests for source hashes/dimensions, six component extraction (not equal-grid slicing), canonical height/foot alignment, alpha, deterministic hashes, and concise manifest.
- [ ] Run the focused test and observe the expected missing-module failure.
- [ ] Implement the smallest deterministic builder and source manifest.
- [ ] Run focused tests and asset validation.
- [ ] Generate ignored checker/light/dark contact sheets and inspect them.

### Task 2: Real feed-frame playback and restoration

**Files:**
- Modify: `src/desktop_pet/assets.py`
- Modify: `src/desktop_pet/window.py`
- Test: `tests/test_feed_animation.py`

**Interfaces:**
- Consumes: six generated RGBA frames and Tk `after`/`after_cancel`.
- Produces: `load_feed_frames()` and `PetWindow.play_feed_success()` with exclusive full-frame playback and latest-pose restoration.

- [ ] Write focused failing tests for the requested pose sequence, repaint suppression, and restoration on finish/interruption.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement the dedicated minimal player and window integration without modifying shared FEED transaction state.
- [ ] Run focused animation/window tests.

### Task 3: Build and archive gates

**Files:**
- Modify: `.gitignore`
- Modify: `build_feed_core.ps1`
- Modify: `desktop_pet_feed_core.spec`
- Modify: `tools/verify_feed_core_archive.py`
- Modify: `.github/workflows/windows-feed-core.yml`
- Modify: `BUILD_INFO_FEED_CORE.json`
- Modify: `BASELINE_V2.1.md`
- Test: `tests/test_feed_animation_packaging.py`

**Interfaces:**
- Consumes: tracked sources/manifest and the deterministic builder.
- Produces: one independently named feed-animation candidate containing the six real generated frames.

- [ ] Write failing packaging-contract tests.
- [ ] Run them and observe expected failures.
- [ ] Add pre-build generation, real-frame PyInstaller data, archive verification, candidate naming, and ignored output rules.
- [ ] Run focused checks, compileall, deterministic rebuild comparison, source hash comparison, diff-size audit, and `git diff --check`.
- [ ] Update baseline facts and pending gates, commit in small commits, and create the required pull request.

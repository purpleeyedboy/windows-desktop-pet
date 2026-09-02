# Approved Head and Body Runtime Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stale runtime head/body base with the two exact PNGs approved by the user in the “🐈桌面宠物2” continuation, then build a separately named Windows candidate without altering either approved source image.

**Architecture:** Keep the existing eye-follow, blink, continuous head deformation, and idle-tilt code. Add one deterministic offline asset assembler that validates the approved source bytes, alpha-composites the 230×241 head at canvas offset `(24, 204)` over the approved 512×768 body, restores the already-approved neutral-eye aperture pixels only inside the union of the existing eye masks, and writes the derived `underlay.png`; copy the approved body bytes unchanged to `body-backplate.png`. Update only locked hashes, provenance metadata, candidate naming, and archive expectations.

**Tech Stack:** Python 3.11, Pillow 11, pytest 8, PyInstaller 6, PowerShell, GitHub Actions.

## Global Constraints

- Exact approved head: `assets/rig/v1/source/approved/猫头-精准抠图.png`, 230×241 RGBA, SHA-256 `6e57c1be03db1a97a484576f6f88be8639d8f01bbfe5b0d792c68e3d985864e6`.
- Exact approved body: `assets/rig/v1/source/approved/猫身-原像素保留-仅补头部缺口.png`, 512×768 RGBA, SHA-256 `527eaad70a84c611f0839bc3898b5c00f41df383c191771c7e07a1af588e5ce8`.
- Never regenerate, retouch, clone, warp, resize, crop, or overwrite either approved source PNG.
- Lock the approved head canvas offset to `(24, 204)`; it was independently established by exact non-eye pixel alignment with the existing source.
- Preserve the existing eye surfaces and masks byte-for-byte. Preserve the existing neutral underlay only where the union eye mask is nonzero.
- The generated body backplate must be byte-for-byte identical to the approved body PNG.
- Preserve the stable six-frame EXE and rejected QA evidence. Do not touch existing delivery files.
- New candidate name: `桌面宠物-头颈素材更新版.exe`. Do not overwrite any prior EXE.
- Keep NumPy, OpenCV, image generation, and new runtime dependencies out of production.
- Separate automated tests, static checks, archive verification, and real Windows desktop user acceptance.

---

### Task 1: Integrate the exact approved head and body assets

**Files:**
- Create: `assets/rig/v1/source/approved/猫头-精准抠图.png`
- Create: `assets/rig/v1/source/approved/猫身-原像素保留-仅补头部缺口.png`
- Create: `tools/build_approved_runtime_assets.py`
- Create: `tests/test_build_approved_runtime_assets.py`
- Modify: `assets/rig/v1/source/eye-neutral-v1/body-backplate.png`
- Modify: `assets/rig/v1/source/eye-neutral-v1/underlay.png`
- Modify: `assets/rig/v1/source/eye-neutral-v1/authoring.json`
- Modify: `src/desktop_pet/assets.py`
- Modify: `src/desktop_pet/neutral_eye_compositor.py`
- Modify: `desktop_pet_eye_follow.spec`
- Modify: `build_eye_follow_candidate.ps1`
- Modify: `.github/workflows/windows-eye-follow-candidate.yml`
- Modify: `tests/test_neutral_eye_compositor.py`
- Modify: `tests/test_eye_follow_candidate_packaging.py`
- Modify: `tests/test_windows_eye_follow_candidate_workflow.py`
- Create: `.superpowers/sdd/approved-head-body-integration-report.md`

**Interfaces:**
- `build_approved_runtime_assets.build(approved_dir: Path, runtime_source_dir: Path) -> dict[str, str]` validates all inputs, performs the deterministic composite, atomically replaces only the derived underlay/backplate, and returns their SHA-256 values.
- `HEAD_OFFSET = (24, 204)`, `APPROVED_HEAD_SHA256`, and `APPROVED_BODY_SHA256` are immutable module constants.

- [ ] Step 1: Write focused tests before the production assembler exists. Tests must assert the two exact source hashes and dimensions, prove RED from the missing module, require `body-backplate.png` bytes to equal the approved body bytes, require deterministic underlay output, require pixels outside the eye-mask union to equal the approved body-plus-head composite, require fully masked eye pixels to retain the previous neutral underlay, and require both approved source files to remain byte-identical before and after two builds.

- [ ] Step 2: Run `python -m pytest -q tests/test_build_approved_runtime_assets.py` and record the expected missing-module failure.

- [ ] Step 3: Implement the minimal Pillow-only assembler. Decode and validate the approved PNGs and existing eye masks/underlay, place the head without resampling at `(24, 204)`, alpha-composite it over the approved body, use `Image.composite(previous_underlay, approved_composite, max(eye-left-mask, eye-right-mask))`, clear RGB only where final alpha is zero, encode adjacent temporary PNGs, decode-verify, then atomically replace `underlay.png` and `body-backplate.png`. Never write either approved source path.

- [ ] Step 4: Run the focused test, generate the two derived assets twice, and require byte-identical results. Update `authoring.json` with the exact approved source paths, hashes, dimensions, offset, composition rule, and derived output hashes. Update only the two locked Python hash constants.

- [ ] Step 5: Update packaging to the exact filename `桌面宠物-头颈素材更新版.exe` and artifact name `desktop-pet-approved-head-neck-assets`; update the existing packaging/workflow tests first and observe the old-name failures before modifying production packaging files.

- [ ] Step 6: Run `python -m pytest -q tests/test_build_approved_runtime_assets.py tests/test_neutral_eye_compositor.py tests/test_assets.py tests/test_head_neck_deformation.py tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py`, `python -m py_compile` on changed Python files, and `git diff --check`. Record all exact results and limitations in the report.

- [ ] Step 7: Commit one logical change. Do not claim Windows EXE build or desktop acceptance until the hosted Windows workflow and a real user desktop respectively provide those separate proofs.

## Required review and release gate

- A fresh reviewer must verify specification compliance and code quality from the complete task diff.
- Push only after focused tests and review pass.
- The existing pull-request workflow must run against the pushed commit. Download its artifact and independently verify the EXE archive, file size, and SHA-256.
- Real mouse tracking, blink, tilt, drag, resize, menu, single-instance, and light/dark wallpaper appearance remain user desktop acceptance items.

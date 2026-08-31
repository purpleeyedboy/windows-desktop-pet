# Eye Follow Candidate EXE Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

Goal: Build and deliver a separate Windows single-file EXE that packages the already-reviewed continuous arbitrary-angle eye-follow runtime as a clearly labeled test build.

Architecture: Keep the source-checkout probe path for development, but add one runtime resource resolver that prefers the PyInstaller bundle location. Package only the six approved neutral-eye runtime files, comprising five PNGs plus `authoring.json`, into a runtime destination alongside the existing stable keyframes, bubble, font, dialogue, and notice assets. Build and verify the candidate on a GitHub-hosted Windows runner, then upload only the candidate EXE as a short-lived Actions artifact.

Tech Stack: Python 3.11, Pillow 11, Tkinter, Win32 ctypes, PyInstaller 6, PowerShell, GitHub Actions.

## Global Constraints

- Do not overwrite or rename the stable `桌面宠物-6帧猫耳颜文字版.exe`.
- The partial test build is named `桌面宠物-眼球跟随测试版.exe`; do not call it the completed natural-follow release.
- R5 remains blocked until the user visually checks the real Windows EXE.
- Do not implement or claim head or neck deformation, five-direction assets, blinking, idle head tilt, installer, signing, or formal release.
- Preserve the existing continuous arbitrary-angle cursor mapping and the approved horizontal and vertical motion limits.
- Package the six approved neutral-eye files, comprising five PNGs plus `authoring.json`, under `assets/rig/v1/runtime/eye-neutral-v1`; do not package the `assets/rig/v1/source` path, QA evidence, GIFs, generators, NumPy, or OpenCV.
- Keep the candidate EXE below 50 MiB.
- Use `permissions: contents: read`, pinned official Actions commits, Python 3.11, Pillow major 11, and the full unmodified `python -m pytest -q` command before packaging.
- Upload only the candidate EXE with a seven-day retention period; do not create a GitHub Release.
- Every production behavior change follows RED, GREEN, regression verification, independent task review, and final whole-branch review.

---

### Task 1: Frozen-safe neutral-eye runtime loading

Files:

- Modify: `src/desktop_pet/assets.py`
- Modify: `src/desktop_pet/main.py`
- Modify: `tests/test_assets.py`

Interfaces:

- Consume: `desktop_pet.paths.asset_path`, `NeutralEyeCompositor.load`, and the existing source-checkout neutral-eye directory.
- Produce: `neutral_eye_runtime_root() -> Path` and `load_neutral_eye_compositor(root: Path | None = None) -> NeutralEyeCompositor`.

Steps:

- [ ] Add failing tests proving the runtime root uses `asset_path("assets", "rig", "v1", "runtime", "eye-neutral-v1")`, the loader prefers an explicit root, and a source checkout falls back only when the packaged runtime directory is absent.
- [ ] Run the focused tests and record the expected missing-interface failures.
- [ ] Implement the minimal resolver and loader, preserving `load_neutral_eye_source_probe` for compatibility.
- [ ] Change `main.py` to call the frozen-safe loader without changing window behavior.
- [ ] Run `python -m pytest -q tests/test_assets.py tests/test_main.py tests/test_neutral_eye_compositor.py`.
- [ ] Run the applicable non-Tk regression suite and `git diff --check`.
- [ ] Commit the task and write its SDD report.

Acceptance:

- Source checkouts still load the exact approved neutral-eye source.
- A frozen bundle resolves only the runtime destination and never depends on the repository source path.
- Existing fallback, actions, and cursor behavior remain unchanged.

### Task 2: Separate candidate build, archive gate, and Windows artifact

Files:

- Create: `desktop_pet_eye_follow.spec`
- Create: `build_eye_follow_candidate.ps1`
- Create: `tools/verify_eye_follow_candidate_archive.py`
- Create: `tests/test_eye_follow_candidate_packaging.py`
- Create: `.github/workflows/windows-eye-follow-candidate.yml`
- Create: `tests/test_windows_eye_follow_candidate_workflow.py`
- Update: `.superpowers/sdd/progress.md`

Interfaces:

- Consume: existing stable build assets and the six files from `assets/rig/v1/source/eye-neutral-v1`.
- Produce: `dist-eye-follow-candidate/桌面宠物-眼球跟随测试版.exe` and Actions artifact `desktop-pet-eye-follow-candidate`.

Steps:

- [ ] Add failing contract tests for the candidate name, one-file build, runtime-only archive destination, exclusion of source and offline tooling, complete stable runtime assets, exact archive-byte verification, 50 MiB size gate, full test command, and read-only pinned workflow.
- [ ] Run the focused contract tests and record the expected missing-file failures.
- [ ] Add the minimal separate PyInstaller spec, PowerShell build gate, archive verifier, and Windows workflow.
- [ ] Run the focused contract tests, Task 1 tests, and `git diff --check`.
- [ ] Commit the task and write its SDD report.
- [ ] Publish a dedicated remote branch and PR without rewriting the default branch.
- [ ] Let the PR workflow run the full Windows suite, build the EXE, verify archive bytes and size, and upload the artifact.
- [ ] Download the artifact, verify its SHA-256 and size locally, and retain the EXE for user delivery.

Acceptance:

- Windows full tests pass before packaging.
- PyInstaller produces exactly one EXE with the fixed test-build name.
- The archive contains all required stable runtime assets plus exactly the six approved neutral-eye files at the runtime destination.
- The archive contains no rig source path, QA evidence, GIF, NumPy, or OpenCV.
- The EXE is below 50 MiB, receives a recorded SHA-256, and is downloadable without merging or overwriting the stable release.

## Deferred Gates

- User visual judgment of eye alignment, amplitude, smoothness, seams, and transparent edges on the real desktop.
- Head and neck following, five-direction assets, blinking, idle head tilt, 10-minute and 30-minute idle observations, multi-monitor and DPI matrix, and formal release approval.

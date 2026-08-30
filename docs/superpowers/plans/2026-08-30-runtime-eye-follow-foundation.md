# Runtime Eye-Follow Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, testable Windows cursor and smoothing controller that continuously computes arbitrary-angle eye targets for the already accepted neutral-eye rig, without yet connecting the controller to visible window composition.

**Architecture:** Put cursor acquisition and pure motion math in one Tk- and Pillow-independent runtime module. Inject the clock, scheduler, cursor source, and pose callback so Linux CI can prove the Windows contract with fakes. Keep visible composition out of this increment because the current click animations end on three different non-neutral frames and would visibly snap when the neutral eye rig resumed.

**Tech Stack:** Python 3.11+, standard-library `ctypes`, `math`, `time`, pytest.

## Global Constraints

- Read the cursor every `33ms` through Win32 `GetCursorPos`; do not install a global mouse hook and do not redraw directly from raw mouse events.
- Compute targets continuously from the cursor vector relative to the current on-screen eye midpoint supplied by the geometry provider. Do not use direction names, angle rounding, sprite lookup, nearest-sector selection, or a finite direction table.
- Use the accepted eye-motion envelope: horizontal `±3.0` source pixels and vertical `±2.0` source pixels.
- Scale the activation radius with the current displayed pet height so the accepted `100.0` screen-pixel radius at `280` display pixels becomes `display_height * 100.0 / 280.0`.
- Smooth both axes with `alpha = 1 - exp(-dt / 0.060)` and clamp `dt` to `0..0.100` seconds.
- If cursor acquisition fails, target exact center and converge there without breaking the scheduler.
- At most one scheduled tick may be active. `start()` and `pause()` must be idempotent; `stop()` must cancel the active callback and prevent rescheduling.
- The scheduler, cancel callback, lifecycle calls, and ticks must all run on the Tk UI thread; generation checks prevent stale queued callbacks, not general cross-thread access.
- Suppress pose callbacks when both source-pixel axis changes are below `0.006`, but continue lightweight cursor sampling.
- Add no runtime dependency and do not import Pillow, NumPy, OpenCV, Tk, or the offline `tools` package from the controller module.
- This increment does not modify `PetWindow`, the renderer, action frames, visible eye composition, head directions, blink, tilt, packaging, or EXE output. R5 remains blocked.

---

### Task 1: Continuous Windows Cursor and Eye-Motion Controller

**Files:**
- Create: `src/desktop_pet/eye_follow.py`
- Create: `tests/test_eye_follow.py`
- Create: `.superpowers/sdd/runtime-eye-follow-task-1-report.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Produce `CursorPoint(x: int, y: int)` as an immutable value.
- Produce `Win32CursorProvider(user32=None)` with `position() -> CursorPoint | None`; a failed Win32 call returns `None`.
- Produce `cursor_target(cursor_dx: float, cursor_dy: float, activation_radius: float) -> tuple[float, float]` using the reviewed overflow-safe radial-clamped elliptical mapping.
- Produce immutable `EyeGeometry(midpoint_x: float, midpoint_y: float, display_height: float)`.
- Produce `EyeMotionController(scheduler, cancel, cursor_provider, geometry_provider, pose_changed, clock=time.monotonic)`, where `geometry_provider: Callable[[], EyeGeometry]` is evaluated every tick, with idempotent `start()`, `pause()`, `resume()`, and `stop()` lifecycle methods.
- `pose_changed(eye_x: float, eye_y: float)` receives smoothed source-pixel offsets only when the stability threshold is crossed.

**Acceptance Criteria:**
- Tests cover cursor center, four cardinals, four diagonals, half radius, exact radius, beyond radius, negative screen coordinates, continuity near an angle boundary, invalid numeric inputs, and `sys.float_info.max` without non-finite output.
- Tests prove `GetCursorPos` success and failure using a fake Win32 object and the real `ctypes` point structure contract.
- Tests prove exact `60ms` exponential smoothing, monotonic no-overshoot convergence, approximate equivalence across different time steps, and the `100ms` long-frame clamp.
- Tests prove failed cursor acquisition converges toward center.
- Tests prove the activation radius scales from `100.0` at height `280` to `200.0` at height `560`.
- Tests prove repeated start/resume calls do not create duplicate callbacks, pause cancels the active callback without resetting pose, stop prevents future scheduling, and stable input suppresses redundant pose callbacks while sampling continues.
- Focused tests are observed RED before implementation, then GREEN. The currently available cloud suite passes after the last change.
- The diff contains no visible runtime integration or adjacent animation work.

**Steps:**

- [ ] Write `tests/test_eye_follow.py` first for mapping, Win32 acquisition, smoothing, failure recovery, scaled activation radius, stable redraw suppression, and lifecycle ownership.
- [ ] Run `python -m pytest tests/test_eye_follow.py -q` and record the expected RED failure caused by the missing runtime module.
- [ ] Implement the smallest standard-library-only `src/desktop_pet/eye_follow.py` satisfying the tests.
- [ ] Run the focused tests until GREEN, then run `python -m pytest -q` once for regression coverage.
- [ ] Commit the task, create the review package, obtain independent spec-compliance and code-quality approval, and update the durable progress ledger.

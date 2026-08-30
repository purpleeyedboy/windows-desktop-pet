# Task 3 Report: Deadline Controller and Pure Runtime Session

## Scope and baseline

- Implementation base: `780199e2a2d68dfbbd0a771d58b7bc36ce746d26`.
- Changed only `src/desktop_pet/eye_follow.py`, `tests/test_eye_follow.py`, new
  `src/desktop_pet/eye_runtime.py`, new `tests/test_eye_runtime.py`, and this
  report.
- No action/model/animation/window/main/assets/compositor/QA/R5/packaging work
  was performed. The progress ledger was not edited; the primary agent owns it.

## TDD evidence

### RED

After adding the controller deadline/synchronization tests and the pure runtime
session tests, before production changes:

```text
python -m pytest tests/test_eye_follow.py tests/test_eye_runtime.py -q
34 failed, 38 passed in 0.40s
```

The failures were the expected contract gaps: the old controller always queued
another unconditional 33ms, `EyeMotionController.synchronize_pose` did not
exist, and `desktop_pet.eye_runtime` did not exist.

During self-review, a second focused RED exposed integer-delay rounding at a
future deadline less than a picosecond away:

```text
python -m pytest tests/test_eye_follow.py::test_controller_never_rounds_a_future_deadline_to_zero_delay -q
FAILED: assert [33, 0] == [33, 1]
1 failed in 0.05s
```

The minimal correction guarantees a positive 1ms delay rather than a zero-delay
catch-up callback.

### GREEN

Final focused result after the O(1) late-deadline coalescing refactor:

```text
python -m pytest tests/test_eye_follow.py tests/test_eye_runtime.py -q
73 passed in 0.05s
```

Focused cadence/recenter proof:

```text
python -m pytest -vv \
  tests/test_eye_follow.py::test_controller_absolute_deadline_preserves_start_cadence \
  tests/test_eye_follow.py::test_controller_coalesces_missed_deadline_without_catch_up_burst \
  tests/test_eye_follow.py::test_controller_coalesces_a_delayed_callback_to_one_future_deadline \
  tests/test_eye_follow.py::test_controller_never_rounds_a_future_deadline_to_zero_delay \
  tests/test_eye_runtime.py::test_recenter_interpolates_at_33_66_99_and_132ms_then_completes \
  tests/test_eye_runtime.py::test_first_recenter_callback_after_duration_displays_center_without_overshoot \
  tests/test_eye_runtime.py::test_delayed_recenter_callbacks_coalesce_elapsed_progress_monotonically
9 passed in 0.08s
```

## Exact deadline evidence

- Work durations 0ms, 7ms, and 20ms record callback start times
  `[0.033, 0.066, 0.099, 0.132]` seconds. Their follow-up delays are 33ms,
  26ms, and 13ms respectively, derived from the prior absolute deadline.
- With 40ms of work, recorded starts are `[0.033, 0.099]`: the missed 66ms
  deadline is skipped, the actual start-to-start smoothing interval is 66ms,
  and the next queued delay is 26ms. There is one tick per callback, one live
  token, and no zero-delay burst.
- A first callback coalesced at 120ms schedules one future deadline at 132ms
  with a 12ms delay. Deadline skipping is O(1), not proportional to lateness.
- Smoothing continues to use actual callback start times and the existing
  100ms cap. Pause/stop generations reject stale callbacks; resume establishes
  a new `now + 33ms` phase.

## Synchronization and recenter evidence

- `synchronize_pose` rejects pre-start, running, and stopped states; accepts
  only the actual paused state; validates finite `±3.0/±2.0` input; updates
  internal and last-emitted pose without emitting or scheduling.
- A centered target within the stability threshold snaps the internal pose to
  exact `(0.0, 0.0)` and emits exact center once.
- Runtime start composes/displays exact center before starting one eye token.
  Only a successful display commits `last_displayed_pose`.
- Geometry tests exercise drag, resize, and negative coordinates with the live
  authoritative rect and the required source-to-screen formulas.
- Recenter tests observe 0.75, 0.50, 0.25, and exact 0.00 of the starting pose
  at elapsed 33/66/99/132ms. A first callback at 150ms displays exact center
  immediately. Delayed callbacks use absolute elapsed progress, remain
  monotonic, and never overshoot.
- Centered recenter completes synchronously without a token. Successful
  completion synchronizes the paused controller before entering `playing`.
  `resume_following` repaints nothing and owns exactly one fresh eye loop.
- Compose/display failures are contained, preserve the last successful pose,
  enter `disabled` once, cancel eye/recenter work, and return explicit fallback
  outcomes thereafter. Generation-tagged stale recenter callbacks are inert.

## Regression and scope verification

Applicable non-Tk suite:

```text
python -m pytest -q --ignore=tests/test_window.py
182 passed, 3 skipped, 1107 warnings in 47.89s
```

The warnings are pre-existing Pillow `Image.getdata` deprecations outside Task
3. An attempted full `python -m pytest -q` reached `185 passed, 3 skipped` but
reported 20 setup errors, all from `tk.Tk()` raising `TclError` because this
environment has no `$DISPLAY`; there were no assertion failures.

Additional checks:

- `python -m compileall -q src/desktop_pet/eye_follow.py src/desktop_pet/eye_runtime.py` — pass.
- `git diff --check` — pass.
- Forbidden-import scan for Tkinter, Pillow, tools, NumPy, OpenCV, Qt, and
  OpenGL in `eye_runtime.py` — no matches.
- Forbidden-scope scan for action, animation, window, head/blink/tilt,
  keyframes, assets, QA, and compositor-algorithm ownership — no matches.

## Self-review and risks

- The pure session deliberately owns no action selection, action images,
  rendering cache, asset loading, Tk adapter, or secondary event loop.
- `SessionResult.FALLBACK` is the narrow handoff for future legacy action
  integration; Task 4/5 may extend transitions but must preserve the tested
  disabled no-compose guarantee.
- Tk/window integration remains intentionally unverified and out of scope.
  The headless full-suite setup errors are the only environment limitation.
- The repository TDD skill references a `testing-anti-patterns.md` companion
  that is not present in this checkout. The added fakes remain state-based,
  exercise real controller/session behavior, and do not add test-only
  production hooks.

## Independent-review fix wave

The first independent review returned two Important findings and one Minor:
external compose/display reentrancy could revive or mutate a stopped session,
completion callback exceptions could escape and strand `playing`, and direct
stop coverage did not enumerate every lifecycle state.

### Review-fix RED

Tests were added before changing production code for initial, following, and
recentering compose/display callbacks that reentrantly stop the session;
centered and timed completion exceptions; completion that stops then raises;
and direct idempotent stop from unstarted, playing, disabled, and stopped.

```text
python -m pytest tests/test_eye_runtime.py -q \
  -k 'reentrant or completion_exception or stop_is_directly'
9 failed, 3 passed, 19 deselected in 0.17s
```

The failures reproduced all review traces: initial start returned accepted
after stop, following work committed a post-stop pose, recenter leaked
`synchronize_pose` `RuntimeError`, and both centered/timed completion errors
escaped.

### Review-fix GREEN

`RuntimeEyeSession` now increments a lifecycle epoch on every ownership
transition and stop. Session-owned work snapshots both epoch and state, then
revalidates after compose, after display, and before start/recenter caller
continuations. Stale/reentrant work cannot display after compose-time stop,
commit after display-time stop, complete, reschedule, or revive the session.

Completion exceptions are contained. If the callback left the lifecycle at
the same `playing` epoch, the synchronized controller deterministically resumes
exactly one following loop. If the callback changed state or stopped, that
newer lifecycle wins and is not overwritten.

```text
python -m pytest tests/test_eye_runtime.py -q \
  -k 'reentrant or completion_exception or stop_is_directly'
12 passed, 19 deselected in 0.02s

python -m pytest tests/test_eye_follow.py tests/test_eye_runtime.py -q
85 passed in 0.05s

python -m pytest -q --ignore=tests/test_window.py
194 passed, 3 skipped, 1107 warnings in 47.40s
```

The Pillow warnings remain pre-existing and outside Task 3. No Task 3 scope
expansion was required for the review fixes.

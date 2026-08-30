# Runtime Eye-Follow Task 1 Report

## TDD evidence

Tests were written before `src/desktop_pet/eye_follow.py` existed.

RED command:

```bash
python -m pytest tests/test_eye_follow.py -q
```

RED result: `33 failed in 0.21s`. Every failure was the expected
`ModuleNotFoundError: No module named 'desktop_pet'`; no runtime package or
production controller had been created yet.

GREEN command:

```bash
python -m pytest tests/test_eye_follow.py -q
```

GREEN result: `33 passed in 0.04s`.

Full-suite command:

```bash
python -m pytest -q
```

Full-suite result: `91 passed, 3021 warnings in 52.94s`. The warnings are the
pre-existing Pillow `Image.getdata` deprecation warnings in the offline neutral
eye asset tests.

## Implementation

- Added immutable `CursorPoint`, `Win32CursorProvider`, and the reviewed
  overflow-safe radial-clamped elliptical `cursor_target` mapping.
- Added the standard-library-only `EyeMotionController`: Win32 cursor sampling
  every 33 ms, display-height activation-radius scaling, 60 ms exponential
  smoothing with a 100 ms frame cap, center fallback on acquisition failure,
  and a 0.006 source-pixel callback threshold.
- The controller owns one scheduler callback at a time; start/pause/resume are
  idempotent and stop cancels the current callback and disables rescheduling.

## Self-review

- Scope: only the new runtime package, focused tests, this report, and progress
  status changed. There is no `PetWindow`, renderer, animation, composition,
  packaging, or EXE integration.
- Lifecycle: the scheduled handle is cleared at tick entry, cancellation occurs
  on pause/stop, and scheduling is guarded by running/stopped state.
- Numeric safety: inputs are finite/positive checked; scaled-vector math avoids
  overflow for `sys.float_info.max`; smoothing uses a finite clamped delta time.
- Test quality: tests cover the required cardinal/diagonal/radius/invalid/
  extreme mapping cases, actual ctypes point-pointer behavior, smoothing and
  long-frame behavior, provider failure, radius scaling, lifecycle ownership,
  and callback suppression while sampling continues.

## Review-fix TDD evidence

New regression tests were added before the fixes: one explicitly invokes stale
callback A after pause/resume has scheduled callback B, and one uses
`sys.float_info.max` display height.

RED command:

```bash
python -m pytest tests/test_eye_follow.py -q
```

RED result: `2 failed, 33 passed in 0.05s`. The stale callback sampled once and
could replace the tracked B callback; the maximum display height did not reject
the non-finite computed activation radius.

GREEN command:

```bash
python -m pytest tests/test_eye_follow.py -q
```

GREEN result: `35 passed in 0.02s`.

Full-suite command:

```bash
python -m pytest -q
```

Full-suite result: `93 passed, 3021 warnings in 51.18s`.

## Review fixes and self-review

- Scheduled callbacks now capture a controller generation. Pause, stop, and a
  fresh start advance that generation; a callback whose generation is stale
  returns before clearing the current handle, sampling, emitting a pose, or
  scheduling again.
- The computed activation radius is finite and positive checked after scaling,
  so finite display height cannot overflow the controller into an invalid state.
- Removed the task-created `src/desktop_pet/__init__.py`; this runtime module
  works as a namespace import locally and will not overwrite the real remote
  package initializer.
- Review check: the stale-A test proves B remains the callback cancelled by the
  next pause. The overflow test is independent of cursor sampling. No visible
  composition or other adjacent runtime work was added.

## Final whole-increment review-fix TDD evidence

The geometry-provider, fixed-POINT-layout, finite-maximum-height, and terminal
stop regression tests were written before this correction was implemented.

RED command:

```bash
python -m pytest tests/test_eye_follow.py -q
```

RED result: `11 failed, 26 passed in 0.12s`. The existing controller had no
`EyeGeometry` or live geometry-provider interface, retained a 16-byte host-long
POINT layout on Linux rather than Windows' fixed 8-byte ABI layout, and could
not satisfy the corrected constructor contract.

GREEN command:

```bash
python -m pytest tests/test_eye_follow.py -q
```

GREEN result: `37 passed in 0.02s`.

Full-suite command:

```bash
python -m pytest -q
```

Full-suite result: `95 passed, 3021 warnings in 52.88s`.

## Final review fixes and self-review

- `EyeGeometry` is immutable and `geometry_provider` is evaluated on every
  live tick. Its current midpoint supplies cursor deltas and its current height
  supplies the activation radius, so dragging or resizing requires neither a
  new controller nor a pose reset.
- Height scaling divides by the reference height before multiplying, preserving
  a finite activation radius for `sys.float_info.max`. Geometry values are
  validated each tick before use.
- `_POINT` has signed `ctypes.c_int32` fields, with tested 8-byte size and
  offsets `x=0`, `y=4`, matching the Win32 POINT contract on every host.
- Terminal `stop()` remains terminal after both `start()` and `resume()` calls.
  The stale-generation behavior remains covered, and the controller documents
  that scheduler, cancellation, lifecycle, and ticks are Tk-UI-thread-only;
  generations are not a threading primitive.
- Scope remains limited to the controller, tests, plan/report/progress
  evidence. No PetWindow, renderer, composition, action asset, packaging, or
  EXE code changed.

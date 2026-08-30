# Task 5 Report: PetWindow Source-Probe Wiring and Safe Fallback

## Scope and baseline

- Implementation base: `286ecbb`.
- Changed only `src/desktop_pet/assets.py`, `src/desktop_pet/window.py`,
  `src/desktop_pet/main.py`, their three focused tests, and this report.
- No visual asset, QA evidence, compositor algorithm, eye math, action/session
  foundation, dependency, package, release, EXE, or R5 work was performed.
- R5 remains blocked.

## TDD evidence

### Initial RED

Tests for the source probe, main injection/fatal path, headless construction,
live geometry, literal center identity, atomic rollback, failure streaks,
composition fallback, later action failure, cancellation failure, shutdown,
and menu lifecycle were added before production changes.

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_assets.py tests/test_main.py tests/test_window.py \
  -k 'source_probe or headless or main_enables or main_routes'
15 failed, 29 deselected in 0.43s
```

All failures were missing API/behavior assertions. There was no Tk construction
or `$DISPLAY` dependency in this selection.

### Self-review RED

After the first GREEN, a new regression captured an external resize render
failure while an action controller still owned playback. The unchanged adapter
left the controller busy:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_window.py \
  -k 'headless_recenter_reuses or headless_resize_failure'
1 failed, 1 passed, 34 deselected in 0.26s
```

The minimum fix tracks the current action at the adapter boundary and uses the
same controller's non-terminal `cancel_current` before enabling fallback. No
second controller was introduced.

A final shutdown audit found that `main()` discarded the PetWindow instance and
could destroy the root directly if `mainloop()` returned without the menu close
path. A focused test failed before the fix:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_main.py \
  -k finally_uses_pet_close
1 failed, 4 deselected in 0.12s
```

`main()` now retains the instance and invokes its idempotent `close()` in
`finally`; only pre-construction failures use direct guarded root cleanup.

### Final focused GREEN

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_assets.py tests/test_main.py
10 passed, 1 skipped in 0.37s

PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_window.py -k headless
13 passed, 23 deselected in 0.63s
```

The skip is the existing Windows mutex test. The headless selection directly
constructs the real `PetWindow` with a fake root, renderer, cursor, compositor,
menu variable, and bubble; it is not a duplicated pure implementation.

## Source probe and startup

- `neutral_eye_source_probe_root()` resolves
  `assets/rig/v1/source/eye-neutral-v1` from the source checkout itself. Its
  name and documentation explicitly say source-checkout-only, and its test
  proves it does not call the bundled `asset_path` resolver.
- `load_neutral_eye_source_probe()` delegates to the fixed-hash validated
  `NeutralEyeCompositor.load` contract.
- `main()` orders startup as DPI, Tk root, physical frame validation, source
  probe load, `Win32CursorProvider`, and `PetWindow` injection. Probe
  `ValueError` joins the existing fatal startup path.
- Direct source import with `PYTHONPATH=src` loaded the real compositor and
  composed `(512, 768) RGBA` center with midpoint `(122.5, 349.0)`.
- `PYTHONPATH=src python -m desktop_pet.main` reached the expected no-display
  startup failure and exited 1 on this cloud host; it cannot exercise Tk or
  Win32 here.

## Runtime ownership and frame identity

- Production construction requires both compositor and cursor provider.
  Legacy construction exists only behind explicit `legacy_mode=True`, which
  the older Tk tests use.
- A small compositor adapter caches exactly one literal center object while
  delegating every moving pose. Runtime initialization displays that center,
  commits it as the current source object, and then owns exactly one 33ms eye
  token.
- Live session geometry reads the current `_window_rect` on every callback.
  Headless coverage moves to a negative-coordinate 512px-high rect and proves
  both compositor movement and the successful renderer coordinates/size.
- Normal clicks route to `RuntimeEyeSession.request_action()`. Logical frame 0
  is a renderer no-op when it is the exact current center object; real physical
  01 through 04 render by source-object identity; frame 5 returns to that same
  center; finish resumes one eye token without repainting.
- A moving-pose recenter test proves the final center presentation reuses the
  cached object and frame 0 still adds no second renderer call.
- Fallback uses the single existing `AnimationController`, one shared
  `ActionCycle`, and physical 00 through 05. Its coordinator orders
  `peek -> play acceptance -> commit -> phrase`; failed play does not commit or
  show a phrase.

## Atomic rendering and failure routing

- `_apply_image` and `_move_to` compute resized image, fitted height, rect, and
  coordinates into locals. The layered renderer is called before root geometry
  or any source/resized/rect/height cache commits.
- The transient failure test snapshots the exact source-image object,
  resized-image object, rect, display height, and root geometry. One injected
  renderer exception preserves every snapshot member, reports once, stops eye
  ownership, and enables legacy action playback. The next physical frame 00
  succeeds, resets the failure streak to zero, commits the action once, and
  shows one matching phrase.
- Any successful render resets the consecutive failure count. A subsequent
  isolated failure is again count one, not persistent failure.
- A second consecutive renderer exception sets rendering unavailable, stops
  eye and animation work, preserves the last successful caches, and blocks all
  later renderer attempts. The close path still destroys the root.
- Composition failure enters the session's disabled state once, makes no
  renderer call, reports once, and leaves physical click actions operational.
- A later scheduled action callback render failure first invalidates the same
  controller owner, then stops/source-disables the session and enables physical
  fallback. A resize failure during an action now follows the same explicit
  cancellation handshake.
- An unresolved cancel rejection/exception is handled conservatively: session
  and controller are terminally stopped and later actions remain blocked, so
  the adapter cannot create a second image owner.

## Shutdown

- Menu Exit and `WM_DELETE_WINDOW` both reference one idempotent `close()`.
- Close order is session stop, animation stop/token cancellation, bubble
  destroy/hide cancellation, then root destroy.
- A captured stale animation callback invoked after two close calls cannot
  compose, render, present a phrase, mutate ownership, or schedule more work.
- `main()` retains its guarded final cleanup, so an already destroyed root is
  harmless.

## Regression, environment, and remaining gates

Applicable non-Tk regression after the final production change:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS=ignore::DeprecationWarning \
  python -m pytest -q --ignore=tests/test_window.py
265 passed, 3 skipped in 51.87s
```

The skips are existing platform gates. Deprecation warnings from the host's
out-of-range Pillow 12 runtime were suppressed only for readable output; the
project remains bounded to Pillow 11 and no dependency changed.

Real Tk attempt on this host:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_window.py --tb=no
16 passed, 20 errors in 0.63s
```

All 20 errors are fixture setup failures from `tk.Tk()` raising
`TclError: no display name and no $DISPLAY environment variable`. All 16 tests
that do not construct real Tk, including the final 13 headless adapter tests,
passed.

The Windows-only renderer/mutex gates, real Tk lifecycle, four display sizes,
callback performance/CPU/memory measurements, drag/resize across real monitors,
light/dark visual review, and every neutral/action join remain manual Windows
gates. Source tests do not approve motion naturalness or publication.

## Independent review remediation

The independent Task 5 review returned **Not approved** with four Important and
two Minor findings. Tests for every finding were added before the remediation.
The review-wave RED was:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_window.py tests/test_main.py \
  -k 'probe_presents or initial_composition or first_renderer_failure_without or partial_init or geometry_failure_restores or geometry_rollback or action_geometry or real_cancel_exception or legacy_commit_mismatch or public_drag_and_resize or constructor_failure_reports'
14 failed, 1 passed, 41 deselected in 0.75s
```

The public negative-coordinate test initially used a drag displacement that did
not cross zero. Its input was corrected before production work so that it
exercises a genuinely negative monitor position; this was a test correction,
not a production fix.

### Hidden startup and one loop

- The root remains withdrawn while the session composes and presents the
  literal neutral center. The verified event order is `compose`, `render`,
  `geometry`, `deiconify`, `lift`, then the one eye-loop `after` call.
- Initial composition failure explicitly presents physical `jump[0]`, then
  shows the window. The disabled session owns no timer and reports once.
- A first renderer failure with no successful presentation snapshot aborts
  construction while the root is still hidden. It cannot fall through to an
  empty window or be mistaken for the identity no-op.

### Transactional partial construction

- Constructor failure first makes callbacks inert, then stops the existing eye
  session, stops the one animation controller, destroys the bubble, and
  rethrows. Cleanup is guarded for failures before each resource exists.
- Coverage injects failure after animation creation and after the session has
  queued a callback but its scheduler raises. The captured stale callback is
  inert and cleanup order is `eye-stop`, `animation-stop`, `bubble-destroy`.
- `main()` then reports the fatal error, destroys the still-live root, and
  closes the mutex; this order has focused coverage.

### Renderer and geometry presentation transaction

- Renderer presentation and `root.geometry` are now one transaction. Source,
  resized image, rectangle, display height, geometry, and the success snapshot
  commit only after both calls succeed.
- If geometry fails after the candidate render, the last successful resized
  image and exact geometry are restored before legacy fallback is enabled.
  Apply, move, and scheduled action callback paths assert exact rollback.
- If either rollback render or rollback geometry fails, rendering becomes
  unavailable immediately and both eye and animation activity stop.
- A raw renderer success followed by geometry failure is not a successful
  presentation and does not reset the renderer-failure streak. After one
  renderer failure, a successful rollback preserves count one; the next
  renderer failure still trips the two-failure fuse. This supersedes the
  earlier broad wording that any renderer success resets the streak.

### Ownership and minor findings

- Legacy fallback treats every `cancel_current` result other than literal
  `True` as terminal action failure and returns without starting fallback.
  Coverage uses the real controller with `after_cancel` raising
  `RuntimeError`; no second owner or later fallback action appears.
- Legacy commit mismatch now routes through `_cancel_action`, which also clears
  adapter ownership state.
- Public drag and resize coverage preserves negative-coordinate monitor
  geometry through both operations.

### Review-wave verification

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_window.py tests/test_main.py \
  -k 'probe_presents or initial_composition or first_renderer_failure_without or partial_init or geometry_failure_restores or geometry_rollback or action_geometry or real_cancel_exception or legacy_commit_mismatch or public_drag_and_resize or constructor_failure_reports'
15 passed, 41 deselected in 0.58s

PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_window.py -k headless
27 passed, 23 deselected in 0.77s

PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_assets.py tests/test_main.py
11 passed, 1 skipped in 0.36s

PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  --ignore=tests/test_window.py
266 passed, 3 skipped in 51.21s
```

The fresh real-Tk attempt remains environment-limited:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_window.py --tb=no
30 passed, 20 errors in 0.74s
```

All 20 errors are the same `tk.Tk()` setup failure caused by the cloud host
having no `$DISPLAY`. The 30 non-real-Tk tests passed, including the explicitly
selectable 27-test headless window integration suite. The Windows/manual gates
listed above remain unchanged; R5 remains blocked.

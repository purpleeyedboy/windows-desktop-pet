# Task 4 Report: Transactional Action Ownership and Cancellation

## Scope and baseline

- Implementation base: `c12215d`.
- Changed only `src/desktop_pet/model.py`, `src/desktop_pet/animation.py`,
  `src/desktop_pet/eye_runtime.py`, their focused tests (including new
  `tests/test_model.py`), and this report.
- No window/main/assets/bubble implementation, compositor, visual asset, QA,
  R5, dependency, packaging, or EXE work was performed. The progress ledger
  was not edited; the primary agent owns it.

## TDD evidence

### RED

The first focused run followed the test-only change and preceded every
production change:

```text
python3 -m pytest -q tests/test_model.py tests/test_animation.py \
  tests/test_eye_runtime.py \
  -k 'action_cycle or six_frames_keep or stop_cancels or action_request_accepts or real_action_logical'
7 failed, 2 passed, 52 deselected in 1.08s
```

The failures were the expected missing contracts: `ActionCycle.peek/commit`,
the animation `cancel` injection/terminal stop, and RuntimeEyeSession action
collaborators and ownership APIs.

### Initial GREEN before independent review

After the minimum implementation and callback-edge self-review additions:

```text
python3 -m pytest -q tests/test_model.py tests/test_animation.py tests/test_eye_runtime.py
70 passed in 1.36s
```

The applicable non-Tk suite is also green:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --ignore=tests/test_window.py
230 passed, 3 skipped, 1107 warnings in 49.60s
```

Later review-fix sections supersede these initial counts; the final applicable
non-Tk result for Task 4 is 261 passed and 3 skipped.

The skips are existing platform gates. The warnings are pre-existing Pillow
`Image.getdata` deprecations outside Task 4. A full-suite attempt reached the
same non-window work without assertion failures, then reported 20
`tests/test_window.py` setup errors because `tk.Tk()` has no `$DISPLAY` in this
environment; Task 4 does not alter or claim Tk coverage.

## Transaction and lifecycle evidence

- `peek()` is repeatable and non-advancing. `commit(expected)` advances once
  only on an exact current-action match; a mismatch raises `ValueError` and
  leaves the current action unchanged. `next()` delegates to that transaction.
- A request snapshots the peeked action before pausing/recentering. Repeated
  requests in `recentering` or `playing` reject without adding callbacks,
  selecting a phrase, or changing the cycle.
- Playback `False` and playback exceptions leave the cycle and phrase work
  untouched, clear pending ownership, and resume exactly one following token.
  Resume performs no additional compose/display; the already-required
  recenter frame is the only display in that completion callback.
- Playback acceptance commits exactly once before phrase selection. Phrase
  chooser/presenter exceptions are contained. Stop and finish transitions
  invoked reentrantly by play/phrase callbacks win through lifecycle-epoch
  checks; stale continuations cannot commit, present, resume, or overwrite the
  newer state.
- Only the matching committed active action can finish. A valid finish
  synchronizes the paused eye controller to exact center, clears action
  ownership, and resumes one eye token without composing or repainting.
  Wrong, duplicate, stale, pending-only, disabled, and stopped finishes reject.
- Stop clears both pending and active ownership. Disabled `request_action()`
  returns explicit `FALLBACK` without another compositor call or logical-frame
  selection.

## Six-frame and cancellation evidence

- Six-frame playback still emits indices `0,1,2,3,4,5` in order. Exactly six
  `90ms` schedules are observed: five between frame changes plus the final
  90ms hold before `finished`.
- The controller owns one generation-tagged scheduled slot/token. Terminal
  `stop()` clears ownership first, cancels the live token when cancellation is
  injected, and permanently rejects later `play()` calls. With legacy callers
  that supply no cancel callback, generation/slot checks still make stale
  callbacks inert.
- Tests invoke callbacks from old generations after stop and after a later
  playback begins; neither can show, finish, clear, or reschedule newer work.
- Initial and scheduled frame exceptions abort ownership and re-raise.
  Scheduler exceptions do the same. Immediate and once-reentrant schedulers
  deterministically either complete with accepted `play() == True` or retain
  exactly the nested live token. A reentrant stop/cancelled start returns false.
  Reentrant stop from both initial and scheduled frame callbacks leaves no busy
  ownership or token.
- Finished callbacks run only after busy ownership/token state is cleared;
  tested reentrant next playback is not overwritten by the stale completion.

## Real-frame identity and fallback evidence

- Tests load all three actions with existing `desktop_pet.assets.load_frames`,
  which applies the committed exact-name, six-file, `512x768 RGBA` validation.
- For each real hydrated `jump`, `squash`, and `shake` mapping, logical slots 0
  and 5 are `is`-identical to the single successfully composed/displayed
  cached neutral-center object. Slots 1 through 4 are `is`-identical to that
  action's physical loaded objects 01 through 04. Physical objects 00 and 05
  remain present and untouched.
- A pure legacy fallback proof combines the same transactional `ActionCycle`,
  cancellable controller, and real physical mappings. Three accepted requests
  emit physical 00 through 05 for `jump`, `squash`, and `shake`, with one
  handwritten matching phrase record and one matching finish each. It observes
  18 frame callbacks and 18 90ms schedule intervals. This is only the required
  pure fallback building-block proof; Task 5 must test the production adapter
  and bubble coordination.
- Git baseline comparison reports no byte changes under `assets/keyframes`,
  `assets/rig`, or `qa`; all 18 action PNG bytes remain unchanged on disk and
  no assets module was edited.

## Verification and risks

- `eye_runtime.py` has no Tk, Pillow, assets-loader, tools, NumPy, OpenCV, Qt,
  OpenGL, or bubble import. Runtime action work remains injected and pure.
- `git diff --check` passes, and the scope scan contains only the three allowed
  source modules, three focused test files, and this report.
- Task 5 still must wire real Tk `after_cancel`, renderer frames, bubble
  presentation/cancellation, shutdown ordering, and the disabled legacy path.
  This task proves the pure building blocks only and makes no UI or shutdown
  adapter claim.
- Visual naturalness of neutral-to-01 and 04-to-neutral joins remains an
  explicit later human/Windows gate. No crossfade, visual edit, or R5 work was
  introduced.

## Independent-review fix wave

The first independent review was not approved and identified three Important
gaps: synchronous animation completion preceded Runtime ownership, accepted
playback was not cancellable when commit lost its reservation, and the
controller retained the caller's mutable frame-count dictionary.

### Review-fix RED

Tests were changed first and composed the real `RuntimeEyeSession` and
`AnimationController` for both synchronous completion and commit invalidation:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_animation.py tests/test_eye_runtime.py \
  -k 'synchronous_scheduler_callbacks or cancel_current_is_nonterminal or frame_counts_are_snapshotted or frame_counts_require or count_access_exception or real_controller_synchronous_completion or real_controller_is_cancelled or real_controller_start_failure'
13 failed, 66 deselected in 0.26s
```

The failures reproduced every review trace: synchronous `play()` returned
false after completing; early finish was rejected before commit; no
non-terminal cancellation protocol existed; original-map mutation raised
`KeyError`; invalid counts were accepted; count-read failure left `busy`; and
real frame-0/scheduler-start failure could not be composed through the missing
cancel interface.

### Review-fix GREEN

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_animation.py tests/test_eye_runtime.py \
  -k 'synchronous_scheduler_callbacks or cancel_current_is_nonterminal or frame_counts_are_snapshotted or frame_counts_require or count_access_exception or real_controller_synchronous_completion or real_controller_is_cancelled or real_controller_start_failure'
13 passed, 66 deselected in 0.15s

 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_model.py tests/test_animation.py tests/test_eye_runtime.py
82 passed in 1.44s

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --ignore=tests/test_window.py
242 passed, 3 skipped, 1107 warnings in 50.28s
```

### Ownership and cancellation correction

- Runtime establishes provisional ownership before calling `play_action`.
  A matching finish during that call is accepted once but recorded as early;
  it does not resume eyes or clear ownership. `AnimationController.play()` now
  reports that a normally synchronous-completed request was accepted.
- After accepted playback, Runtime commits once, attempts matching phrase
  choice/presentation, and only then consumes the recorded early finish. The
  real fully synchronous controller test observes frames 0 through 5, six
  90ms holds, one commit, one phrase, final `following`, and exactly one live
  eye token.
- `AnimationController.cancel_current(expected)` is a non-terminal operation:
  it rejects a mismatch, invalidates the accepted generation, clears ownership,
  cancels the live token when possible, and permits later playback. Runtime
  receives this as `cancel_action`.
- The real commit-invalidation composition mutates the cycle reentrantly from
  frame 0. Runtime calls `cancel_action` successfully before scheduling the
  following eye token; the old animation callback is cancelled/generation
  stale, no phrase is shown, and there is no second image owner.
- If an injected cancel operation raises or reports false for an accepted live
  owner, Runtime deliberately remains paused in `playing` rather than risk two
  render owners. The adapter must surface/stop that broken collaborator; this
  conservative failure cannot provide automatic recovery without a truthful
  cancellation acknowledgement.

### Frame-count and failure correction

- Construction copies the count mapping and rejects zero, negative, boolean,
  non-integer values. Reentrant mutation of the original mapping cannot change
  the accepted action's validated frame count.
- Frame-count access is inside the same abort-and-reraise boundary as frame and
  scheduler callbacks. Even deliberately corrupted internal count state clears
  token/busy ownership before `KeyError` escapes to the owner.
- With the real controller, frame-0 callback failure and first-schedule failure
  both abort the generation before `play()` raises. Runtime therefore treats
  the request as unaccepted, leaves cycle/phrase untouched, and resumes one eye
  loop. Its logical frame 0 is the already-displayed neutral-center identity,
  so this start failure introduces no action-image overwrite.
- The injected `play_action` contract therefore requires `False` or an
  exception to mean that no live action owner remains. Runtime's tested
  production building block is `AnimationController.play`, which enforces that
  rule; an arbitrary callback that raises after secretly retaining ownership
  would violate the collaborator contract and cannot be safely inferred from a
  boolean/exception interface.
- A later post-accept frame/scheduler callback failure still aborts controller
  ownership and re-raises by contract; Task 5's UI adapter must route that
  exceptional callback to its session/window failure or shutdown handling.
  Task 4 does not add a second event loop or a UI error channel.

## Second independent-review fix wave

The second review was not approved. It found four Important ownership/start
handshake gaps and one Minor observability gap: external duplicate finishes
could consume an early finish during phrase work; cancellation could report
success after its callback reentrantly installed a successor; nested
synchronous plays shared one completion marker; frame 0 preceded first
scheduler acceptance; and cancellation failure had no Task 5 signal.

### Second review-fix RED

The new combination and controller regressions failed before production was
changed:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_animation.py tests/test_eye_runtime.py \
  -k 'reentrant_stop_from_frame_callback or frame_exception_aborts or scheduler_exception_aborts or cancel_current_reentrant_successor or nested_fully_synchronous or real_controller_synchronous_completion or real_reentrant_successor or cancel_action_failure or real_controller_start_failure'
10 failed, 1 passed, 73 deselected in 0.31s
```

After the first minimum correction, a separate assertion exposed an unsafe
public recovery escape while cancellation ownership was unresolved:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_eye_runtime.py -k cancel_action_failure_stays_paused
2 failed, 56 deselected in 0.19s
```

### Second review-fix GREEN

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_animation.py tests/test_eye_runtime.py \
  -k 'reentrant_stop_from_frame_callback or frame_exception_aborts or scheduler_exception_aborts or reentrant_scheduler_callback_keeps or cancel_current_reentrant_successor or nested_fully_synchronous or real_controller_synchronous_completion or real_reentrant_successor or cancel_action_failure or real_controller_start_failure'
12 passed, 72 deselected in 0.19s

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_model.py tests/test_animation.py tests/test_eye_runtime.py
87 passed in 1.61s

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --ignore=tests/test_window.py
247 passed, 3 skipped, 1107 warnings in 53.35s
```

### Duplicate-finish and nested-play correction

- While an early matching finish is pending, every later external matching
  finish is rejected, including calls reentered by phrase selection and
  presentation. Only `_begin_action` privately consumes the pending finish
  after phrase work. The real composition observes commit, choose, present,
  then finish, and resumes exactly one following loop.
- Playback acceptance is stored in a generation-local outcome rather than a
  controller-wide completion marker. A fully synchronous action A can finish,
  reentrantly start and fully finish B, and both nested `play()` calls report
  their own accepted result without overwriting each other.

### Cancellation revalidation and failure signal

- `cancel_current(expected)` clears and invalidates the requested generation
  before invoking cancellation, then revalidates generation and owner after
  the callback. If that callback reentrantly starts a successor, cancellation
  returns false. A real controller/session composition proves Runtime remains
  paused and never starts an eye loop beside the successor.
- A false or raising `cancel_action` records public `action_failure` with
  `ActionFailure.CANCEL_REJECTED` or `ActionFailure.CANCEL_RAISED` and invokes
  the injected `on_action_failed(action, reason)` signal. Runtime remains in
  `playing`; even an explicit `resume_following()` rejects while unresolved
  action ownership/failure remains, so no eye token can escape.
- Task 5 must stop or visibly surface this signal. Task 4 deliberately cannot
  infer whether an untruthful external cancel callback retained ownership, so
  it provides diagnosis and conservative pause rather than automatic resume.

### Superseded first-frame start handshake

This fix wave initially scheduled the first hold before frame 0. The next
review demonstrated that this shortened frame 0's visible hold by callback
work time. The third review-fix wave below supersedes that ordering while
retaining the cached-neutral identity/no-action-overwrite contract.

## Third independent-review fix wave

The third review was not approved. It found three Important controller gaps:
abort cancellation could reentrantly install a successor, a scheduler could
return an unfired real token after ownership was lost, and scheduling before
frame 0 stole callback work time from the first 90ms hold.

### Third review-fix RED

Tests were changed before production code. The targeted run reproduced all
three findings across unit and real Runtime/controller compositions:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_animation.py tests/test_eye_runtime.py \
  -k 'reentrant_stop_from_frame_callback or frame_exception_aborts or scheduler_exception_aborts or abort_cleanup or scheduler_post_return or frame_work_does_not_shorten or real_controller_start_failure or post_return_cleanup or real_controller_later_failure'
10 failed, 3 passed, 79 deselected in 0.32s
```

The failures included a measured 73ms frame-0 hold after 17ms of frame work,
successful successor installation during abort cleanup, three uncancelled
post-return tokens, and the old pre-schedule display ordering. The three
passing cases were existing frame-0 and later-callback owner-abort guarantees.

### Third review-fix GREEN

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_animation.py tests/test_eye_runtime.py \
  -k 'reentrant_stop_from_frame_callback or frame_exception_aborts or scheduler_exception_aborts or abort_cleanup or scheduler_post_return or frame_work_does_not_shorten or real_controller_start_failure or post_return_cleanup or real_controller_later_failure'
13 passed, 79 deselected in 0.16s

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_model.py tests/test_animation.py tests/test_eye_runtime.py
95 passed in 1.47s

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --ignore=tests/test_window.py
255 passed, 3 skipped, 1107 warnings in 50.65s
```

### Abort and post-return cleanup correction

- Abort clears the failed generation under a cleanup guard. Every reentrant
  `play()` during the injected cancellation is rejected, and a `finally`
  restores the prior guard state so nested cleanup remains guarded and later
  legitimate playback is allowed. A live-token abort regression proves the
  cancel callback cannot install a successor and no failed generation remains.
- Each scheduled closure records whether it fired. If a scheduler returns an
  unfired real token after reentrant stop, cancel, or successor transition made
  its generation/slot stale, the old stack cancels that token under the same
  cleanup guard. It does not clear or overwrite a successor already installed
  by the scheduler reentrancy. A real Runtime/controller test additionally
  proves cleanup-callback playback is rejected before one eye loop resumes.
- If token cancellation itself raises, the generation/slot guard still makes
  its callback inert, but physical queue removal cannot be guaranteed by a
  callback that violates the injected cancellation contract.

### Restored frame timing and failure ownership

- Frame 0 now completes before the first 90ms schedule is armed. A fake clock
  adds 17ms inside every frame callback and observes frame starts at 0, 107,
  214, 321, 428, and 535ms: frame 1 starts exactly 90ms after frame 0 completes,
  and finish occurs exactly 90ms after frame 5 completes. All six delays remain
  90ms and all logical indices remain 0 through 5, including the final hold.
- Both frame-0 failure and first-scheduler failure may invoke the frame-0
  adapter, but its object is `is`-identical to the already displayed cached
  neutral center. Task 4 therefore proves no action-image overwrite, not a
  literal absence of a display call. Task 5 must make this identity case a
  renderer no-op to meet the end-to-end no-repaint requirement.
- Real Runtime/controller tests show frame-0 and initial-scheduler exceptions
  return to one following eye loop with no action generation, while later
  scheduled-frame and scheduler exceptions clear controller ownership and keep
  Runtime conservatively paused. Later callback failure routing remains a
  Task 5 adapter responsibility.

## Fourth independent-review fix wave

The fourth review was not approved with one remaining Important transaction
gap: a cancelled outer `play()` attempt could start a descendant before the
outer stack returned false or propagated an exception. Runtime would then
resume eye following beside that descendant.

### Fourth review-fix RED

The new tests first reproduced frame, synchronous scheduler, and finished
handoff traces with the unchanged controller:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_animation.py tests/test_eye_runtime.py \
  -k 'frame_zero_cancel or sync_scheduled_frame_cancel or scheduler_post_return_cancels or nested_fully_synchronous or finished_callback_runs or finished_handoff_then_raise or real_reentrant_play_attempt_failure'
7 failed, 4 passed, 87 deselected in 0.27s
```

The failures left successors accepted from frame 0 and a synchronous scheduled
frame, left a descendant busy after a raising finished callback, and reproduced
the real Runtime/controller two-owner false/raise paths. The four passes were
the stop/cancel post-return paths and the two existing legal finished handoffs.

### Fourth review-fix GREEN

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_animation.py tests/test_eye_runtime.py \
  -k 'frame_zero_cancel or sync_scheduled_frame_cancel or scheduler_post_return_cancels or nested_fully_synchronous or finished_callback_runs or finished_handoff_then_raise or real_reentrant_play_attempt_failure'
11 passed, 87 deselected in 0.17s

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_model.py tests/test_animation.py tests/test_eye_runtime.py
101 passed in 1.42s

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --ignore=tests/test_window.py
261 passed, 3 skipped, 1107 warnings in 52.47s
```

### Generation-local attempt and handoff correction

- Every `play()` owns a local outcome with its generation, completion bit, and
  callback phase. The controller keeps the active synchronous attempt stack in
  `try/finally`; frame and scheduler callbacks remain unresolved phases, so
  their reentrant `play()` calls reject even after they cancelled the old owner.
- The only nested-play opening is the top attempt with `completed=True` while
  its phase is `finished_handoff`. The old action and token are cleared before
  entering that phase. Existing asynchronous and fully synchronous finished
  callbacks still start accepted successors, including nested synchronous
  completion with generation-local results.
- Before a false return or propagated exception, the outer attempt removes any
  active generation newer than its own. A raising finished callback uses the
  generation at handoff as its stricter baseline, aborting and cancelling a
  successor it started before re-raising. Cleanup cancellation remains guarded,
  so it cannot replace that descendant with another action.
- Frame-0 cancel-to-successor and synchronous scheduled-frame
  cancel-to-successor tests cover both normal false return and a raised frame
  callback. The real Runtime/controller equivalents prove the successor calls
  reject, controller ownership is empty, the cycle is untouched, and exactly
  one following eye token resumes for both false and exception outcomes.
- This in-flight rule is synchronous call-chain ownership, not a thread-safety
  guarantee. Once an accepted asynchronous `play()` has returned, its attempt
  is resolved; later event-loop callbacks continue to use generation/token and
  explicit cancellation ownership rather than the attempt stack.

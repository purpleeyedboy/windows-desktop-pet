# V2.1 shared runtime API

This is the common runtime contract inherited by the hunger, grooming, feeding,
ear, forelimb, and anticipation branches. Those branches must adapt to these
services rather than create another application state, queue, clock, or store.

## Startup and ownership

`desktop_pet.main.main()` loads `BuildInfo`, acquires the single-instance mutex,
creates one `ApplicationServices` with `create_application_services()`, loads the
V2.1 state envelope, and injects the services into `PetWindow`. The Tk thread is
the sole event consumer and `ActivityCoordinator` is the sole state writer.

The factory's real import path is
`desktop_pet.foundation.services.create_application_services`. There is no
`desktop_pet.foundation.api` module and no `get_services()` global accessor.
Features receive the one application-owned `ApplicationServices` instance by
constructor injection from `main()` through `PetWindow`; they must not create a
second service container or hide one behind a process-global singleton.

```python
from desktop_pet.foundation.config import BuildInfo
from desktop_pet.foundation.services import create_application_services

services = create_application_services(BuildInfo.load_embedded())
state = services.load_state()
window = PetWindow(root, frames, services=services, persisted_state=state, ...)

# A feature adapter is constructed with this same instance.
feed = FeedAdapter(services=services)
services.runtime.bind("feed.request", feed.on_request)
services.runtime.post("feed.request", source="window", operation_id=operation_id)
```

`FeedAdapter` above is an integration-shape example, not a class supplied by the
foundation. The FEED branch owns that adapter and its UI/business implementation.

## Events and state

```python
runtime.post(event_type: str, *, source: str,
             correlation_id: str | None = None, **payload: Any) -> str
runtime.bind(event_type: str, handler: Callable[[RuntimeEvent], None]) -> None
runtime.drain(limit: int = 128) -> int
runtime.snapshot() -> RuntimeSnapshot
```

Every `RuntimeEvent` carries `type`, `source`, monotonic time, correlation ID,
and payload. Producers, including worker threads and OLE callbacks, only post.
Only the creating Tk thread may call `drain()`.

`RuntimeSnapshot` keeps `health`, `activity`, `eye`, `mouth`, `tear`, `particle`,
derived `input_gate`, and `activity_version` orthogonal.

## Activity and animation adapter

```python
coordinator.request_activity(activity: Activity,
                             animation_id: str | None = None,
                             timeout_seconds: float = 30.0) -> ActivityToken | None
coordinator.permits(activity: Activity) -> bool
coordinator.complete(token: ActivityToken,
                     animation_id: str | None = None) -> bool
coordinator.cancel_and_recover(token: ActivityToken | None = None) -> bool
```

An accepted request returns a new version and cancellation ID. Completion checks
the current activity, version, cancellation ID, and animation ID. A stale callback
returns `False`. `PetWindow` adapts the existing `AnimationController` by holding
the returned token through `_trigger_action_direct()` and reporting it from
`_animation_finished()`; click/menu requests enter through `runtime.post()`.

Future channel adapters use the same shape:

```python
animation.play(channel, frames, activity_token)
# completion/cancellation posts an event containing activity_token
```

Head/eye following remains an independent existing channel. `DRAG_PREVIEW` keeps
eye following active while hiding tears. `Health.CRITICAL` denies body/groom and
normal-hunger activity but does not deny feed, menu, shutdown, or debug requests.

### Real graphic frame contract (2026-09-07 increment)

All character actions supplied by feature branches are ordered RGBA graphic
frames—not runtime resize/squash, mesh motion, drawn geometry, or aliases to an
old action. `30 FPS` is only a refresh target and does not prescribe the asset
count. Timing and finite loop sections are explicit:

```python
sequence = AnimationSequence(
    steps=(FrameStep(0, 66), FrameStep(1, 100), FrameStep(2, 133)),
    anchor=(256, 768),
    loop_start=1,
    loop_end=2,
    loop_count=1,
    layer_mode="full",
)
window.register_graphic_clip("feature.action", frames, sequence)
window.request_graphic_clip("feature.action", Activity.BODY_ACTION)
```

Graphic playback retains the feature's real activity: `BODY_ACTION`, `GROOM`,
`NORMAL_HUNGER_ANIMATION`, `SEVERE_HUNGER_ANIMATION`, or
`FEED_ANIMATION`. Do not relabel feeding or grooming as `BODY_ACTION` to get a
clip to play. Transaction processing/review and shutdown are not graphic
activities. `DRAG_PREVIEW` also stays outside this body player because it must
retain live eye following instead of pausing for a full-frame clip. A current
activity token must match the clip name at playback and
completion; stale completion cannot alter a replacement clip. Custom clips
explicitly restore the accepted neutral frame before eye following resumes.

`AnimationController` is the actual window player and schedules every displayed
frame with that frame's `duration_ms`. Its finite timeline expands only the
declared loop segment. The existing runtime activity token/playback ID guards,
cancel callback, and `_recover_body_channel()` return to the cached accepted
neutral frame and prevent accumulated transforms or stale completion.

Full frames must share the accepted neutral canvas, be RGBA, use one source-space
anchor, and contain zero RGB under fully transparent Alpha. Local feature art must
include one restoration/backfill layer per frame and uses:

```python
window.register_local_graphic_clip(
    name, layers, restorations, offsets,
    AnimationSequence(..., layer_mode="local"),
)
```

The restoration is composited before the moved part so a vacated paw, ear, or
mouth cannot leave a duplicate/transparent hole. The result is a full canonical
frame before entering the same player. Feature branches must package their frame
manifest and actual lossless frames (or a deterministically lossless text source)
and provide frame contact sheet plus continuous preview.

The current base executable wires the existing `jump`, `squash`, and `shake`
graphic files through `assets/keyframes/playback.json` as a real invocation
example. It does **not** claim that hand-licking, ear, forelimb, hunger-mouth,
feeding, or anticipation art exists; those six frame sets remain required from
their feature branches. The approved neutral/head/body/eye files remain immutable.

## Regions and coordinates

```python
regions.update_pose(*, window: Rect, source_size: tuple[int, int],
                    anchors: dict[str, tuple[int, int]] | None = None) -> int
regions.hit_test(screen_point: Point, purpose: str) -> RegionHit | None
```

Coordinates are physical screen pixels and may be negative. Each rendered frame
rebuilds regions from the authoritative window rectangle, never from the prior
frame. Hits carry `coordinate_version`. The native renderer derives a Win32
window region from current Alpha with a 16-physical-pixel sensing expansion, so
pixels beyond that region pass through instead of the full rectangle blocking.

## Time, random, persistence, and journal

```python
clock.utc_now() -> datetime
clock.monotonic() -> float
store.load(*, default: dict[str, Any]) -> dict[str, Any]
store.save(data: dict[str, Any], *, durable: bool = False) -> None
journal.append(record: dict[str, Any], *, durable: bool) -> None
services.load_state() -> dict[str, Any]
services.state_snapshot() -> dict[str, Any]
services.commit_state(next_state: dict[str, Any], *, durable=False) -> dict[str, Any]
services.update_state(mutate: Callable[[dict[str, Any]], None], *, durable=False) -> dict[str, Any]
```

Production uses `SystemTimeSource` and `SystemRandomSource`. The state schema is
`desktop-pet-v2.1` version 1 and reserves integer `hunger_anchor_utc_seconds`,
`pending_transaction`, and `recent_operation_ids`. Writes use a sibling temporary
file, flush/fsync, validation, atomic replace, and an independently validated
`state.backup.json`. Load recovery order is formal state, valid backup, then the
latest non-terminal sanitized journal transaction. Corrupt inputs are retained in
`recovery/`. The journal recursively strips full-path keys. Feature branches must wait
for durable writes at transaction boundaries and must enter transaction review
when `pending_transaction` is present before enabling feeding.

The unified data root is `%LOCALAPPDATA%/DesktopPet`: `state.json`,
`state.backup.json`, `settings.json`, `feed-journal.jsonl`, `logs/`, and
`recovery/`. A one-time migration copies missing files from `DesktopPetV21`
without changing or overwriting the legacy source. `SharedState` persists a
candidate before publishing it as the in-memory snapshot; `close()` ignores its
legacy state argument so a stale startup copy cannot overwrite a committed reward.
Normal logs rotate at 2 MiB with five backups and redact complete paths.

## FEED integration responsibilities

The common foundation already supplies these concrete, shared mechanisms:

- the `FEED_CONFIRM`, `FEED_ANIMATION`, `FEED_PROCESSING`, and
  `TRANSACTION_REVIEW` activities and their priority/cancellation rules;
- one serial runtime event queue and one application-owned services instance;
- validated persist-before-publish state commits, including
  `pending_transaction` and `recent_operation_ids` fields;
- a durable, path-sanitizing transaction journal with non-terminal recovery;
- an OLE diagnostic drop target and a dedicated STA file-worker queue; and
- startup transition to `TRANSACTION_REVIEW` when journal recovery leaves a
  pending transaction.

The common foundation deliberately does **not** claim a `feed_activity` boolean
or a permanently true capability gate. Activity permission must be requested
from `services.runtime.coordinator` at the moment of transition and may be denied
or preempted. There is likewise no fake recycle/reward service in this package.

The FEED branch remains responsible for all of the following:

1. Interpret OLE/file candidates without logging a complete user path, present
   confirmation, and post its inputs/results to the shared runtime queue.
2. Implement and verify trusted Recycle Bin handling under ordinary-user
   permissions. The foundation drop target currently rejects drops and does not
   move, delete, or recycle a user file.
3. Define transaction phases and append/flush the recovery record before each
   irreversible boundary; then durably commit `pending_transaction` before file
   work and durably clear it only after review/completion.
4. Make rewards idempotent with stable `OperationId` values and the shared
   `recent_operation_ids` ledger. A repeated operation must not grant a second
   reward, including after restart or transaction review.
5. Supply and register the real feeding frame assets and interaction UI. The
   foundation only supplies the coordinated graphic-frame player contract.

Until those FEED-owned items are implemented and exercised on Windows, the
presence of the foundation activities, journal, or worker is not evidence that
feeding, trusted recycling, or idempotent rewards are complete.

## OLE, workers, and debugging

```python
dragdrop.register(hwnd: int) -> None
dragdrop.candidate_snapshot() -> dict[str, int | bool]
dragdrop.close() -> None
file_worker.submit(operation_id: str, operation: Callable[[], object]) -> None
file_worker.close() -> None
debug.register(name: str, command: Callable[[], None], *, enabled=True) -> None
```

The Windows Tk STA calls `OleInitialize`, installs the shared diagnostic
`IDropTarget` with `RegisterDragDrop`, and revokes/uninitializes it on close. The
foundation rejects drops and performs no file operation. The single dedicated
file-worker thread initializes its own OLE STA, executes a feature-supplied
operation, and posts only its operation ID/status/result back to `runtime`; it
never mutates state directly or logs complete paths.

The test build exposes one top-level **调试** item opening one directly scrollable
second-level list (wheel, arrows/Listbox navigation, Home, End, Esc). Unavailable
feature commands are visibly disabled. `BuildInfo` and `FeatureConfig` are
immutable and the embedded build JSON is the identity source used by About/status.

## Shutdown

`PetWindow.close()` cancels the runtime timer, stops eye and animation channels,
destroys the bubble, closes runtime/OLE, persists state, and destroys Tk. `main()`
always releases the single-instance mutex. A second launch activates/notifies the
existing instance and reports the requested build instead of silently returning.

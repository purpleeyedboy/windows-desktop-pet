# V2.1 shared runtime API

This is the common runtime contract inherited by the hunger, grooming, feeding,
ear, forelimb, and anticipation branches. Those branches must adapt to these
services rather than create another application state, queue, clock, or store.

## Startup and ownership

`desktop_pet.main.main()` loads `BuildInfo`, acquires the single-instance mutex,
creates one `ApplicationServices` with `create_application_services()`, loads the
V2.1 state envelope, and injects the services into `PetWindow`. The Tk thread is
the sole event consumer and `ActivityCoordinator` is the sole state writer.

```python
services = create_application_services(BuildInfo.load_embedded())
state = services.load_state()
window = PetWindow(root, frames, services=services, persisted_state=state, ...)
services.runtime.post("feature.request", source="hunger", operation_id=operation_id)
```

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

# V2.1-PAWS foundation integration contract

PAWS does not own an application state, event queue, clock, or state store.  PR5 must
provide the `PawActivityService` adapter consumed by `PetWindow`:

- `request_paw(side) -> ActivityApproval | None` asks the one serialized
  `ActivityCoordinator` for the Forepaw activity lock.
- `validate_paw(approval) -> bool` validates animation ID, state version and
  cancellation token against the current Activity before every sample/callback.
- `complete_paw(approval)` completes only the still-current approved activity.
- `paw_allowed() -> bool` applies Health and priority policy: Normal/Hungry are
  allowed; SevereHungry is allowed only outside its severe animation; CriticalHungry,
  drag/drop, every feed stage, menu, Recovery, TransactionReview and shutdown deny it.

The shared `InputRouter` must back `PawInputGate.any_button_down()` and
`pointer_interaction_blocked()`.  The shared `CursorMovementService` must implement
only position read/set, pointer nominal height, monitor bounds and current clip reads.
It must not expose input synthesis, cursor capture or clip mutation to PAWS.

`LocalPawActivityAdapter` is explicitly a feature-local source-checkout bridge.  It
has no global state policy and must be replaced by PR5's adapter before this candidate
is described as acceptance-ready.

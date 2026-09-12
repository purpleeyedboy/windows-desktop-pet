# Activity recovery reentrancy fix — 2026-09-12

Recovery callbacks may synchronously acquire a new activity, including shutdown.
The old cancellation/timeout/preemption finally block must not clear its token.
The interrupted request must not overwrite the callback's newer activity.

The regression reproduces six failures before the fix (three operations, with
and without callback exceptions). After the fix, these six cases and six normal
lifecycle cases pass using Python unittest. The Windows workflow runs the same
checks without skipping them or requiring pytest.

Scope: coordinator runtime and focused regression only. No visual assets or
file recycling implementation changed. Full application integration, Windows
EXE behavior and visual acceptance remain pending. A successful candidate build
alone is not full-suite or user acceptance evidence.
